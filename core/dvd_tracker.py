import os
import sys
import yaml
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional, Callable

# Jalali Month names in Persian
JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

# Jalali Weekday names in Persian
JALALI_WEEKDAYS = [
    "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"
]

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 335]
    
    g_leap = 1 if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0) else 0
    
    g_day_no = g_d_m[gm - 1] + gd
    if gm > 2 and g_leap:
        g_day_no += 1
        
    if g_day_no > 79:
        jy = gy - 621
        j_day_no = g_day_no - 79
    else:
        jy = gy - 622
        j_day_no = g_day_no + 286
        prev_g_leap = 1 if ((gy - 1) % 4 == 0 and (gy - 1) % 100 != 0) or ((gy - 1) % 400 == 0) else 0
        if prev_g_leap:
            j_day_no += 1
            
    if j_day_no <= 186:
        jm = (j_day_no - 1) // 31 + 1
        jd = (j_day_no - 1) % 31 + 1
    else:
        jm = (j_day_no - 187) // 30 + 7
        jd = (j_day_no - 187) % 30 + 1
        
    return jy, jm, jd

def get_jalali_date_str(dt: datetime) -> str:
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    wd = JALALI_WEEKDAYS[dt.weekday()]
    return f"{wd}، {jd} {JALALI_MONTHS[jm-1]} {jy}"

def get_jalali_folder_name(start_dt: datetime, end_dt: datetime) -> str:
    sy, sm, sd = gregorian_to_jalali(start_dt.year, start_dt.month, start_dt.day)
    ey, em, ed = gregorian_to_jalali(end_dt.year, end_dt.month, end_dt.day)
    return f"{sy:04d},{sm:02d},{sd:02d}-{ey:04d},{em:02d},{ed:02d}"

@dataclass
class DvdWeek:
    key: str
    start_date: datetime
    end_date: datetime
    from_jalali: str
    to_jalali: str
    from_gregorian: str
    to_gregorian: str
    written: bool = False
    sent: bool = False

@dataclass
class CopyProgress:
    current_file: str
    copied_files: int
    total_files: int
    copied_bytes: int
    total_bytes: int
    percentage: float

def get_dvd_tracker_path() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "dvd_tracker.yaml"

def load_dvd_tracker() -> Dict[str, Dict[str, bool]]:
    path = get_dvd_tracker_path()
    if not path.exists():
        save_dvd_tracker({})
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("weeks", {})
    except Exception:
        return {}

def save_dvd_tracker(weeks_data: Dict[str, Dict[str, bool]]):
    path = get_dvd_tracker_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump({"weeks": weeks_data}, f, allow_unicode=True, sort_keys=False)
    except Exception:
        pass

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    # Search Gregorian years around jy + 620 to jy + 623 to find the matching Gregorian date
    for gy in range(jy + 620, jy + 623):
        for gm in range(1, 13):
            for gd in range(1, 32):
                try:
                    dt = datetime(gy, gm, gd)
                    cal_jy, cal_jm, cal_jd = gregorian_to_jalali(gy, gm, gd)
                    if cal_jy == jy and cal_jm == jm and cal_jd == jd:
                        return gy, gm, gd
                except ValueError:
                    pass
    return jy + 621, 1, 1 # fallback

