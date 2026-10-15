import os
import sys
import re
import time
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
from datetime import datetime
from .config_loader import BackupJob

@dataclass
class FileMeta:
    name: str
    path: Path
    relative_path: Path
    size_bytes: int
    mtime: datetime

@dataclass
class ProgressUpdate:
    job_id: str
    job_name: str
    current_file: str
    files_copied: int
    total_files_to_copy: int
    bytes_copied: int
    total_bytes_to_copy: int
    current_file_progress_pct: float
    total_progress_pct: float
    speed_mbps: float
    elapsed_seconds: float
    eta_seconds: float

@dataclass
class JobResult:
    job: BackupJob
    success: bool
    source_available: bool
    exit_code: int
    files_before: int
    files_after: int
    new_files_count: int
    copied_files: List[FileMeta] = field(default_factory=list)
    newest_file: Optional[FileMeta] = None
    warning_stale: bool = False
    stale_hours: float = 0.0
    error_message: str = ""

def parse_unc(unc_path: str) -> Optional[Tuple[str, str, str]]:
    """Extracts (host, share, subpath) from Windows UNC or smb:// URI."""
    clean = unc_path.replace("\\", "/").strip()
    if clean.startswith("smb://"):
        clean = clean[6:]
    elif clean.startswith("//"):
        clean = clean[2:]
    elif clean.startswith("/"):
        clean = clean[1:]
    else:
        return None

    parts = [p for p in clean.split("/") if p]
    if len(parts) >= 2:
        host, share = parts[0], parts[1]
        subpath = "/".join(parts[2:])
        return host, share, subpath
    return None

def resolve_path(path_str: str) -> Path:
    """
    Resolves local paths, Windows UNC paths, or SMB paths into an accessible Path.
    On Linux, resolves UNC shares mapped through GVFS (/run/user/<uid>/gvfs).
    """
    path_str = (path_str or "").strip()
    if not path_str:
        return Path(".")

    # On Windows or standard existing local path
    p = Path(path_str)
    if p.exists() or sys.platform == "win32":
        return p

    unc_info = parse_unc(path_str)
    if unc_info and sys.platform != "win32":
        host, share, subpath = unc_info
        gvfs_dir = Path(f"/run/user/{os.getuid()}/gvfs")
        if gvfs_dir.exists():
            # Check exact match candidates
            candidates = [
                f"smb-share:server={host},share={share.lower()}",
                f"smb-share:server={host},share={share}",
                f"smb-share:server={host.lower()},share={share.lower()}",
                f"smb-share:server={host.lower()},share={share}",
            ]
            for cand in candidates:
                cand_path = gvfs_dir / cand
                if cand_path.exists():
                    return cand_path / subpath if subpath else cand_path

            # Fuzzy search across active gvfs mounts
            try:
                for item in gvfs_dir.iterdir():
                    name_l = item.name.lower()
                    if f"server={host.lower()}" in name_l and f"share={share.lower()}" in name_l:
                        return item / subpath if subpath else item
            except OSError:
                pass

    return p

