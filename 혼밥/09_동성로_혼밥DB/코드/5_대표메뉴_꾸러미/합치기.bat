@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -I -B 합치기.py
if errorlevel 9009 py -I -B 합치기.py
pause
