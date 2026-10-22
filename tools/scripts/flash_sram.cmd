@echo off
REM ===========================================================================
REM  flash_sram.cmd  --  Program the bitstream into the FPGA's SRAM
REM
REM  SRAM programming is VOLATILE: the design disappears on power off.
REM  That is the RIGHT choice while developing:
REM      fast (~4 seconds), zero risk, unlimited rewrites.
REM  Only after the design is frozen should you consider programming Flash
REM  (use the Gowin Programmer GUI for that -- the target medium still needs
REM  to be confirmed: on-chip embFlash vs the board's external SPI flash).
REM
REM  Usage:  double-click this file, or run it from any terminal:
REM      tools\scripts\flash_sram.cmd
REM
REM  Why this script exists: the toolchain path is long, and typing it by hand
REM  has already produced a typo ("prgrammer_cli.exe"). Let the shell hold the
REM  path instead of your fingers.
REM ===========================================================================
setlocal

REM --- paths ------------------------------------------------------------------
REM  Quote the WHOLE assignment:  set "VAR=value"   (NOT  set VAR="value")
REM  The latter stores the quote characters inside the variable, which then
REM  becomes part of the command name and breaks execution.
set "GOWIN_HOME=D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64"
set "PC=%GOWIN_HOME%\Programmer\bin\programmer_cli.exe"

REM  %~dp0 = the folder this script lives in (tools\scripts\), with a trailing \.
set "FS=%~dp0..\..\src\gowin\bringup_9k\impl\pnr\bringup_9k.fs"

REM --- sanity checks ----------------------------------------------------------
if not exist "%PC%" (
    echo [ERROR] programmer_cli.exe not found at:
    echo         %PC%
    echo         Fix GOWIN_HOME at the top of this script.
    exit /b 1
)
if not exist "%FS%" (
    echo [ERROR] bitstream not found at:
    echo         %FS%
    echo         Build it first with:
    echo             powershell -NoProfile -File tools\scripts\build_gowin.ps1 -Project src\gowin\bringup_9k\bringup_9k.gprj -SspiAsGpio
    exit /b 1
)

REM --- step 1: is the download cable there? -----------------------------------
echo == Looking for the download cable ==
"%PC%" --scan-cables
if errorlevel 1 goto :fail

REM --- step 2: program SRAM ---------------------------------------------------
echo.
echo == Programming SRAM ^(about 4 seconds^) ==
"%PC%" --device GW1NR-9C --operation_index 2 --fsFile "%FS%"
if errorlevel 1 goto :fail

echo.
echo == Done. The screen should show the picture now. ==
exit /b 0

:fail
echo.
echo [FAILED] Checklist:
echo    1. Is this a DATA-capable USB cable?  Charge-only cables power the
echo       board but never appear to the PC.  Test it on a phone: if the phone
echo       only says "charging", the cable has no data wires.
echo    2. Try the other USB-C port on the board.
echo    3. Wait about 10 seconds after plugging in for the driver to load.
echo    4. Device Manager should show 2x "USB Serial Converter" + 1 COM port.
exit /b 1
