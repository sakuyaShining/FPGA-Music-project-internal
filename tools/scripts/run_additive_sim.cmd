@echo off
REM ===========================================================================
REM  run_additive_sim.cmd -- one command: stimulus -> simulate -> FFT -> WAV
REM
REM  This is the WHOLE verification chain of the additive synthesis engine,
REM  and it needs NO hardware at all: no board, no sensors, no speaker.
REM
REM  Steps:
REM    1. python additive_tool.py gen      -> sine table + stimulus .hex files
REM    2. iverilog + vvp                   -> dump 12000 samples x 2 test cases
REM    3. python additive_tool.py analyze  -> WAV (listenable) + FFT + report
REM
REM  Output: sim_build\additive\
REM     samples_harmonic.txt / samples_inharmonic.txt   raw simulation output
REM     additive_harmonic.wav / additive_inharmonic.wav LISTEN to these
REM     spectrum_*.csv                                   FFT data
REM     <report>.md                                      pass/fail report
REM     osc_additive.vcd                                 waveform for GTKWave
REM
REM  Usage:  tools\scripts\run_additive_sim.cmd
REM ===========================================================================
setlocal
chcp 936 >nul

set "IVROOT=D:\iverilog"
set "PATH=%IVROOT%\bin;%PATH%"

set "ROOT=%~dp0..\.."
set "BUILD=%ROOT%\sim_build\additive"
set "PY=python"

if not exist "%BUILD%" mkdir "%BUILD%"

echo ============================================================
echo  [1/3] Generating sine table and stimulus
echo ============================================================
%PY% "%ROOT%\tools\scripts\additive_tool.py" gen --outdir "%BUILD%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  [2/3] Compiling and running simulation
echo ============================================================
pushd "%BUILD%"
iverilog -g2005 -o sim.vvp "%ROOT%\src\sim\tb_osc_additive.v" "%ROOT%\src\rtl\osc_additive.v"
if errorlevel 1 (
    echo [COMPILE FAILED]
    popd
    goto :fail
)
vvp sim.vvp
if errorlevel 1 (
    echo [SIMULATION FAILED]
    popd
    goto :fail
)
popd

echo.
echo ============================================================
echo  [3/3] FFT analysis and WAV rendering
echo ============================================================
%PY% "%ROOT%\tools\scripts\additive_tool.py" analyze --indir "%BUILD%" --outdir "%BUILD%" --meta "%BUILD%\stimulus_meta.json"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo   [OK] ALL PEAKS MATCHED
) else (
    echo   [WARN] some peaks did not match - read the report
)
echo ============================================================
echo   Output folder: %BUILD%
echo.
echo   Listen to :  additive_harmonic.wav
echo                additive_inharmonic.wav
echo   Read      :  the report .md in that folder
echo.
start "" "%BUILD%"
exit /b %RC%

:fail
echo.
echo [ABORTED]
exit /b 1
