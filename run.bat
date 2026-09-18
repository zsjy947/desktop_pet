@echo off
rem Launch the desktop pet with pythonw (no console window).
rem Extra args are passed through, e.g. run.bat --char pikachu
cd /d "%~dp0"
start "" pythonw main.py %*
