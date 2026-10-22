# weekly_check.ps1
# 用途：每周检查竞赛官网是否有新通知 / 新文件，并追加记录到监控日志
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\weekly_check.ps1
#
# 判定规则（基线见 tools\state\monitor-state.json）：
#   通知 id > lastNewsId  或  文件 id > lastFileId  =>  视为有新内容
#
# 注意：本文件必须保存为 UTF-8 with BOM，否则 Windows PowerShell 5.1 会按 GBK 读取导致乱码

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = Split-Path -Parent (Split-Path -Parent $scriptDir)
$stateFile = Join-Path $root 'tools\state\monitor-state.json'
$logFile   = Join-Path $root 'docs\01-竞赛情报\monitoring-log.md'

New-Item -ItemType Directory -Force -Path (Split-Path $stateFile) | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Log([string]$text) {
    [System.IO.File]::AppendAllText($logFile, $text + "`r`n", $utf8NoBom)
}

$now   = Get-Date
$stamp = $now.ToString('yyyy-MM-dd HH:mm')

# ---------- 载入基线 ----------
$state = $null
if (Test-Path $stateFile) {
    try {
        $state = [System.IO.File]::ReadAllText($stateFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    } catch { $state = $null }
}
if (-not $state) {
    $state = [pscustomobject]@{ lastNewsId = 56; lastFileId = 25; lastCheck = $null; lastResult = $null }
}

try {
    . (Join-Path $scriptDir 'api.ps1')

    $newsRaw = Invoke-Api '/cms/news/list' @{ pageNum = 1; pageSize = 80 }
    $fileRaw = Invoke-Api '/cms/file/list' @{ pageNum = 1; pageSize = 80 }

    if ($newsRaw -match '^ERR' -or $fileRaw -match '^ERR') {
        throw ('接口返回异常')
    }

    $news  = $newsRaw | ConvertFrom-Json
    $files = $fileRaw | ConvertFrom-Json

    $newNews  = @($news.rows  | Where-Object { [int]$_.id -gt [int]$state.lastNewsId } | Sort-Object { [int]$_.id })
    $newFiles = @($files.rows | Where-Object { [int]$_.id -gt [int]$state.lastFileId } | Sort-Object { [int]$_.id })

    $changed = ($newNews.Count -gt 0) -or ($newFiles.Count -gt 0)

    # ---------- 写日志 ----------
    Write-Log ''
    Write-Log ('## 检查 ' + $stamp)
    Write-Log ''
    Write-Log ('- 通知总数 **' + $news.total  + '**（上次基线 id=' + $state.lastNewsId + '）')
    Write-Log ('- 文件总数 **' + $files.total + '**（上次基线 id=' + $state.lastFileId + '）')

    if (-not $changed) {
        Write-Log ''
        Write-Log '> OK — 无新内容'
    } else {
        if ($newNews.Count -gt 0) {
            Write-Log ''
            Write-Log ('### 新通知 ' + $newNews.Count + ' 条')
            Write-Log ''
            foreach ($r in $newNews) {
                Write-Log ('- id=' + $r.id + '  ' + $r.createTime + '  「' + $r.title.Trim() + '」')
            }
        }
        if ($newFiles.Count -gt 0) {
            Write-Log ''
            Write-Log ('### 新文件 ' + $newFiles.Count + ' 个')
            Write-Log ''
            foreach ($r in $newFiles) {
                Write-Log ('- id=' + $r.id + '  ' + $r.createTime + '  「' + $r.title.Trim() + '」')
            }
        }
        Write-Log ''
        Write-Log '> 注意 — 发现新内容，需判断是否影响项目（评分细则 / 作品报告模板 / 提交要求 / 选题指南）'
    }

    # ---------- 更新基线 ----------
    $maxNews = [int]$state.lastNewsId
    $maxFile = [int]$state.lastFileId
    if ($newNews.Count  -gt 0) { $maxNews = [int](($newNews  | Measure-Object -Property id -Maximum).Maximum) }
    if ($newFiles.Count -gt 0) { $maxFile = [int](($newFiles | Measure-Object -Property id -Maximum).Maximum) }

    $newState = [pscustomobject]@{
        lastNewsId = $maxNews
        lastFileId = $maxFile
        lastCheck  = $stamp
        lastResult = $(if ($changed) { 'changed' } else { 'no-change' })
    }
    [System.IO.File]::WriteAllText($stateFile, ($newState | ConvertTo-Json), $utf8NoBom)

    Write-Host ('[OK] ' + $stamp + '  新通知 ' + $newNews.Count + ' 条 / 新文件 ' + $newFiles.Count + ' 个')
    exit 0
}
catch {
    Write-Log ''
    Write-Log ('## 检查 ' + $stamp)
    Write-Log ''
    Write-Log ('> 检查失败：' + $_.Exception.Message)
    Write-Log '> 基线未变更，下次检查会重新核对。'
    Write-Host ('[FAIL] ' + $_.Exception.Message)
    exit 1
}
