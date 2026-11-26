@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -I -u 수집.py
if errorlevel 9009 py -I -u 수집.py
pause
