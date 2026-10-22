$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$script:base = 'http://www.fpgachina.cn/rest/pc'
$script:key  = 'kiHjr0YY2GXSu8FySitOKUiwRGmKwGaGFjc1Cm'
$script:md5  = [System.Security.Cryptography.MD5]::Create()

function Get-Md5Upper([string]$s) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
    $hash  = $script:md5.ComputeHash($bytes)
    ($hash | ForEach-Object { $_.ToString('x2') }) -join '' | ForEach-Object { $_.ToUpper() }
}

function Get-Nonce {
    $cs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    -join (1..16 | ForEach-Object { $cs[(Get-Random -Maximum $cs.Length)] })
}

function Get-Signed([hashtable]$params) {
    $p = @{}
    foreach ($k in $params.Keys) {
        $v = $params[$k]
        if ($null -eq $v -or "$v" -eq '') { continue }
        $p[$k] = "$v"
    }
    $ts    = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString()
    $nonce = Get-Nonce
    $p['timestamp'] = $ts
    $p['nonce']     = $nonce

    $sb = New-Object System.Text.StringBuilder
    foreach ($k in ($p.Keys | Sort-Object)) {
        [void]$sb.Append("$k=$($p[$k])&")
    }
    [void]$sb.Append("key=$script:key")
    $sign = Get-Md5Upper $sb.ToString()
    $p['sign'] = $sign
    return $p
}

function Invoke-Api([string]$path, [hashtable]$params) {
    $p = Get-Signed $params
    $qs = ($p.Keys | Sort-Object | ForEach-Object { "$_=$([uri]::EscapeDataString($p[$_]))" }) -join '&'
    $url = "$script:base$path`?$qs"
    try {
        $tmp = Join-Path $env:TEMP ("api_" + [guid]::NewGuid().ToString('N') + '.json')
        Invoke-WebRequest -Uri $url -Headers @{ lang = 'zh' } -UseBasicParsing -TimeoutSec 30 -OutFile $tmp
        $bytes = [System.IO.File]::ReadAllBytes($tmp)
        Remove-Item $tmp -Force
        return [System.Text.Encoding]::UTF8.GetString($bytes)
    } catch {
        return "ERR: $($_.Exception.Message)"
    }
}

function Show([string]$label, [string]$path, [hashtable]$params) {
    Write-Output "===== $label  ($path) ====="
    $c = Invoke-Api $path $params
    if ($c.Length -gt 4000) { $c = $c.Substring(0, 4000) + '...[truncated]' }
    Write-Output $c
}
