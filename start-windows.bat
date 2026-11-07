@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"
if exist "%~dp0.python-path.txt" (
  set /p BHYT_PYTHON=<"%~dp0.python-path.txt"
  goto configured
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py --port 8766 --open
  goto finished
)
echo Chua tim thay Python. Xem README.md de cau hinh Python da cai.
pause
exit /b 1
:configured
if not exist "%BHYT_PYTHON%" (
  echo Duong dan Python khong con ton tai. Cap nhat .python-path.txt.
  pause
  exit /b 1
)
"%BHYT_PYTHON%" server.py --port 8766 --open
:finished
if errorlevel 1 pause
