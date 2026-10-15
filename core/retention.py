import os
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class CleanupResult:
    files_removed: int
    bytes_freed: int
    errors: List[str]

def run_retention_policy(target_dir: str, max_age_days: int) -> CleanupResult:
    from .copier import resolve_path
    dir_path = resolve_path(target_dir)
    if not dir_path.exists() or max_age_days <= 0:
        return CleanupResult(files_removed=0, bytes_freed=0, errors=[])

    now = time.time()
    cutoff = now - (max_age_days * 86400)
    removed_count = 0
    freed_bytes = 0
    errors = []

    try:
        for root, _, files in os.walk(dir_path):
            for fn in files:
                fp = Path(root) / fn
                try:
                    stat = fp.stat()
                    if stat.st_mtime < cutoff:
                        size = stat.st_size
                        fp.unlink()
                        removed_count += 1
                        freed_bytes += size
                except Exception as e:
                    errors.append(f"Failed to delete {fp}: {str(e)}")
    except Exception as e:
        errors.append(f"Retention error walking directory {target_dir}: {str(e)}")

    return CleanupResult(files_removed=removed_count, bytes_freed=freed_bytes, errors=errors)
