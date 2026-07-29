import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
from typing import List
from core.copier import JobResult

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console(force_terminal=True, legacy_windows=False)

def print_header():
    title = Text("🚀 سیستم مدیریت و پشتیبان‌گیری سرورها", style="bold cyan")
    subtitle = Text(f"تاریخ و زمان اجرا: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}", style="dim")
    panel = Panel(
        Text.assemble(title, "\n", subtitle),
        border_style="cyan",
        padding=(0, 2)
    )
    console.print(panel)

def print_job_start(job_name: str, source: str):
    console.print(f"\n[bold yellow]🔍 بررسی سرور {job_name}...[/bold yellow]")
    console.print(f"  [dim]مسیر سورس: {source}[/dim]")

def print_results_table(results: List[JobResult]):
    table = Table(title="📊 خلاصه وضعیت بکاپ سرورها", border_style="bright_blue", header_style="bold magenta")

    table.add_column("نام سرور", style="cyan", justify="right")
    table.add_column("وضعیت", justify="center")
    table.add_column("فایل‌های جدید", justify="center")
    table.add_column("مجموع فایل‌ها", justify="center")
    table.add_column("آخرین بکاپ", justify="center")
    table.add_column("پیام / هشدار", justify="right")

    for r in results:
        if not r.source_available:
            status = "[bold red]در دسترس نیست[/bold red]"
            new_f = "-"
            total_f = "-"
            age = "-"
            msg = "[red]خطا: عدم دسترسی به شبکه/سورس[/red]"
        elif not r.success:
            status = "[bold red]خطا در کپی[/bold red]"
            new_f = str(r.new_files_count)
            total_f = str(r.files_after)
            age = f"{r.stale_hours}h ago"
            msg = f"[red]کد خطای robocopy: {r.exit_code}[/red]"
        else:
            if r.warning_stale:
                status = "[bold yellow]هشدار مانیتورینگ[/bold yellow]"
                msg = f"[bold red]!! بکاپ بیش از {r.job.warn_older_than_hours} ساعت پیش انجام شده !![/bold red]"
            else:
                status = "[bold green]موفق[/bold green]"
                msg = "[green]عملیات با موفقیت انجام شد[/green]"

            new_f = f"[green]+{r.new_files_count}[/green]" if r.new_files_count > 0 else "0"
            total_f = str(r.files_after)
            age = f"[yellow]{r.stale_hours}h ago[/yellow]" if r.warning_stale else f"{r.stale_hours}h ago"

        table.add_row(r.job.name, status, new_f, total_f, age, msg)

    console.print("\n")
    console.print(table)

def print_copied_details(results: List[JobResult]):
    for r in results:
        if r.copied_files:
            console.print(f"\n[bold yellow]📋 فایل‌های کپی شده - {r.job.name}:[/bold yellow]")
            for f in r.copied_files:
                console.print(f"  [green]•[/green] {f.name} | [dim]{f.mtime.strftime('%Y-%m-%d %H:%M')}[/dim]")

def print_footer():
    console.print(Panel(Text("✅ تمامی مراحل پشتیبان‌گیری به پایان رسید", style="bold green", justify="center"), border_style="green"))
