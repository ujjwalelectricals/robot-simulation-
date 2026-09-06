@echo off
setlocal
cd /d "%~dp0"
python launcher.py
if errorlevel 1 (
  echo.
  echo Evolve exited with an error.
  pause
)
