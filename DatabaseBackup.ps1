# =============================================
# اسکریپت بکاپ پایگاه داده
# Database Backup Script
# =============================================

$logFile = "Y:\DatabaseBackup\Database\backup_log_$(Get-Date -Format 'yyyy-MM-dd_HHmm').txt"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log {
    param([string]$msg, [string]$color = "White")
    $line = "[$timestamp] $msg"
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $logFile -Value $line
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   شروع عملیات بکاپ پایگاه داده" -ForegroundColor Cyan
Write-Host "          $(Get-Date -Format 'yyyy/MM/dd HH:mm')" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Log "شروع عملیات بکاپ" "Cyan"

# Track copied files
$copiedFiles1 = @()
$copiedFiles2 = @()

# -----------------------------------------------
# مرحله ۱: بکاپ از سرور ORUMDC
# -----------------------------------------------
$source1 = "\\ORUMDC\Backup"
$dest1 = "Y:\DatabaseBackup\Database\acc"

Write-Log "بررسی سرور حقوق مالی انبار ..." "Yellow"

if (Test-Path $source1) {
    Write-Log "سرور در دسترس است. شروع کپی..." "Yellow"
    
    # Count files before copy
    $filesBefore = (Get-ChildItem -Path $dest1 -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Log "تعداد فایل‌های موجود: $filesBefore" "Gray"
    
    # Run robocopy with logging
    $robocopyLog = "Y:\DatabaseBackup\Database\robocopy_acc.log"
    robocopy $source1 $dest1 /xo /s /nfl /np /log+:$robocopyLog
    
    $exitCode = $LASTEXITCODE
    $filesAfter = (Get-ChildItem -Path $dest1 -Recurse -File -ErrorAction SilentlyContinue).Count
    $newFiles = $filesAfter - $filesBefore

    # Get list of new files
    if ($newFiles -gt 0) {
        $copiedFiles1 = Get-ChildItem -Path $dest1 -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First $newFiles
    }

    # Find newest file in destination
    $newestFile1 = Get-ChildItem -Path $dest1 -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1

    if ($exitCode -le 3) {
        Write-Log "بکاپ سرور حقوق مالی انبار با موفقیت انجام شد" "Green"
        Write-Log "فایل‌های جدید: $newFiles " "Green"
        Write-Log "مجموع: $filesAfter" "Green"
        if ($newestFile1) {
            $hoursAgo1 = [math]::Round(((Get-Date) - $newestFile1.LastWriteTime).TotalHours, 0)
            if ($hoursAgo1 -gt 24) {
                Write-Log "جدیدترین فایل بکاپ: $($hoursAgo1) ساعت پیش" "Red"
                Write-Log "!! هشدار: بکاپ بیش از 24 ساعت پیش انجام شده !!" "Red"
            } else {
                Write-Log "جدیدترین فایل بکاپ: $($hoursAgo1) ساعت پیش" "Yellow"
            }
        }        
    } else {
        Write-Log "هشدار: کد خروج robocopy = $exitCode" "Red"
    }
} else {
    Write-Log "خطا: مسیر سرور در دسترس نیست!" "Red"
}

Write-Host ""
 
# -----------------------------------------------
# مرحله ۲: انتظار ۳ ثانیه
# -----------------------------------------------
Write-Log "انتظار ۳ ثانیه قبل از مرحله بعد..." "Yellow"
for ($i = 3; $i -ge 1; $i--) {
    Write-Host "  $i..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
}

Write-Host ""

# -----------------------------------------------
# مرحله ۳: بکاپ از سرور 172.30.39.21
# -----------------------------------------------
$source2 = "\\172.30.39.21\backup_pw"
$dest2 = "Y:\DatabaseBackup\Database\pw"

Write-Log "بررسی سرور دوم حضورغیاب..." "Yellow"

if (Test-Path $source2) {
    Write-Log "سرور در دسترس است. شروع کپی..." "Yellow"
    
    # Count files before copy
    $filesBefore = (Get-ChildItem -Path $dest2 -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Log "تعداد فایل‌های موجود: $filesBefore" "Gray"
    
    # Run robocopy with logging
    $robocopyLog = "Y:\DatabaseBackup\Database\robocopy_pw.log"
    robocopy $source2 $dest2 /xo /s /nfl /np /log+:$robocopyLog
    
    $exitCode = $LASTEXITCODE
    $filesAfter = (Get-ChildItem -Path $dest2 -Recurse -File -ErrorAction SilentlyContinue).Count
    $newFiles = $filesAfter - $filesBefore

    # Get list of new files
    if ($newFiles -gt 0) {
        $copiedFiles2 = Get-ChildItem -Path $dest2 -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First $newFiles
    }

    # Find newest file in destination
    $newestFile2 = Get-ChildItem -Path $dest2 -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1

    if ($exitCode -le 3) {
        Write-Log "بکاپ سرور دوم حضورغیاب با موفقیت انجام شد" "Green"
        Write-Log "فایل‌های جدید: $newFiles " "Green"
        Write-Log "مجموع: $filesAfter" "Green"
        if ($newestFile2) {
            $hoursAgo2 = [math]::Round(((Get-Date) - $newestFile2.LastWriteTime).TotalHours, 0)
            if ($hoursAgo2 -gt 24) {
                Write-Log "جدیدترین فایل بکاپ: $($hoursAgo2) ساعت پیش" "Red"
                Write-Log "!! هشدار: بکاپ بیش از 24 ساعت پیش انجام شده !!" "Red"
            } else {
                Write-Log "جدیدترین فایل بکاپ: $($hoursAgo2) ساعت پیش" "Yellow"
            }
        } 
    } else {
        Write-Log "هشدار: کد خروج robocopy = $exitCode" "Red"
    }
} else {
    Write-Log "خطا: مسیر سرور در دسترس نیست!" "Red"
}

# -----------------------------------------------
# پایان عملیات - خلاصه
# -----------------------------------------------
Write-Host ""
Write-Log "========================================" "Cyan"
Write-Log "   خلاصه عملیات بکاپ" "Cyan"
Write-Log "========================================" "Cyan"

if ($copiedFiles1.Count -gt 0) {
    Write-Log "--- فایل‌های کپی شده حقوق مالی انبار ---" "Yellow"
    foreach ($f in $copiedFiles1) {
        Write-Log "  $($f.Name) | $($f.LastWriteTime)" "Gray"
    }
} else {
    Write-Log "مرحله ۱: فایل جدیدی کپی نشد" "Gray"
}

Write-Host ""

if ($copiedFiles2.Count -gt 0) {
    Write-Log "--- فایل‌های کپی شده حضورغیاب ---" "Yellow"
    foreach ($f in $copiedFiles2) {
        Write-Log "  $($f.Name) | $($f.LastWriteTime)" "Gray"
    }
} else {
    Write-Log "مرحله ۲: فایل جدیدی کپی نشد" "Gray"
}

Write-Host ""
Write-Log "========================================" "Cyan"
Write-Log "   عملیات بکاپ به پایان رسید" "Cyan"
Write-Log "========================================" "Cyan"

Start-Process notepad.exe $logFile

