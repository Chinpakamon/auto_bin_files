# Firmware Patch Tool

Скрипт сравнивает два бинарных файла прошивки, сохраняет отличия в JSON-патч и применяет этот патч к другому оригинальному файлу по тем же адресам.

Формат патча: `offset` + `old` + `new`, где `old` и `new` записаны в hex.

## Требования

Python 3.8+ без внешних зависимостей.

## Команды

### 1. Создать патч

```bash
python firmware_patch_tool.py diff original.bin modified.bin patch.json
```

Результат: файл `patch.json` со списком изменений.

### 2. Применить патч к новому оригинальному файлу

```bash
python firmware_patch_tool.py apply new_original.bin patch.json result.bin
```

По умолчанию скрипт проверяет, что байты в `new_original.bin` на нужных адресах совпадают с `old` из патча. Если не совпадают, применение останавливается, чтобы не испортить файл.

Принудительное применение без проверки старых байтов:

```bash
python firmware_patch_tool.py apply new_original.bin patch.json result.bin --force
```

### 3. Проверить результат

```bash
python firmware_patch_tool.py verify result.bin output.bin
```

Если файлы совпадают, будет выведено:

```text
OK: files are identical
```
