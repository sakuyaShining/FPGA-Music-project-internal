@echo off
REM Canonical Tang Nano 20K SRAM entry. Preview by default; -Program writes SRAM.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0program_project.ps1" %*
exit /b %errorlevel%
