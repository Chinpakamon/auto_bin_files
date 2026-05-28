import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

Patch = Dict[str, Any]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_binary(path: Path) -> bytearray:
    try:
        return bytearray(path.read_bytes())
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")


def build_patch(original_path: Path, modified_path: Path) -> Patch:
    original = read_binary(original_path)
    modified = read_binary(modified_path)

    if len(original) != len(modified):
        raise SystemExit(
            f"Files have different sizes: {original_path}={len(original)}, "
            f"{modified_path}={len(modified)}"
        )

    changes: List[Dict[str, Any]] = []
    i = 0
    while i < len(original):
        if original[i] == modified[i]:
            i += 1
            continue

        start = i
        old = bytearray()
        new = bytearray()
        while i < len(original) and original[i] != modified[i]:
            old.append(original[i])
            new.append(modified[i])
            i += 1

        changes.append(
            {
                "offset": start,
                "length": len(old),
                "old": old.hex(),
                "new": new.hex(),
            }
        )

    return {
        "format": "firmware-byte-patch-v1",
        "source": {
            "original": str(original_path),
            "modified": str(modified_path),
            "size": len(original),
            "original_sha256": sha256_file(original_path),
            "modified_sha256": sha256_file(modified_path),
        },
        "changes": changes,
    }


def save_patch(patch: Patch, patch_path: Path) -> None:
    patch_path.write_text(json.dumps(patch, indent=2, ensure_ascii=False), encoding="utf-8")


def load_patch(patch_path: Path) -> Patch:
    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Patch file not found: {patch_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON patch file {patch_path}: {exc}")

    if patch.get("format") != "firmware-byte-patch-v1":
        raise SystemExit("Unsupported patch format")
    if not isinstance(patch.get("changes"), list):
        raise SystemExit("Patch file has no valid 'changes' list")
    return patch


def apply_patch(input_path: Path, patch_path: Path, output_path: Path, force: bool = False) -> int:
    data = read_binary(input_path)
    patch = load_patch(patch_path)
    changes = patch["changes"]

    for idx, change in enumerate(changes, start=1):
        try:
            offset = int(change["offset"])
            old = bytes.fromhex(change["old"])
            new = bytes.fromhex(change["new"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"Invalid change #{idx}: {exc}")

        end = offset + len(old)
        if offset < 0 or end > len(data):
            raise SystemExit(f"Change #{idx} is outside input file bounds")
        if len(old) != len(new):
            raise SystemExit(f"Change #{idx} changes length; only in-place patches are supported")

        current = bytes(data[offset:end])
        if current != old and not force:
            raise SystemExit(
                f"Old bytes mismatch at change #{idx}, offset 0x{offset:X}.\n"
                f"Expected: {old.hex()}\n"
                f"Actual:   {current.hex()}\n"
                f"Use --force to write new bytes anyway."
            )
        data[offset : offset + len(new)] = new

    output_path.write_bytes(data)
    return len(changes)


def verify_files(actual_path: Path, expected_path: Path) -> bool:
    actual = read_binary(actual_path)
    expected = read_binary(expected_path)
    return actual == expected


def cmd_diff(args: argparse.Namespace) -> int:
    patch = build_patch(Path(args.original), Path(args.modified))
    save_patch(patch, Path(args.patch))
    changed_bytes = sum(c["length"] for c in patch["changes"])
    print(f"Patch saved: {args.patch}")
    print(f"Change blocks: {len(patch['changes'])}")
    print(f"Changed bytes: {changed_bytes}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    count = apply_patch(Path(args.input), Path(args.patch), Path(args.output), args.force)
    print(f"Patch applied: {args.output}")
    print(f"Applied change blocks: {count}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ok = verify_files(Path(args.actual), Path(args.expected))
    if ok:
        print("OK: files are identical")
        return 0
    print("FAIL: files differ")
    return 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare and apply binary firmware patches")
    sub = parser.add_subparsers(dest="command", required=True)

    p_diff = sub.add_parser("diff", help="Create patch from original and modified binaries")
    p_diff.add_argument("original")
    p_diff.add_argument("modified")
    p_diff.add_argument("patch")
    p_diff.set_defaults(func=cmd_diff)

    p_apply = sub.add_parser("apply", help="Apply patch to another original binary")
    p_apply.add_argument("input")
    p_apply.add_argument("patch")
    p_apply.add_argument("output")
    p_apply.add_argument("--force", action="store_true", help="Apply even if old bytes do not match")
    p_apply.set_defaults(func=cmd_apply)

    p_verify = sub.add_parser("verify", help="Compare two files byte by byte")
    p_verify.add_argument("actual")
    p_verify.add_argument("expected")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
