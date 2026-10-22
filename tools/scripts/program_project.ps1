# SRAM only. Preview by default; -Program performs the hardware operation.
[CmdletBinding()]
param([string]$GowinHome = $env:FPGA_MUSIC_GOWIN_HOME, [string]$Bitstream, [switch]$Program)
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $GowinHome) { throw 'Set FPGA_MUSIC_GOWIN_HOME or pass -GowinHome.' }
$taskProgrammer = Join-Path $GowinHome 'Programmer/bin/programmer_cli.exe'
if (-not (Test-Path -LiteralPath $taskProgrammer)) { throw "Programmer not found: $taskProgrammer" }
if (-not $Bitstream) { $Bitstream = Join-Path $taskProjectRoot 'src/gowin/tdm_synth/impl/pnr/tdm_synth.fs' }
$taskBitstreamPath = (Resolve-Path -LiteralPath $Bitstream).Path
$taskArguments = @('--device', 'GW2AR-18C', '--operation_index', '2', '--fsFile', $taskBitstreamPath)
Write-Output 'Device: GW2AR-18C; operation: SRAM Program (2)'
Write-Output "Bitstream: $taskBitstreamPath"
Write-Output "SHA256: $((Get-FileHash -LiteralPath $taskBitstreamPath -Algorithm SHA256).Hash)"
if (-not $Program) { Write-Output 'Preview only. Add -Program to program SRAM; power cycling removes this design.'; exit 0 }
& $taskProgrammer @taskArguments
exit $LASTEXITCODE
