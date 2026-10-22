@echo off
cd /d "%~dp0\..\.."
python tools\host\dsp_gui.py
if errorlevel 1 pause
