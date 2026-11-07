@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"
rem 1) Python ghi trong .python-path.txt (neu con ton tai)
if exist "%~dp0.python-path.txt" (
  set /p BHYT_PYTHON=<"%~dp0.python-path.txt"
)
if defined BHYT_PYTHON if exist "%BHYT_PYTHON%" (
  "%BHYT_PYTHON%" server.py --port 8766 --open
  goto finished
)
if defined BHYT_PYTHON echo Duong dan trong .python-path.txt khong con ton tai; thu Python Launcher.
rem 2) Python Launcher cua Windows (py -3)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py --port 8766 --open
  goto finished
)
echo Chua tim thay Python 3.10+. Cai Python tu python.org hoac ghi duong dan python.exe vao .python-path.txt.
pause
exit /b 1
:finished
if errorlevel 1 pause
