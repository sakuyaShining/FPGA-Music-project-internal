#=============================================================================
# accept_all.ps1 —— 验收总入口（编译 → 回归 → 综合布局布线 → 时序判据）
#
# 为什么要有它：以前每次验收都是临时敲命令，"时序有没有达标"靠人记着去读。
# 现在把四步串起来，任一步不过就整体判红，并且【时序不达标 = 验收失败】。
#
# 用法：
#   powershell -File tools\scripts\accept_all.ps1
#   powershell -File tools\scripts\accept_all.ps1 -MinSlackNs 5
#   powershell -File tools\scripts\accept_all.ps1 -SkipPnr      # 只编译 + 回归
#   powershell -File tools\scripts\accept_all.ps1 -SkipGate     # 跳过回归
#
# 退出码：0 = 全部通过；1 = 有环节失败（含时序不达标）
#=============================================================================
param(
    [double]$MinSlackNs = 5.0,
    [switch]$SkipGate,
    [switch]$SkipPnr,
    [string]$Project = "src\gowin\tdm_synth\tdm_synth.gprj",
    [string]$Log = "sim_build\accept_all.log"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # 仓库根
Set-Location $root

New-Item -ItemType Directory -Force -Path sim_build | Out-Null
$t0 = Get-Date
"=== 验收开始 $($t0.ToString('yyyy-MM-dd HH:mm:ss')) ===" | Out-File $Log -Encoding utf8
$bad = @()

Write-Host "`n[1/4] 编译全部测试台" -ForegroundColor Cyan
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_sims.ps1 *>> $Log
"REAL_EXIT build_sims=$LASTEXITCODE" | Out-File $Log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { $bad += "build_sims" }
Write-Host "      rc=$LASTEXITCODE"

if (-not $SkipGate) {
    Write-Host "[2/4] 全量回归" -ForegroundColor Cyan
    python tools\scripts\regress_all.py --full *>> $Log
    "REAL_EXIT full_gate=$LASTEXITCODE" | Out-File $Log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { $bad += "full_gate" }
    Write-Host "      rc=$LASTEXITCODE"
} else {
    Write-Host "[2/4] 已跳过回归" -ForegroundColor DarkGray
}

if (-not $SkipPnr) {
    Write-Host "[3/4] 综合与布局布线（约 10 分钟）" -ForegroundColor Cyan
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_gowin.ps1 `
        -Project $Project -SspiAsGpio -PlaceOpt 2 -RouteOpt 2 *>> $Log
    "REAL_EXIT pnr=$LASTEXITCODE" | Out-File $Log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { $bad += "pnr" }
    Write-Host "      rc=$LASTEXITCODE"
} else {
    Write-Host "[3/4] 已跳过综合与布局布线" -ForegroundColor DarkGray
}

Write-Host "[4/4] 时序判据（slack ≥ $MinSlackNs ns）" -ForegroundColor Cyan
if ($SkipPnr) {
    python tools\scripts\check_timing.py --min $MinSlackNs *>> $Log
} else {
    # 本次真实跑过 PnR，要求时序文件是新的，避免拿旧结果当验收依据
    python tools\scripts\check_timing.py --min $MinSlackNs --require-fresh *>> $Log
}
$tRC = $LASTEXITCODE
"REAL_EXIT timing=$tRC" | Out-File $Log -Append -Encoding utf8
Get-Content $Log -Tail 5 | Where-Object { $_ -match "SETUP slack|判红|通过|年龄" } | ForEach-Object { Write-Host "      $_" }
if ($tRC -ne 0) { $bad += "timing" }

# ---- 汇总 ----
$t1 = Get-Date
"=== 验收结束 $($t1.ToString('yyyy-MM-dd HH:mm:ss'))，用时 $([int]($t1 - $t0).TotalMinutes) 分钟 ===" | Out-File $Log -Append -Encoding utf8
$verdict = if ($bad.Count -eq 0) { "通过" } else { "失败：" + ($bad -join "、") }
"验收结论：$verdict" | Out-File $Log -Append -Encoding utf8
"验收结论：$verdict" | Out-File sim_build\accept_result.txt -Encoding utf8

Write-Host ""
if ($bad.Count -eq 0) {
    Write-Host "验收通过（用时 $([int]($t1 - $t0).TotalMinutes) 分钟）" -ForegroundColor Green
    exit 0
} else {
    Write-Host "验收失败：$($bad -join '、')" -ForegroundColor Red
    Write-Host "详见 $Log" -ForegroundColor Red
    exit 1
}
