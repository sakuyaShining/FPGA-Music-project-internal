# Canonical Tang Nano 20K build entry. Run from any working directory.
[CmdletBinding()]
param([string]$GowinHome = $env:FPGA_MUSIC_GOWIN_HOME, [switch]$SynOnly)
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $GowinHome) {
    $taskGwCommand = Get-Command gw_sh.exe -ErrorAction SilentlyContinue
    if ($taskGwCommand) { $GowinHome = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $taskGwCommand.Source)) }
}
if (-not $GowinHome) { throw 'Set FPGA_MUSIC_GOWIN_HOME or pass -GowinHome (the directory containing IDE and Programmer).' }
& (Join-Path $PSScriptRoot 'build_gowin.ps1') `
    -Project (Join-Path $taskProjectRoot 'src/gowin/tdm_synth/tdm_synth.gprj') `
    -GowinHome $GowinHome -TopModule tdm_ship -SspiAsGpio -SynOnly:$SynOnly
exit $LASTEXITCODE
