# AGENTS.md — Server Backup Manager

## Entry point & architecture

- `backup_manager.py` → `ui.gui_main.run_gui()` — the single entrypoint
- `core/` — config loading, file copy engine, retention, DVD/Jalali calendar tracker
- `ui/` — PyQt6 GUI (`gui_main.py`), Rich terminal UI (`terminal.py`)
- Windows-only: SMB auth via `net use`, chunked Python copy, `robocopy` flag conventions in config

## Key files

| File | Purpose |
|---|---|
| `config.yaml` | Backup job definitions (sources are UNC paths, destinations are local) |
| `dvd_tracker.yaml` | Weekly archive write/send status (Jalali/Persian calendar week keys) |
| `core/config_loader.py` | `load_config()`, `save_config()`, `BackupJob`, `AppConfig` dataclasses |
| `core/copier.py` | `run_backup_job_with_progress()` — chunked copy with progress callbacks |
| `core/dvd_tracker.py` | Jalali ↔ Gregorian date conversion, weekly period generation |
| `core/retention.py` | `run_retention_policy()` — deletes files older than N days |

## Dependencies

```
pip install pyyaml PyQt6 pyinstaller rich
```

`rich` is not in `requirements.txt` but is used by `ui/terminal.py`.

## Build

```bat
build_exe.bat
# or directly:
pyinstaller --noconsole --onefile --icon=assets/app_icon.ico --add-data "assets;assets" --name "BackupManager" backup_manager.py
```

Two `.spec` files produce `BackupManager.exe` and `DatabaseBackupManager.exe` from the same source.

## Config & data files are discovered relative to the executable

- `config.yaml` — expected next to the EXE (or in parent directory as fallback)
- `dvd_tracker.yaml` — next to the EXE
- `assets/` — bundled inside the EXE via `--add-data`

## Running without building

```bat
start.bat
# or manually:
python backup_manager.py
```

Python 3.14 is in `C:\Users\Mehdi\AppData\Local\Programs\Python\Python314\python.exe`.

## Persian localization

- UI layout is `RightToLeft` throughout
- Custom fonts in `assets/`: `Vazirmatn-Regular.ttf`, `Vazirmatn-Bold.ttf`
- `dvd_tracker.py` uses a built-in Jalali calendar implementation (no external Persian date library)
- All user-facing strings are in Persian

## No tests, no CI, no linting config

Add these if introduced. The repo currently has no formatter, type checker, or test runner configured.

## No remote

Local-only repo. No CI workflows, no `.github/`, no pre-commit hooks.
