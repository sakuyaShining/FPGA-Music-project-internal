<#
=============================================================================
 build_gowin.ps1 -- 用 Gowin 命令行控制台 (gw_sh) 批量编译 .gprj 工程

 为什么要有这个脚本：
   Gowin IDE 的图形界面点一遍能编译，但每改一次代码都要点鼠标、还要手动
   记住一堆工程配置选项（比如本工程的 "Use SSPI as regular IO"）。
   把编译变成一条命令，才能做到"改完代码一条命令出码流"，也才能被自动化。

 用法：
   pwsh -File tools\scripts\build_gowin.ps1 `
        -Project src\gowin\tdm_synth\tdm_synth.gprj -SspiAsGpio

 产物：
   <工程目录>\impl\pnr\<顶层模块名>.fs     <-- 要烧进 FPGA 的码流文件

 注意 -SspiAsGpio：
   本工程把 LCD 的 G4/G5/B0 三个信号接在了引脚 54/55/56 上，这三个脚默认是
   SSPI（从机配置接口）专用脚。不释放它们，布局布线会直接报：
       ERROR (PR2017): ... for the location is a dedicated pin (SSPI)
   释放方式就是 set_option -use_sspi_as_gpio 1。
   官方文件里也这么做（TangNano-9K-example/lcd_4.3），所以是标准做法。
   释放 SSPI 不影响 JTAG 烧录，也不影响从板载 Flash 上电启动（那走的是 MSPI）。
=============================================================================
#>
[CmdletBinding()]
param(
    # .gprj 工程文件路径（相对当前目录或绝对路径都行）
    [Parameter(Mandatory = $true)]
    [string]$Project,

    # Gowin EDA 安装根目录。默认是本机教育版的安装位置。
    [string]$GowinHome = "D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64",

    # 把 SSPI 专用脚释放为普通 IO（LCD 用到 54/55/56 时必须开）
    [switch]$SspiAsGpio,

    # 顶层模块名。留空则交给 Gowin 自动识别（工程里只有一个顶层时够用）
    [string]$TopModule = "",

    # 只做综合，不做布局布线（快速查语法错）
    [switch]$SynOnly,

    # 放置/布线策略（0/1/2…；遇到 "DesRoute failed / PR0004" 时可换策略试）
    [int]$PlaceOpt = -1,

    # 布线策略
    [int]$RouteOpt = -1
)

$ErrorActionPreference = "Stop"

# --- 1. 解析路径 -------------------------------------------------------------
$prjPath = (Resolve-Path -LiteralPath $Project).Path
$prjDir  = Split-Path -Parent $prjPath
$gwSh    = Join-Path $GowinHome "IDE\bin\gw_sh.exe"

if (-not (Test-Path -LiteralPath $gwSh)) {
    throw "找不到 gw_sh.exe：$gwSh`n请用 -GowinHome 指定 Gowin EDA 安装目录。"
}

# gw_sh 用正斜杠更稳（反斜杠在 Tcl 里是转义符）
$prjTcl = $prjPath -replace '\\', '/'
$dirTcl = $prjDir  -replace '\\', '/'

# --- 2. 生成 Tcl 脚本 --------------------------------------------------------
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("open_project `"$prjTcl`"")
if ($SspiAsGpio) {
    $lines.Add("set_option -use_sspi_as_gpio 1")
}
if ($TopModule -ne "") {
    $lines.Add("set_option -top_module $TopModule")
}
if ($PlaceOpt -ge 0) {
    $lines.Add("set_option -place_option $PlaceOpt")
}
if ($RouteOpt -ge 0) {
    $lines.Add("set_option -route_option $RouteOpt")
}
if ($SynOnly) {
    $lines.Add("run syn")
} else {
    $lines.Add("run all")
}
$lines.Add("exit")

$tclPath = Join-Path $env:TEMP ("gowin_build_" + [guid]::NewGuid().ToString("N") + ".tcl")
Set-Content -LiteralPath $tclPath -Value $lines -Encoding ascii

# --- 3. 调 gw_sh 编译 --------------------------------------------------------
Write-Host "== 工程 : $prjPath" -ForegroundColor Cyan
if ($SspiAsGpio) { Write-Host "== 选项 : -use_sspi_as_gpio 1" -ForegroundColor Cyan }
Write-Host "== 开始编译 ..." -ForegroundColor Cyan

$env:GOWINHOME = $GowinHome

# ---------------------------------------------------------------------------
# 【踩坑记录】不要用 `& $gwSh $tcl 2>&1 | Out-String` 抓 gw_sh 的输出。
# gw_sh 会把进度等普通内容写到 stderr，而 Windows PowerShell 5.1 一遇到
# "外部程序写了 stderr" 就抛 NativeCommandError —— 哪怕 gw_sh 运行完全正常，
# 脚本也会被误判成失败。（临时改 $ErrorActionPreference 也压不住。）
# 可靠做法：用 Start-Process 把 stdout / stderr **各自重定向到文件**，
# 两个流在操作系统层就分开了，不经过 PowerShell 的流包装。
# ---------------------------------------------------------------------------
$outFile = Join-Path $env:TEMP ("gowin_out_" + [guid]::NewGuid().ToString("N") + ".txt")
$errFile = Join-Path $env:TEMP ("gowin_err_" + [guid]::NewGuid().ToString("N") + ".txt")

$proc = Start-Process -FilePath $gwSh -ArgumentList @($tclPath) `
                      -WorkingDirectory $prjDir -NoNewWindow -Wait -PassThru `
                      -RedirectStandardOutput $outFile -RedirectStandardError $errFile

$gwExit = $proc.ExitCode
$output = ((Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue) + "`n" +
           (Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue))
Remove-Item -LiteralPath $outFile, $errFile, $tclPath -ErrorAction SilentlyContinue

# --- 4. 汇报结果 -------------------------------------------------------------
# 只挑关键行显示，避免刷屏；完整输出在出错时会全部打印
$errs = $output -split "`r?`n" | Where-Object { $_ -match '\bERROR\b' }
$warns = $output -split "`r?`n" | Where-Object { $_ -match '\bWARN\b' }

if ($errs.Count -gt 0) {
    Write-Host "== 编译失败，错误如下：" -ForegroundColor Red
    $errs | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "== 完整输出：" -ForegroundColor DarkGray
    Write-Host $output
    exit 1
}

if ($warns.Count -gt 0) {
    Write-Host "== 告警（不影响出码流，但值得看一眼）：" -ForegroundColor Yellow
    $warns | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}

if ($SynOnly) {
    Write-Host "== 综合通过（未做布局布线）" -ForegroundColor Green
    exit 0
}

$fs = Get-ChildItem -Path (Join-Path $prjDir "impl\pnr") -Filter *.fs -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($null -eq $fs) {
    Write-Host "== 没找到 .fs 码流文件，编译可能没走完" -ForegroundColor Red
    Write-Host $output
    exit 1
}

Write-Host ""
Write-Host "== 编译成功" -ForegroundColor Green
Write-Host ("== 码流文件 : " + $fs.FullName) -ForegroundColor Green
Write-Host ("== 大小     : " + [math]::Round($fs.Length / 1KB, 1) + " KB") -ForegroundColor Green
Write-Host ("== 时间     : " + $fs.LastWriteTime) -ForegroundColor Green
