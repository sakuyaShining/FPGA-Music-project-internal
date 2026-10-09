[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BuildRecord,
    [string]$Programmer = "D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\Programmer\bin\programmer_cli.exe"
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
Push-Location -LiteralPath $repoRoot
try {
    python tools/scripts/project_version.py check-build $BuildRecord
    if ($LASTEXITCODE -ne 0) { throw 'Source/build identity check failed; download refused.' }
    $record = Get-Content -LiteralPath $BuildRecord -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($record.configuration -notmatch 'GW2AR-LV18QN88C8/I7') { throw 'Record is not for Tang Nano 20K.' }
    Write-Host "Temporary SRAM download: $($record.bitstream)"
    Write-Host "SHA256: $($record.bitstream_sha256)"
    & $Programmer --device GW2AR-18C --operation_index 2 --frequency 2.5MHz --fsFile $record.bitstream
    if ($LASTEXITCODE -ne 0) { throw "SRAM programming failed: $LASTEXITCODE" }
    Write-Host 'Downloaded the identified build. Hardware behavior still requires recorded tests.'
} finally { Pop-Location }
