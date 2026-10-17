import os
import sys
import re
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, List, Tuple


@dataclass
class OpticalDrive:
    path: str
    name: str


def find_optical_drives() -> List[OpticalDrive]:
    """Find available optical drives on Linux or Windows."""
    drives = []
    if sys.platform.startswith("linux"):
        # Check standard /dev/sr* and /dev/cdrom
        sr_paths = sorted(Path("/dev").glob("sr*"))
        for p in sr_paths:
            drives.append(OpticalDrive(path=str(p), name=f"Optical Drive ({p.name})"))
        if not drives and Path("/dev/cdrom").exists():
            drives.append(OpticalDrive(path="/dev/cdrom", name="Optical Drive (/dev/cdrom)"))
    elif sys.platform == "win32":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in "EFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & (1 << (ord(letter) - ord("A"))):
                drive_str = f"{letter}:\\"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_str)
                # DRIVE_CDROM is 5
                if drive_type == 5:
                    drives.append(OpticalDrive(path=f"{letter}:", name=f"CD/DVD Drive ({letter}:)"))
    return drives


def is_burning_tool_available() -> Tuple[bool, str]:
    """Check if burning tools are available on the host system."""
    if sys.platform.startswith("linux"):
        if shutil.which("growisofs"):
            return True, "growisofs"
        if shutil.which("xorriso"):
            return True, "xorriso"
        return False, "ابزار رایت (dvd+rw-tools یا growisofs) بر روی سیستم نصب نیست."
    elif sys.platform == "win32":
        return True, "windows"
    return False, "پلتفرم ناشناخته"


def eject_drive(drive_path: str):
    """Eject disc tray after burning."""
    try:
        if sys.platform.startswith("linux"):
            subprocess.run(["eject", drive_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            pass
    except Exception:
        pass


def burn_directory_to_dvd(
    source_dir: str,
    drive_path: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Tuple[bool, str]:
    """
    Burn a folder to DVD using growisofs on Linux.
    progress_callback receives (percentage: float, status_text: str)
    """
    src = Path(source_dir).resolve()
    if not src.exists():
        return False, f"مسیر منبع یافت نشد: {source_dir}"

    if not drive_path:
        drives = find_optical_drives()
        if not drives:
            return False, "هیچ درایو نوری شناسایی نشد. لطفاً درایو DVD را متصل کنید."
        drive_path = drives[0].path

    if sys.platform.startswith("linux"):
        growisofs_bin = shutil.which("growisofs")
        if not growisofs_bin:
            return False, "دستور growisofs یافت نشد. لطفاً با sudo pacman -S dvd+rw-tools آن را نصب کنید."

        # Command: growisofs -Z /dev/sr0 -R -J -udf /path/to/folder
        cmd = [growisofs_bin, "-Z", drive_path, "-R", "-J", "-udf", str(src)]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Match patterns like: 24.32% done, estimate finish ...
            pct_regex = re.compile(r"(\d+(?:\.\d+)?)%\s+done")
            last_pct = 0.0

            output_lines = []
            while True:
                if cancel_check and cancel_check():
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return False, "عملیات رایت توسط کاربر متوقف شد."

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    clean_line = line.strip()
                    output_lines.append(clean_line)
                    if len(output_lines) > 20:
                        output_lines.pop(0)

                    m = pct_regex.search(clean_line)
                    if m:
                        try:
                            last_pct = float(m.group(1))
                            if progress_callback:
                                progress_callback(last_pct, clean_line)
                        except ValueError:
                            pass
                    else:
                        if progress_callback and clean_line:
                            progress_callback(last_pct, clean_line)

            retcode = process.poll()
            if retcode == 0:
                eject_drive(drive_path)
                return True, "رایت دیسک با موفقیت به پایان رسید و دیسک خارج شد."
            else:
                last_err = "\n".join(output_lines[-5:]) if output_lines else "بدون پیام خطا"
                return False, f"فرآیند رایت با کد خطای {retcode} متوقف شد.\n\nجزئیات خطا:\n{last_err}"

        except Exception as e:
            return False, f"خطا در اجرای فرآیند رایت: {str(e)}"

    return False, "رایت مستقیم در حال حاضر روی این سیستم‌عامل پشتیبانی نمی‌شود."
