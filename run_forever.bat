@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run setup.bat first.
  pause
  exit /b 1
)

:loop
".venv\Scripts\python.exe" bot.py
echo.
echo [%date% %time%] Bot exited. Restarting in 5 seconds. Close this window to stop.
timeout /t 5 >nul
goto loop
