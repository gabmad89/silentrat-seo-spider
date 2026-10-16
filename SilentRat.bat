@echo off
cd /d "%~dp0"
python silentrat.py
if errorlevel 1 pause
