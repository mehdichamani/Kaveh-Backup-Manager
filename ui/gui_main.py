import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QFrame, QMessageBox, QDialog, QListWidget,
    QLineEdit, QCheckBox, QFormLayout, QGroupBox, QSpinBox, QTabWidget,
    QTabBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QFontDatabase

from core.config_loader import load_config, save_config, AppConfig, BackupJob, RetentionConfig
from core.copier import run_backup_job_with_progress, JobResult, ProgressUpdate
from core.retention import run_retention_policy
from core.dvd_tracker import (
    generate_weekly_periods, DvdWeek, CopyProgress, copy_weekly_backups,
    save_dvd_tracker, load_dvd_tracker
)

def get_asset_path(filename: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS) / "assets"
    else:
        base = Path(__file__).resolve().parent.parent / "assets"
    return str(base / filename)

STYLESHEET = """
QMainWindow, QDialog {
    background-color: #181825;
}
QWidget {
    font-family: 'Vazirmatn', 'Segoe UI', sans-serif;
    color: #cdd6f4;
    font-size: 13px;
}
QFrame.Card {
    background-color: #1e1e2e;
    border-radius: 12px;
    border: 1px solid #313244;
}
QLabel.Title {
    font-size: 19px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel.Subtitle {
    color: #a6adc8;
    font-size: 12px;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: bold;
    color: #cdd6f4;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton#PrimaryBtn {
    background-color: #a6e3a1;
    color: #11111b;
    border: none;
}
QPushButton#PrimaryBtn:hover {
    background-color: #94e2d5;
}
QPushButton#StopBtn {
    background-color: #f38ba8;
    color: #11111b;
    border: none;
}
QPushButton#StopBtn:hover {
    background-color: #eba0ac;
}
QProgressBar {
    border: 1px solid #45475a;
    border-radius: 8px;
    text-align: center;
    background-color: #11111b;
    color: #cdd6f4;
    font-weight: bold;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 7px;
}
QTableWidget {
    background-color: #1e1e2e;
    gridline-color: #45475a;
    border: 1px solid #313244;
    border-radius: 10px;
    selection-background-color: #313244;
    font-size: 13px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
    border: 1px solid #45475a;
    padding: 8px;
}
QHeaderView::section:hover {
    background-color: #45475a;
}
QTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 10px;
    color: #a6adc8;
    font-family: 'Consolas', 'Vazirmatn', monospace;
    font-size: 12px;
}
QLineEdit, QListWidget {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    color: #cdd6f4;
}
QSpinBox {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    padding-left: 28px; /* Give room for up/down buttons on the left in RTL */
    color: #cdd6f4;
}
QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #89b4fa;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}
QTabWidget::panel {
    border: 1px solid #313244;
    border-radius: 10px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #11111b;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    color: #a6adc8;
}
QTabBar::tab:selected, QTabBar::tab:hover {
    background-color: #1e1e2e;
    color: #89b4fa;
}
"""

