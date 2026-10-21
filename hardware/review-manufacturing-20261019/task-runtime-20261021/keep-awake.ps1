# Temporary system-sleep request for this user-authorized unattended task.
# No registry, global power-plan or execution-policy change. Display may turn off.
$taskRuntimeDir = 'C:\Users\Sakuya\.codex\worktrees\06df\FPGA-Music-project\hardware\review-manufacturing-20261019\task-runtime-20261021'
$taskStopFile = Join-Path $taskRuntimeDir 'stop-keep-awake.flag'
$taskStateFile = Join-Path $taskRuntimeDir 'keep-awake-state.json'
$taskDeadline = [DateTime]::UtcNow.AddHours(4)
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class MusicTaskPowerRequest { [DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint state); }'
try {
    $taskPreviousState = [MusicTaskPowerRequest]::SetThreadExecutionState([uint32]2147483649)
    if ($taskPreviousState -eq 0) { throw 'System sleep request failed' }
    @{ pid=$PID; active=$true; started_utc=[DateTime]::UtcNow.ToString('o'); expires_utc=$taskDeadline.ToString('o'); display_required=$false; global_power_plan_changed=$false } | ConvertTo-Json | Set-Content -LiteralPath $taskStateFile -Encoding utf8
    while ([DateTime]::UtcNow -lt $taskDeadline -and -not (Test-Path -LiteralPath $taskStopFile)) {
        [System.Threading.Thread]::Sleep(50000)
    }
} finally {
    [void][MusicTaskPowerRequest]::SetThreadExecutionState([uint32]2147483648)
    @{ pid=$PID; active=$false; stopped_utc=[DateTime]::UtcNow.ToString('o'); global_power_plan_changed=$false } | ConvertTo-Json | Set-Content -LiteralPath $taskStateFile -Encoding utf8
}
