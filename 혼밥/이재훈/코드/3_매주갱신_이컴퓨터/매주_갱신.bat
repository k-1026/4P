@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -B -I -u 매주_갱신.py %*
if errorlevel 9009 py -B -I -u 매주_갱신.py %*