class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنظیمات سیستم پشتیبان‌گیری")
        self.resize(750, 520)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.config = config
        self.jobs = list(config.jobs)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Right side: Jobs list
        right_vbox = QVBoxLayout()
        right_vbox.addWidget(QLabel("📋 لیست کارها:"))
        self.jobs_list_widget = QListWidget()
        self.jobs_list_widget.currentRowChanged.connect(self.load_job_details)
        right_vbox.addWidget(self.jobs_list_widget)

        list_btns_hbox = QHBoxLayout()
        self.add_job_btn = QPushButton("➕ کار جدید")
        self.add_job_btn.clicked.connect(self.add_new_job)
        self.del_job_btn = QPushButton("❌ حذف کار")
        self.del_job_btn.clicked.connect(self.delete_job)
        list_btns_hbox.addWidget(self.add_job_btn)
        list_btns_hbox.addWidget(self.del_job_btn)
        right_vbox.addLayout(list_btns_hbox)

        main_layout.addLayout(right_vbox, stretch=1)

        # Left side: Job details & General settings
        left_vbox = QVBoxLayout()

        # Job Details Group
        self.job_group = QGroupBox("تنظیمات کار انتخاب شده")
        form_layout = QFormLayout(self.job_group)

        self.name_input = QLineEdit()
        self.source_input = QLineEdit()
        self.dest_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.warn_spin = QSpinBox()
        self.warn_spin.setRange(1, 168)
        self.warn_spin.setValue(24)
        self.warn_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enabled_chk = QCheckBox("کار فعال باشد")

        form_layout.addRow("نام کار:", self.name_input)
        form_layout.addRow("مسیر منبع (سورس):", self.source_input)
        form_layout.addRow("مسیر مقصد:", self.dest_input)
        form_layout.addRow("نام کاربری شبکه:", self.username_input)
        form_layout.addRow("رمز عبور شبکه:", self.password_input)
        form_layout.addRow("آستانه هشدار (ساعت):", self.warn_spin)
        form_layout.addRow("", self.enabled_chk)

        # Save active field edits back to memory on any change
        self.name_input.textChanged.connect(self.save_current_job_fields)
        self.source_input.textChanged.connect(self.save_current_job_fields)
        self.dest_input.textChanged.connect(self.save_current_job_fields)
        self.username_input.textChanged.connect(self.save_current_job_fields)
        self.password_input.textChanged.connect(self.save_current_job_fields)
        self.warn_spin.valueChanged.connect(self.save_current_job_fields)
        self.enabled_chk.stateChanged.connect(self.save_current_job_fields)

        left_vbox.addWidget(self.job_group)

        # General / Retention settings group
        general_group = QGroupBox("تنظیمات عمومی")
        gen_form = QFormLayout(general_group)
        self.log_dir_input = QLineEdit(self.config.log_directory)
        self.ret_chk = QCheckBox("حذف بکاپ‌های قدیمی فعال باشد")
        self.ret_chk.setChecked(self.config.retention.enabled)
        self.ret_days_spin = QSpinBox()
        self.ret_days_spin.setRange(1, 365)
        self.ret_days_spin.setValue(self.config.retention.delete_files_older_than_days)
        self.ret_days_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)

        gen_form.addRow("پوشه ذخیره لاگ:", self.log_dir_input)
        gen_form.addRow(self.ret_chk)
        gen_form.addRow("مدت نگهداری (روز):", self.ret_days_spin)
        left_vbox.addWidget(general_group)

        # Save/Cancel buttons
        save_hbox = QHBoxLayout()
        self.save_all_btn = QPushButton("💾 ذخیره نهایی تنظیمات")
        self.save_all_btn.setObjectName("PrimaryBtn")
        self.save_all_btn.clicked.connect(self.save_all_settings)
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.clicked.connect(self.reject)

        save_hbox.addStretch()
        save_hbox.addWidget(self.save_all_btn)
        save_hbox.addWidget(self.cancel_btn)
        left_vbox.addLayout(save_hbox)

        main_layout.addLayout(left_vbox, stretch=2)

        self.refresh_list()
        if self.jobs:
            self.jobs_list_widget.setCurrentRow(0)

    def refresh_list(self):
        self.jobs_list_widget.clear()
        for j in self.jobs:
            self.jobs_list_widget.addItem(j.name)

    def load_job_details(self, row: int):
        if row < 0 or row >= len(self.jobs):
            self.job_group.setEnabled(False)
            return

        self.job_group.setEnabled(True)
        job = self.jobs[row]

        # Temporarily block signals to prevent self-triggering updates
        self.name_input.blockSignals(True)
        self.source_input.blockSignals(True)
        self.dest_input.blockSignals(True)
        self.username_input.blockSignals(True)
        self.password_input.blockSignals(True)
        self.warn_spin.blockSignals(True)
        self.enabled_chk.blockSignals(True)

        self.name_input.setText(job.name)
        self.source_input.setText(job.source)
        self.dest_input.setText(job.destination)
        self.username_input.setText(job.username)
        self.password_input.setText(job.password)
        self.warn_spin.setValue(job.warn_older_than_hours)
        self.enabled_chk.setChecked(job.enabled)

        self.name_input.blockSignals(False)
        self.source_input.blockSignals(False)
        self.dest_input.blockSignals(False)
        self.username_input.blockSignals(False)
        self.password_input.blockSignals(False)
        self.warn_spin.blockSignals(False)
        self.enabled_chk.blockSignals(False)

    def save_current_job_fields(self):
        row = self.jobs_list_widget.currentRow()
        if row < 0 or row >= len(self.jobs):
            return
        job = self.jobs[row]
        job.name = self.name_input.text()
        job.source = self.source_input.text()
        job.destination = self.dest_input.text()
        job.username = self.username_input.text()
        job.password = self.password_input.text()
        job.warn_older_than_hours = self.warn_spin.value()
        job.enabled = self.enabled_chk.isChecked()

        self.jobs_list_widget.item(row).setText(job.name)

    def add_new_job(self):
        new_id = f"job_{int(datetime.now().timestamp())}"
        new_job = BackupJob(
            id=new_id,
            name="کار جدید",
            enabled=True,
            source="",
            destination="",
            username="",
            password=""
        )
        self.jobs.append(new_job)
        self.refresh_list()
        self.jobs_list_widget.setCurrentRow(len(self.jobs) - 1)
        self.name_input.setFocus()

    def delete_job(self):
        row = self.jobs_list_widget.currentRow()
        if row < 0 or row >= len(self.jobs):
            return
        del self.jobs[row]
        self.refresh_list()
        if self.jobs:
            self.jobs_list_widget.setCurrentRow(max(0, row - 1))

    def save_all_settings(self):
        self.config.log_directory = self.log_dir_input.text()
        self.config.retention = RetentionConfig(
            enabled=self.ret_chk.isChecked(),
            delete_files_older_than_days=self.ret_days_spin.value()
        )
        self.config.jobs = self.jobs

        try:
            save_config(self.config)
            QMessageBox.information(self, "موفق", "تنظیمات با موفقیت ذخیره گردید.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ذخیره‌سازی تنظیمات:\n{e}")