def connect_network_share(unc_path: str, username: Optional[str], password: Optional[str]) -> Tuple[bool, str]:
    if not unc_path:
        return True, ""

    if sys.platform == "win32":
        if not username or not password:
            return True, ""
        match = re.match(r"^\\\\([^\\]+)\\([^\\]+)", unc_path)
        if not match:
            return True, ""
        share_root = f"\\\\{match.group(1)}\\{match.group(2)}"
        try:
            # Establish connection with net use
            cmd = ["net", "use", share_root, password, f"/user:{username}", "/y"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode != 0:
                return False, f"خطای اتصال شبکه: {proc.stderr.strip()}"
            return True, ""
        except Exception as e:
            return False, f"خطای سیستمی اتصال شبکه: {str(e)}"

    # Linux SMB connection handling
    unc_info = parse_unc(unc_path)
    if not unc_info:
        return True, ""

    host, share, _ = unc_info
    resolved = resolve_path(unc_path)
    if resolved.exists():
        return True, ""

    # Attempt to mount via gio mount if available
    gio_bin = shutil.which("gio")
    if gio_bin:
        smb_uri = f"smb://{host}/{share}"
        try:
            # Check if mount stdin can provide credentials
            if username and password:
                # gio mount prompts for user/domain/password
                input_data = f"{username}\n\n{password}\n"
                proc = subprocess.run(
                    [gio_bin, "mount", smb_uri],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            else:
                proc = subprocess.run(
                    [gio_bin, "mount", "-a", smb_uri],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

            # Check if mounted now
            if resolve_path(unc_path).exists():
                return True, ""
            if proc.returncode != 0 and "already mounted" not in proc.stderr.lower():
                return False, f"خطای اتصال SMB (gio mount): {proc.stderr.strip() or proc.stdout.strip()}"
        except Exception as e:
            return False, f"خطای سیستمی مونت SMB: {str(e)}"

    return True, ""


def scan_directory_files(dir_path: Path, base_path: Optional[Path] = None) -> List[FileMeta]:
    files = []
    if not dir_path.exists():
        return files
    if base_path is None:
        base_path = dir_path

    try:
        for entry in os.scandir(dir_path):
            if entry.is_file(follow_symlinks=False):
                try:
                    stat = entry.stat()
                    fp = Path(entry.path)
                    rel_p = fp.relative_to(base_path)
                    files.append(FileMeta(
                        name=entry.name,
                        path=fp,
                        relative_path=rel_p,
                        size_bytes=stat.st_size,
                        mtime=datetime.fromtimestamp(stat.st_mtime)
                    ))
                except OSError:
                    pass
            elif entry.is_dir(follow_symlinks=False):
                files.extend(scan_directory_files(Path(entry.path), base_path))
    except Exception:
        pass
    return files

def run_backup_job_with_progress(
    job: BackupJob,
    log_dir: Path,
    progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
    cancel_requested: Optional[Callable[[], bool]] = None
) -> JobResult:
    # Attempt SMB Authentication if credentials exist
    auth_success, auth_err = connect_network_share(job.source, job.username, job.password)
    if not auth_success:
        return JobResult(
            job=job,
            success=False,
            source_available=False,
            exit_code=-2,
            files_before=0,
            files_after=0,
            new_files_count=0,
            error_message=auth_err
        )

    source_path = resolve_path(job.source)
    dest_path = resolve_path(job.destination)

    # Check source availability
    if not source_path.exists():
        return JobResult(
            job=job,
            success=False,
            source_available=False,
            exit_code=-1,
            files_before=0,
            files_after=0,
            new_files_count=0,
            error_message=f"مسیر سورس '{job.source}' در دسترس نیست!"
        )

    # Gather destination files before copy
    dest_files_before = scan_directory_files(dest_path)
    count_before = len(dest_files_before)
    dest_file_map = {f.relative_path: f for f in dest_files_before}

    # Scan source files
    source_files = scan_directory_files(source_path)

    # Filter files that need copying
    files_to_copy: List[FileMeta] = []
    total_bytes_to_copy = 0

    for sf in source_files:
        df = dest_file_map.get(sf.relative_path)
        if not df or sf.size_bytes != df.size_bytes or sf.mtime > df.mtime:
            files_to_copy.append(sf)
            total_bytes_to_copy += sf.size_bytes

    total_files_count = len(files_to_copy)
    bytes_copied_total = 0
    files_copied_count = 0

    start_time = time.time()
    last_speed_calc_time = start_time
    bytes_since_last_calc = 0
    current_speed_mbps = 0.0

    copied_file_metas: List[FileMeta] = []

    # Perform chunked file copying with progress calculation
    for sf in files_to_copy:
        if cancel_requested and cancel_requested():
            return JobResult(
                job=job,
                success=False,
                source_available=True,
                exit_code=99,
                files_before=count_before,
                files_after=count_before + files_copied_count,
                new_files_count=files_copied_count,
                copied_files=copied_file_metas,
                error_message="عملیات توسط کاربر متوقف شد."
            )

        target_file_path = dest_path / sf.relative_path
        os.makedirs(target_file_path.parent, exist_ok=True)

        # Copy in 1MB chunks
        chunk_size = 1024 * 1024
        file_bytes_copied = 0

        try:
            with open(sf.path, 'rb') as fsrc:
                with open(target_file_path, 'wb') as fdst:
                    while True:
                        if cancel_requested and cancel_requested():
                            break
                        chunk = fsrc.read(chunk_size)
                        if not chunk:
                            break
                        fdst.write(chunk)

                        chunk_len = len(chunk)
                        file_bytes_copied += chunk_len
                        bytes_copied_total += chunk_len
                        bytes_since_last_calc += chunk_len

                        now = time.time()
                        time_diff = now - last_speed_calc_time
                        if time_diff >= 0.5:
                            current_speed_mbps = (bytes_since_last_calc / (1024 * 1024)) / time_diff
                            last_speed_calc_time = now
                            bytes_since_last_calc = 0

                        elapsed = now - start_time
                        overall_pct = (bytes_copied_total / total_bytes_to_copy * 100.0) if total_bytes_to_copy > 0 else 100.0
                        file_pct = (file_bytes_copied / sf.size_bytes * 100.0) if sf.size_bytes > 0 else 100.0
                        eta = ((total_bytes_to_copy - bytes_copied_total) / (1024 * 1024 * current_speed_mbps)) if current_speed_mbps > 0 else 0.0

                        if progress_callback:
                            progress_callback(ProgressUpdate(
                                job_id=job.id,
                                job_name=job.name,
                                current_file=sf.name,
                                files_copied=files_copied_count,
                                total_files_to_copy=total_files_count,
                                bytes_copied=bytes_copied_total,
                                total_bytes_to_copy=total_bytes_to_copy,
                                current_file_progress_pct=round(file_pct, 1),
                                total_progress_pct=round(overall_pct, 1),
                                speed_mbps=round(current_speed_mbps, 2),
                                elapsed_seconds=round(elapsed, 1),
                                eta_seconds=round(eta, 1)
                            ))

            # Preserve timestamp
            try:
                os.utime(target_file_path, (sf.mtime.timestamp(), sf.mtime.timestamp()))
            except OSError:
                pass

            files_copied_count += 1
            copied_file_metas.append(sf)

        except Exception as e:
            pass

    # Gather destination files after copy
    dest_files_after = scan_directory_files(dest_path)
    count_after = len(dest_files_after)
    dest_files_sorted = sorted(dest_files_after, key=lambda x: x.mtime, reverse=True)
    newest_file = dest_files_sorted[0] if dest_files_sorted else None

    warning_stale = False
    stale_hours = 0.0
    if newest_file:
        now = datetime.now()
        stale_hours = round((now - newest_file.mtime).total_seconds() / 3600.0, 1)
        if stale_hours > job.warn_older_than_hours:
            warning_stale = True

    return JobResult(
        job=job,
        success=True,
        source_available=True,
        exit_code=0,
        files_before=count_before,
        files_after=count_after,
        new_files_count=files_copied_count,
        copied_files=copied_file_metas,
        newest_file=newest_file,
        warning_stale=warning_stale,
        stale_hours=stale_hours,
        error_message=""
    )
