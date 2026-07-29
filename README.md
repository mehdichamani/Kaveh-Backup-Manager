# Server Backup Manager

A Windows desktop application for managing automated file backups from network shares to local storage, with optional DVD archiving and retention policies.

## Features

- **GUI (PyQt6)** — visual interface with real-time progress bars and Persian (RTL) UI
- **Terminal UI (Rich)** — text-based interface for headless/scripted use
- **Robocopy integration** — reliable file copying with configurable flags per job
- **Jalali calendar** — DVD archive tracking using the Persian calendar
- **Retention policy** — optionally auto-delete files older than N days
- **Chunked copy** — progress callbacks during large file transfers

## Project Structure

```
backup_manager.py          # Entry point
core/
  config_loader.py         # YAML config parsing, BackupJob/AppConfig dataclasses
  copier.py                # File copy engine with progress callbacks
  dvd_tracker.py           # Jalali calendar & weekly archive tracking
  retention.py             # Delete files older than N days
ui/
  gui_main.py              # PyQt6 GUI (main window)
  terminal.py              # Rich-based terminal UI
assets/                    # Icons and Persian fonts
config.yaml                # Backup job definitions (edit this)
dvd_tracker.yaml           # DVD archive tracking state
```

## Requirements

- Windows (SMB auth, robocopy, PyInstaller)
- Python 3.10+

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Run the GUI
python backup_manager.py

# Or use the launcher
start.bat
```

## Configuration

Edit `config.yaml` to define your backup jobs:

```yaml
general:
  log_directory: /path/to/logs
  open_log_on_finish: false
  max_log_files_to_keep: 60

jobs:
  - id: my_backup
    name: My Backup Job
    enabled: true
    source: \\server\share\path
    destination: D:\Backups\my_backup
    username: ''
    password: ''
    warn_older_than_hours: 24
    robocopy_flags:
      - /xo
      - /s
      - /nfl
      - /np
      - /r:2
      - /w:5

retention:
  enabled: false
  delete_files_older_than_days: 90
```

## Building

```bat
build_exe.bat
```

Produces `dist\BackupManager.exe` (standalone, no Python required).

## License

MIT