class BackupWorkerThread(QThread):
    progress_signal = pyqtSignal(ProgressUpdate)
    job_finished_signal = pyqtSignal(JobResult)
    log_signal = pyqtSignal(str)
    all_finished_signal = pyqtSignal(list)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        results: List[JobResult] = []
        now_str = datetime.now().strftime("%Y-%m-%d_%H%M")
        log_dir = Path(self.config.log_directory)
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = Path("./logs")
            os.makedirs(log_dir, exist_ok=True)

        log_file = log_dir / f"backup_log_{now_str}.txt"
        log_lines = [f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] شروع عملیات پشتیبان‌گیری"]

        for job in self.config.jobs:
            if not job.enabled or self._is_cancelled:
                continue

            self.log_signal.emit(f"🔍 شروع بررسی سرور {job.name}...")

            def on_progress(p: ProgressUpdate):
                self.progress_signal.emit(p)

            def is_cancel():
                return self._is_cancelled

            res = run_backup_job_with_progress(job, log_dir, on_progress, is_cancel)
            results.append(res)
            self.job_finished_signal.emit(res)

            status_str = "موفق" if res.success else "خطا"
            msg = f"پایان سرور {job.name}: وضعیت={status_str}، جدید={res.new_files_count}، مجموع={res.files_after}"
            self.log_signal.emit(f"  • {msg}")
            log_lines.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

            if res.warning_stale:
                warn_msg = f"  !! هشدار: آخرین بکاپ سرور {job.name} مربوط به {res.stale_hours} ساعت پیش است !!"
                self.log_signal.emit(warn_msg)
                log_lines.append(warn_msg)

        # Retention
        if self.config.retention.enabled and not self._is_cancelled:
            self.log_signal.emit("🧹 اجرای فرآیند پاکسازی فایل‌های قدیمی...")
            for job in self.config.jobs:
                if job.enabled:
                    clean_res = run_retention_policy(job.destination, self.config.retention.delete_files_older_than_days)
                    if clean_res.files_removed > 0:
                        ret_msg = f"  • {job.name}: تعداد {clean_res.files_removed} فایل قدیمی حذف شد."
                        self.log_signal.emit(ret_msg)

        # Save log
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines) + "\n")
        except Exception:
            pass

        self.all_finished_signal.emit(results)


