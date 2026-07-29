import os
import sys
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class BackupJob:
    id: str
    name: str
    enabled: bool
    source: str
    destination: str
    username: str = ""
    password: str = ""
    warn_older_than_hours: int = 24
    robocopy_flags: List[str] = field(default_factory=lambda: ["/xo", "/s", "/nfl", "/np", "/r:2", "/w:5"])

@dataclass
class RetentionConfig:
    enabled: bool = False
    delete_files_older_than_days: int = 90

@dataclass
class AppConfig:
    log_directory: str
    open_log_on_finish: bool
    max_log_files_to_keep: int
    jobs: List[BackupJob]
    retention: RetentionConfig
    raw_config: Dict[str, Any]

def get_base_dir() -> Path:
    """Returns base executable directory or script directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def load_config(config_path: Optional[str] = None) -> AppConfig:
    if not config_path:
        base_dir = get_base_dir()
        config_path = base_dir / "config.yaml"
        if not config_path.exists() and (base_dir.parent / "config.yaml").exists():
            config_path = base_dir.parent / "config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        # Create empty config file with minimal structure
        data = {
            "general": {
                "log_directory": "",
                "open_log_on_finish": False,
                "max_log_files_to_keep": 60
            },
            "jobs": [],
            "retention": {
                "enabled": False,
                "delete_files_older_than_days": 90
            }
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        return AppConfig(
            log_directory="",
            open_log_on_finish=False,
            max_log_files_to_keep=60,
            jobs=[],
            retention=RetentionConfig(),
            raw_config=data
        )

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    general = data["general"]
    log_dir = general["log_directory"]
    open_log = general["open_log_on_finish"]
    max_logs = general["max_log_files_to_keep"]

    # Load jobs
    jobs_data = data["jobs"]
    jobs = []
    for j in jobs_data:
        jobs.append(BackupJob(
            id=j["id"],
            name=j.get("name", j["id"]),
            enabled=j.get("enabled", True),
            source=j["source"],
            destination=j["destination"],
            username=j.get("username", ""),
            password=j.get("password", ""),
            warn_older_than_hours=j.get("warn_older_than_hours", 24),
            robocopy_flags=j.get("robocopy_flags", ["/xo", "/s", "/nfl", "/np", "/r:2", "/w:5"])
        ))

    # Load retention
    ret_data = data["retention"]
    retention = RetentionConfig(
        enabled=ret_data["enabled"],
        delete_files_older_than_days=ret_data["delete_files_older_than_days"]
    )

    return AppConfig(
        log_directory=log_dir,
        open_log_on_finish=open_log,
        max_log_files_to_keep=max_logs,
        jobs=jobs,
        retention=retention,
        raw_config=data
    )

def save_config(app_config: AppConfig, config_path: Optional[str] = None) -> None:
    if not config_path:
        base_dir = get_base_dir()
        config_path = base_dir / "config.yaml"
        if not config_path.exists() and (base_dir.parent / "config.yaml").exists():
            config_path = base_dir.parent / "config.yaml"
    else:
        config_path = Path(config_path)

    # Reconstruct dictionary
    jobs_list = []
    for job in app_config.jobs:
        jobs_list.append({
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "source": job.source,
            "destination": job.destination,
            "username": job.username,
            "password": job.password,
            "warn_older_than_hours": job.warn_older_than_hours,
            "robocopy_flags": job.robocopy_flags
        })

    data = {
        "general": {
            "log_directory": app_config.log_directory,
            "open_log_on_finish": app_config.open_log_on_finish,
            "max_log_files_to_keep": app_config.max_log_files_to_keep
        },
        "jobs": jobs_list,
        "retention": {
            "enabled": app_config.retention.enabled,
            "delete_files_older_than_days": app_config.retention.delete_files_older_than_days
        }
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