def generate_weekly_periods() -> List[DvdWeek]:
    today = datetime.now()
    tracker_data = load_dvd_tracker()
    
    start_anchor = None
    if tracker_data:
        oldest_greg_start = None
        for key in tracker_data.keys():
            try:
                # Key is "YYYY,MM,DD-YYYY,MM,DD"
                start_part = key.split("-")[0]
                jy, jm, jd = map(int, start_part.split(","))
                gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
                greg_dt = datetime(gy, gm, gd)
                if oldest_greg_start is None or greg_dt < oldest_greg_start:
                    oldest_greg_start = greg_dt
            except Exception:
                pass
        start_anchor = oldest_greg_start

    # Start from current week's Saturday if no tracked data yet
    if start_anchor is None:
        days_to_sub = (today.weekday() - 5) % 7
        start_anchor = today - timedelta(days=days_to_sub)
    periods: List[DvdWeek] = []
    current_start = start_anchor
    has_new_weeks = False
    
    while current_start <= today:
        current_end = current_start + timedelta(days=6) # Saturday to Friday
        
        from_jalali = get_jalali_date_str(current_start)
        to_jalali = get_jalali_date_str(current_end)
        
        from_greg = current_start.strftime("%Y-%m-%d")
        to_greg = current_end.strftime("%Y-%m-%d")
        
        key = get_jalali_folder_name(current_start, current_end)
        
        if key not in tracker_data:
            tracker_data[key] = {
                "written": False,
                "sent": False
            }
            has_new_weeks = True
            
        status = tracker_data[key]
        written = status.get("written", False)
        sent = status.get("sent", False)
        
        periods.append(DvdWeek(
            key=key,
            start_date=current_start,
            end_date=current_end,
            from_jalali=from_jalali,
            to_jalali=to_jalali,
            from_gregorian=from_greg,
            to_gregorian=to_greg,
            written=written,
            sent=sent
        ))
        
        current_start += timedelta(days=7) # Next week Saturday
        
    if has_new_weeks:
        save_dvd_tracker(tracker_data)
        
    return list(reversed(periods)) # Newest weeks on top

def copy_weekly_backups(
    source_dir: str,
    dest_dir_name: str,
    start_dt: datetime,
    progress_callback: Optional[Callable[[CopyProgress], None]] = None,
    cancel_requested: Optional[Callable[[], bool]] = None
) -> Tuple[bool, int, int, str]:
    # Saturday to Thursday range
    range_start = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0)
    thursday = start_dt + timedelta(days=5)
    range_end = datetime(thursday.year, thursday.month, thursday.day, 23, 59, 59)
    
    desktop_path = Path(os.path.expanduser("~")) / "Desktop"
    dest_path = desktop_path / dest_dir_name
    
    src_path = Path(source_dir)
    if not src_path.exists():
        return False, 0, 0, "پوشه مرجع بکاپ یافت نشد!"
        
    files_to_copy: List[Tuple[Path, Path, int]] = []
    total_bytes = 0
    
    try:
        for root, _, filenames in os.walk(src_path):
            for fn in filenames:
                fp = Path(root) / fn
                try:
                    stat = fp.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    if range_start <= mtime <= range_end:
                        rel_path = fp.relative_to(src_path)
                        files_to_copy.append((fp, dest_path / rel_path, stat.st_size))
                        total_bytes += stat.st_size
                except Exception:
                    pass
    except Exception as e:
        return False, 0, 0, f"خطا در اسکن فایل‌ها: {str(e)}"
        
    total_files = len(files_to_copy)
    if total_files == 0:
        return True, 0, 0, "هیچ فایلی برای کپی در این بازه تاریخی یافت نشد."
        
    copied_files = 0
    copied_bytes = 0
    
    for src_file, target_file, size in files_to_copy:
        if cancel_requested and cancel_requested():
            return False, copied_files, copied_bytes, "عملیات متوقف شد."
            
        try:
            os.makedirs(target_file.parent, exist_ok=True)
            shutil.copy2(src_file, target_file)
            copied_files += 1
            copied_bytes += size
            
            if progress_callback:
                pct = (copied_bytes / total_bytes * 100.0) if total_bytes > 0 else 100.0
                progress_callback(CopyProgress(
                    current_file=src_file.name,
                    copied_files=copied_files,
                    total_files=total_files,
                    copied_bytes=copied_bytes,
                    total_bytes=total_bytes,
                    percentage=round(pct, 1)
                ))
        except Exception:
            pass
            
    return True, copied_files, copied_bytes, ""
