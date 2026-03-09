@echo off
REM ============================================================
REM  LMS AI Reminder – Windows Task Scheduler Script
REM  Chạy mỗi 6 giờ để nhắc deadline và lịch thi
REM ============================================================
REM 
REM Để cài vào Task Scheduler:
REM   1. Mở "Task Scheduler" (tìm trong Start Menu)
REM   2. Click "Create Basic Task"
REM   3. Trigger: Daily, Repeat every 6 hours
REM   4. Action: Start a program
REM   5. Program: python
REM   6. Arguments: "C:\lms\ai_reminder\reminder.py"
REM   7. Start in: C:\lms\ai_reminder
REM
REM Hoặc chạy thủ công file này:
REM ============================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [%date% %time%] Chạy LMS AI Reminder...
python reminder.py

if %ERRORLEVEL% NEQ 0 (
    echo [LỖI] Reminder thất bại. Xem reminder.log để biết chi tiết.
) else (
    echo [OK] Reminder hoàn thành.
)

pause
