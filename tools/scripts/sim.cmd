@echo off
REM ===========================================================================
REM  sim.cmd  --  Compile + run + view waveform   (Icarus Verilog + GTKWave)
REM
REM  WHY THIS SCRIPT EXISTS
REM    1. The iverilog installer did NOT add itself to PATH, so "iverilog" is
REM       not found in a normal terminal.
REM    2. Setting PATH here affects THIS SESSION ONLY -- your system PATH in
REM       the registry is left untouched. (That is deliberate: the user
REM       prefers terminal-level overrides over permanent PATH edits.)
REM
REM  USAGE
REM      tools\scripts\sim.cmd  <file1.v> [file2.v ...]
REM
REM  EXAMPLES
REM      tools\scripts\sim.cmd  src\sim\tb_hello_tick.v src\sim\hello_tick.v
REM      tools\scripts\sim.cmd  src\sim\tb_my_design.v src\rtl\my_design.v
REM
REM  WHAT IT DOES
REM      1. iverilog : compile all the .v files into sim_build\sim.vvp
REM      2. vvp      : run the simulation
REM      3. gtkwave  : open the newest .vcd produced under sim_build\
REM
REM  NOTE ON THE TESTBENCH
REM      Your testbench must contain $dumpfile / $dumpvars, otherwise no .vcd
REM      is produced and GTKWave will open an empty window.
REM ===========================================================================
setlocal

set "IVROOT=D:\iverilog"
set "PATH=%IVROOT%\bin;%PATH%"

if "%~1"=="" (
    echo.
    echo   Usage:  sim.cmd  ^<file1.v^> [file2.v ...]
    echo   Example: sim.cmd  src\sim\tb_hello_tick.v src\sim\hello_tick.v
    echo.
    exit /b 1
)

if not exist "%IVROOT%\bin\iverilog.exe" (
    echo [ERROR] iverilog not found at %IVROOT%\bin\iverilog.exe
    echo         Fix IVROOT at the top of this script.
    exit /b 1
)

set "ROOT=%~dp0..\.."
set "OUTDIR=%ROOT%\sim_build"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

REM --- 1. compile ------------------------------------------------------------
echo == [1/3] Compiling ==
iverilog -g2005 -Wall -o "%OUTDIR%\sim.vvp" %*
if errorlevel 1 (
    echo.
    echo [COMPILE FAILED]  read the errors above.
    exit /b 1
)
echo    OK -^> %OUTDIR%\sim.vvp

REM --- 2. run ----------------------------------------------------------------
echo.
echo == [2/3] Running ==
pushd "%OUTDIR%"
vvp sim.vvp
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
    echo.
    echo [SIMULATION FAILED]  exit code %RC%
    exit /b 1
)

REM --- 3. waveform -----------------------------------------------------------
echo.
echo == [3/3] Waveform ==
if defined SIM_NOWAVE (
    echo    SIM_NOWAVE is set -^> skipping GTKWave, .vcd kept for later.
    goto :done
)
set "VCD="
for /f "delims=" %%V in ('dir /b /o-d "%OUTDIR%\*.vcd" 2^>nul') do (
    if not defined VCD set "VCD=%OUTDIR%\%%V"
)
if defined VCD (
    echo    Opening %VCD%
    REM  NOTE: a GUI child inherits this process's stdout. If you redirect
    REM        sim.cmd's output to a pipe or a file, the pipe stays open until
    REM        GTKWave is closed. Set SIM_NOWAVE=1 to skip the GUI in scripts.
    start "" "%IVROOT%\bin\gtkwave.exe" "%VCD%"
) else (
    echo    No .vcd found under %OUTDIR%
    echo    Does your testbench call  $dumpfile / $dumpvars ?
)

:done
exit /b 0
