@echo off
setlocal
cd /d "%~dp0"
python main.py
if errorlevel 1 (
  echo.
  echo Evolve exited with an error.
  pause
)