class DvdCopyWorkerThread(QThread):
    progress_signal = pyqtSignal(CopyProgress)
    finished_signal = pyqtSignal(bool, int, int, str)

    def __init__(self, source_dir: str, folder_name: str, start_dt: datetime, parent=None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.folder_name = folder_name
        self.start_dt = start_dt
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        def on_progress(p: CopyProgress):
            self.progress_signal.emit(p)
        def is_cancel():
            return self._is_cancelled

        success, files, bytes_copied, err = copy_weekly_backups(
            source_dir=self.source_dir,
            dest_dir_name=self.folder_name,
            start_dt=self.start_dt,
            progress_callback=on_progress,
            cancel_requested=is_cancel
        )
        self.finished_signal.emit(success, files, bytes_copied, err)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("درباره برنامه")
        self.resize(420, 280)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # App logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = get_asset_path("app_icon.png")
        if os.path.exists(icon_path):
            logo_label.setPixmap(QIcon(icon_path).pixmap(QSize(64, 64)))
        layout.addWidget(logo_label)

        # App Name & version
        app_title = QLabel("KavehGlass Industries Backup App")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(app_title)

        version_lbl = QLabel("نسخه ۲.۶ (نگارش گرافیکی پایتون)")
        version_lbl.setStyleSheet("color: #a6adc8;")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_lbl)

        desc_lbl = QLabel("این برنامه به کوشش تیم آی تی اروم شیشه ساچی در جهت تسریع عملیات بک آپ، حفظ نهایت دقت و جلوگیری از خطاهای انسانی طراحی شده است.")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        layout.addWidget(desc_lbl)

        line = QFrame()
        line.setMinimumHeight(1)
        line.setMaximumHeight(1)
        line.setStyleSheet("background-color: #313244;")
        layout.addWidget(line)

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("سیستم مدیریت و پشتیبان‌گیری دیتابیس")
        self.resize(1050, 750)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        icon_path = get_asset_path("app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.worker: Optional[BackupWorkerThread] = None
        self.dvd_worker: Optional[DvdCopyWorkerThread] = None

        try:
            self.config = load_config()
        except Exception as e:
            QMessageBox.critical(self, "خطا در تنظیمات", f"خطا در بارگذاری config.yaml:\n{e}")
            sys.exit(1)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Tab Widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Build Tabs
        self.setup_backup_tab()
        self.setup_dvd_tab()

        # Footer copyright label
        footer_lbl = QLabel("© ۱۴۰۵ تمامی حقوق محفوظ است. توسعه‌یافته جهت مدیریت پشتیبان‌گیری سرورها")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_lbl.setStyleSheet("color: #585b70; font-size: 11px; margin-top: 4px;")
        main_layout.addWidget(footer_lbl)

    def setup_backup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Card
        header_card = QFrame()
        header_card.setProperty("class", "Card")
        header_layout = QHBoxLayout(header_card)

        title_vbox = QVBoxLayout()
        title_label = QLabel("🚀 سیستم پشتیبان‌گیری سرورها")
        title_label.setProperty("class", "Title")
        subtitle_label = QLabel(f"تاریخ لود تنظیمات: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        subtitle_label.setProperty("class", "Subtitle")
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(subtitle_label)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        # Unified Action Button (Start / Stop)
        self.action_btn = QPushButton("▶ شروع پشتیبان‌گیری")
        self.action_btn.setObjectName("PrimaryBtn")
        self.action_btn.setMinimumHeight(42)
        self.action_btn.clicked.connect(self.toggle_backup_action)

        self.config_btn = QPushButton("⚙️ مدیریت تنظیمات و کارها")
        self.config_btn.setMinimumHeight(42)
        self.config_btn.clicked.connect(self.open_settings_dialog)

        self.about_btn = QPushButton("ℹ️ درباره ما")
        self.about_btn.setMinimumHeight(42)
        self.about_btn.clicked.connect(self.open_about_dialog)

        header_layout.addWidget(self.action_btn)
        header_layout.addWidget(self.config_btn)
        header_layout.addWidget(self.about_btn)

        layout.addWidget(header_card)

        # Live Progress Card
        progress_card = QFrame()
        progress_card.setProperty("class", "Card")
        prog_vbox = QVBoxLayout(progress_card)

        self.status_info_label = QLabel("آماده به کار")
        self.status_info_label.setStyleSheet("font-weight: bold; color: #74c7ec; font-size: 14px;")

        # Speed and metrics labels
        metrics_hbox = QHBoxLayout()
        self.speed_label = QLabel("⚡ سرعت: 0.0 MB/s")
        self.copied_bytes_label = QLabel("📦 حجم کپی شده: 0 MB / 0 MB")
        self.eta_label = QLabel("⏱️ زمان باقیمانده: --")

        metrics_hbox.addWidget(self.speed_label)
        metrics_hbox.addWidget(self.copied_bytes_label)
        metrics_hbox.addWidget(self.eta_label)
        metrics_hbox.addStretch()

        prog_vbox.addWidget(self.status_info_label)
        prog_vbox.addLayout(metrics_hbox)

        self.job_progress_bar = QProgressBar()
        self.job_progress_bar.setFormat("پیشرفت کپی: %p%")
        prog_vbox.addWidget(self.job_progress_bar)

        layout.addWidget(progress_card)

        # Status Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "نام سرور", "وضعیت", "فایل جدید", "کل فایل‌ها", "آخرین بکاپ", "توضیحات / مسیر شبکه"
        ])
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h_header.setStretchLastSection(True)
        h_header.setHighlightSections(True)

        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 120)

        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)

        self.populate_initial_table()
        layout.addWidget(self.table)

        # Live Log View
        log_label = QLabel("📋 لاگ زنده سیستم:")
        log_label.setStyleSheet("font-weight: bold; color: #a6adc8;")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(110)
        layout.addWidget(self.log_text)

        self.tab_widget.addTab(tab, "⚙️ پشتیبان‌گیری سرورها")

    def setup_dvd_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Info Card
        header_card = QFrame()
        header_card.setProperty("class", "Card")
        header_layout = QHBoxLayout(header_card)
        
        info_vbox = QVBoxLayout()
        title = QLabel("💿 بایگانی هفتگی و رایت DVD")
        title.setProperty("class", "Title")
        desc = QLabel("عملیات رایت شنبه‌ها انجام می‌شود. فایل‌های کپی شده از شنبه تا پنج‌شنبه هفته قبل روی دسکتاپ آماده رایت می‌گردند.")
        desc.setProperty("class", "Subtitle")
        info_vbox.addWidget(title)
        info_vbox.addWidget(desc)
        header_layout.addLayout(info_vbox)
        layout.addWidget(header_card)

        # Live Progress panel for DVD Copying
        self.dvd_progress_card = QFrame()
        self.dvd_progress_card.setProperty("class", "Card")
        self.dvd_progress_card.setVisible(False)
        dvd_prog_layout = QVBoxLayout(self.dvd_progress_card)

        self.dvd_status_label = QLabel("آماده کپی...")
        self.dvd_status_label.setStyleSheet("font-weight: bold; color: #f9e2af;")
        self.dvd_progress_bar = QProgressBar()
        self.dvd_progress_bar.setFormat("پیشرفت کپی فایل‌ها: %p%")
        
        self.dvd_cancel_btn = QPushButton("انصراف از کپی")
        self.dvd_cancel_btn.setObjectName("StopBtn")
        self.dvd_cancel_btn.clicked.connect(self.cancel_dvd_copy)

        dvd_hbox = QHBoxLayout()
        dvd_hbox.addWidget(self.dvd_status_label)
        dvd_hbox.addStretch()
        dvd_hbox.addWidget(self.dvd_cancel_btn)

        dvd_prog_layout.addLayout(dvd_hbox)
        dvd_prog_layout.addWidget(self.dvd_progress_bar)
        layout.addWidget(self.dvd_progress_card)

        # Table for DVD weeks
        self.dvd_table = QTableWidget()
        self.dvd_table.setColumnCount(5)
        self.dvd_table.setHorizontalHeaderLabels([
            "رایت شده", "ارسال شده", "شروع هفته (شنبه)", "پایان هفته (جمعه)", "عملیات"
        ])
        
        dh = self.dvd_table.horizontalHeader()
        dh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        dh.setStretchLastSection(True)

        self.dvd_table.setColumnWidth(0, 90)
        self.dvd_table.setColumnWidth(1, 90)
        self.dvd_table.setColumnWidth(2, 270)
        self.dvd_table.setColumnWidth(3, 270)

        self.dvd_table.setShowGrid(True)
        self.dvd_table.setAlternatingRowColors(True)

        # Populate table
        self.refresh_dvd_table()
        
        # Connect itemChanged to save checkmark status changes
        self.dvd_table.itemChanged.connect(self.on_dvd_table_item_changed)

        layout.addWidget(self.dvd_table)
        self.tab_widget.addTab(tab, "💿 آرشیو و رایت DVD")

    def refresh_dvd_table(self):
        # Temporarily block itemChanged signals to prevent loop during population
        self.dvd_table.blockSignals(True)
        
        self.dvd_weeks = generate_weekly_periods()
        self.dvd_table.setRowCount(len(self.dvd_weeks))

        for row, week in enumerate(self.dvd_weeks):
            # Checkbox: Written
            write_item = QTableWidgetItem()
            write_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            write_item.setCheckState(Qt.CheckState.Checked if week.written else Qt.CheckState.Unchecked)
            write_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dvd_table.setItem(row, 0, write_item)

            # Checkbox: Sent
            send_item = QTableWidgetItem()
            send_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            send_item.setCheckState(Qt.CheckState.Checked if week.sent else Qt.CheckState.Unchecked)
            send_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dvd_table.setItem(row, 1, send_item)

            # Week details
            self.dvd_table.setItem(row, 2, QTableWidgetItem(week.from_jalali))
            self.dvd_table.setItem(row, 3, QTableWidgetItem(week.to_jalali))

            # Action button
            copy_btn = QPushButton("📂 آماده‌سازی پوشه")
            copy_btn.setStyleSheet("margin: 2px; padding: 4px; font-size: 12px; font-weight: bold;")
            copy_btn.setMinimumHeight(28)
            copy_btn.clicked.connect(lambda checked, w=week: self.start_dvd_copy(w))
            self.dvd_table.setCellWidget(row, 4, copy_btn)

        self.dvd_table.blockSignals(False)

    def on_dvd_table_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self.dvd_weeks):
            return
            
        week = self.dvd_weeks[row]
        checked = (item.checkState() == Qt.CheckState.Checked)

        if col == 0:
            week.written = checked
        elif col == 1:
            week.sent = checked

        # Save back to dvd_tracker.yaml
        tracker_data = {}
        for w in self.dvd_weeks:
            tracker_data[w.key] = {
                "written": w.written,
                "sent": w.sent
            }
        save_dvd_tracker(tracker_data)

    def start_dvd_copy(self, week: DvdWeek):
        if self.dvd_worker and self.dvd_worker.isRunning():
            QMessageBox.warning(self, "خطا", "یک عملیات کپی آرشیو دیگر در حال اجراست.")
            return

        self.dvd_progress_card.setVisible(True)
        self.dvd_progress_bar.setValue(0)
        self.dvd_status_label.setText(f"در حال آماده‌سازی فایل‌های هفته: {week.key}")
        self.tab_widget.setEnabled(False)

        # Source is config.log_directory (Y:\\DatabaseBackup\\Database)
        self.dvd_worker = DvdCopyWorkerThread(
            source_dir=self.config.log_directory,
            folder_name=week.key,
            start_dt=week.start_date
        )
        self.dvd_worker.progress_signal.connect(self.on_dvd_copy_progress)
        self.dvd_worker.finished_signal.connect(self.on_dvd_copy_finished)
        self.dvd_worker.start()

    def cancel_dvd_copy(self):
        if self.dvd_worker and self.dvd_worker.isRunning():
            self.dvd_worker.cancel()
            self.dvd_status_label.setText("در حال متوقف کردن عملیات...")

    def on_dvd_copy_progress(self, p: CopyProgress):
        self.dvd_status_label.setText(f"در حال کپی فایل: {p.current_file} ({p.copied_files}/{p.total_files})")
        self.dvd_progress_bar.setValue(int(p.percentage))

    def on_dvd_copy_finished(self, success: bool, files: int, bytes_copied: int, err: str):
        self.tab_widget.setEnabled(True)
        self.dvd_progress_card.setVisible(False)
        
        if success:
            mb = round(bytes_copied / (1024 * 1024), 1)
            QMessageBox.information(
                self, "موفقیت", 
                f"فایل‌های این هفته با موفقیت کپی شدند!\nتعداد کل فایل‌ها: {files} عدد\nحجم کل: {mb} مگابایت\nمسیر ذخیره‌سازی: روی دسکتاپ"
            )
        else:
            QMessageBox.critical(self, "خطا", f"عملیات کپی آرشیو با خطا مواجه شد:\n{err}")

    def populate_initial_table(self):
        self.table.setRowCount(len(self.config.jobs))
        for idx, job in enumerate(self.config.jobs):
            self.table.setItem(idx, 0, QTableWidgetItem(job.name))
            self.table.setItem(idx, 1, QTableWidgetItem("در انتظار"))
            self.table.setItem(idx, 2, QTableWidgetItem("-"))
            self.table.setItem(idx, 3, QTableWidgetItem("-"))
            self.table.setItem(idx, 4, QTableWidgetItem("-"))
            self.table.setItem(idx, 5, QTableWidgetItem(f"سورس: {job.source}"))

    def toggle_backup_action(self):
        if self.worker and self.worker.isRunning():
            self.stop_backup()
        else:
            self.start_backup()

    def start_backup(self):
        self.action_btn.setText("⏹ توقف فرآیند")
        self.action_btn.setObjectName("StopBtn")
        self.action_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        self.config_btn.setEnabled(False)
        self.log_text.clear()
        self.log("🚀 شروع فرآیند پشتیبان‌گیری...")

        self.worker = BackupWorkerThread(self.config)
        self.worker.progress_signal.connect(self.on_progress_update)
        self.worker.job_finished_signal.connect(self.on_job_finished)
        self.worker.log_signal.connect(self.log)
        self.worker.all_finished_signal.connect(self.on_all_finished)
        self.worker.start()

    def stop_backup(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log("🛑 انصراف توسط کاربر ارسال شد...")
            self.action_btn.setEnabled(False)

    def on_progress_update(self, p: ProgressUpdate):
        self.status_info_label.setText(f"در حال کپی سرور: {p.job_name} | فایل: {p.current_file}")
        self.job_progress_bar.setValue(int(p.total_progress_pct))

        speed_mb = p.speed_mbps
        copied_mb = round(p.bytes_copied / (1024 * 1024), 1)
        total_mb = round(p.total_bytes_to_copy / (1024 * 1024), 1)

        self.speed_label.setText(f"⚡ سرعت: {speed_mb:.1f} MB/s")
        self.copied_bytes_label.setText(f"📦 حجم: {copied_mb} MB / {total_mb} MB ({p.files_copied}/{p.total_files_to_copy} فایل)")
        self.eta_label.setText(f"⏱️ تخمین زمان باقی‌مانده: {p.eta_seconds:.0f} ثانیه")

    def on_job_finished(self, r: JobResult):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == r.job.name:
                if not r.source_available:
                    status_item = QTableWidgetItem("عدم دسترسی")
                    status_item.setForeground(QColor("#f38ba8"))
                    msg_item = QTableWidgetItem(f"خطا: {r.error_message}")
                elif not r.success:
                    status_item = QTableWidgetItem("خطا در کپی")
                    status_item.setForeground(QColor("#f38ba8"))
                    msg_item = QTableWidgetItem(f"کد خطا: {r.exit_code}")
                elif r.warning_stale:
                    status_item = QTableWidgetItem("هشدار مانیتورینگ")
                    status_item.setForeground(QColor("#f9e2af"))
                    msg_item = QTableWidgetItem(f"!! آخرین بکاپ {r.stale_hours} ساعت پیش انجام شده !!")
                else:
                    status_item = QTableWidgetItem("موفق")
                    status_item.setForeground(QColor("#a6e3a1"))
                    msg_item = QTableWidgetItem("کپی با موفقیت انجام شد")

                self.table.setItem(row, 1, status_item)
                self.table.setItem(row, 2, QTableWidgetItem(str(r.new_files_count)))
                self.table.setItem(row, 3, QTableWidgetItem(str(r.files_after)))
                self.table.setItem(row, 4, QTableWidgetItem(f"{r.stale_hours} ساعت پیش" if r.newest_file else "-"))
                self.table.setItem(row, 5, msg_item)

    def on_all_finished(self, results: List[JobResult]):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("▶ شروع پشتیبان‌گیری")
        self.action_btn.setObjectName("PrimaryBtn")
        self.action_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b;")
        self.config_btn.setEnabled(True)
        self.status_info_label.setText("✅ اتمام فرآیند پشتیبان‌گیری")
        self.job_progress_bar.setValue(100)
        self.log("✅ تمامی مراحل پشتیبان‌گیری اتمام یافت.")

    def log(self, text: str):
        self.log_text.append(text)

    def open_settings_dialog(self):
        diag = SettingsDialog(self.config, self)
        if diag.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.table.setRowCount(0)
            self.populate_initial_table()

    def open_about_dialog(self):
        diag = AboutDialog(self)
        diag.exec()


def run_gui():
    app = QApplication(sys.argv)

    font_reg = get_asset_path("Vazirmatn-Regular.ttf")
    font_bold = get_asset_path("Vazirmatn-Bold.ttf")

    if os.path.exists(font_reg):
        QFontDatabase.addApplicationFont(font_reg)
    if os.path.exists(font_bold):
        QFontDatabase.addApplicationFont(font_bold)

    app.setFont(QFont("Vazirmatn", 10))
    app.setStyleSheet(STYLESHEET)

    icon_path = get_asset_path("app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
