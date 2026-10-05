# build_sims.ps1 -- rebuild ALL testbenches with one command, then print timestamps
#
# WHY THIS EXISTS
#   This project has twice been burned by the same thing:
#     * editing RTL but rebuilding only SOME testbenches -> drawing conclusions
#       from a stale .vvp;
#     * calling iverilog through a PowerShell function with array splatting,
#       which printed success but never actually rebuilt anything.
#   So "compile + check timestamps" is frozen into one script. After it runs,
#   every .vvp is compared against the newest .v: anything older is flagged.
#
# ASCII ONLY: Windows PowerShell 5.1 reads a BOM-less UTF-8 .ps1 as ANSI and
#   mangles non-ASCII text into a parse error. Keep this file ASCII.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_sims.ps1

# NOTE: iverilog writes warnings to stderr; with ErrorActionPreference=Stop
#       PowerShell turns that into a terminating NativeCommandError. Keep
#       'Continue' and filter for real errors instead.
$ErrorActionPreference = 'Continue'
$iverilog = 'D:\iverilog\bin\iverilog.exe'
if (-not (Test-Path $iverilog)) { Write-Error "iverilog not found: $iverilog" }

$RTL = 'src\rtl'

$S_COMMON = @("$RTL\osc_env.v", "$RTL\tdm_engine.v", "$RTL\pitch_mod.v")
$S_TOP = @(
  "$RTL\audio_clk_en.v", "$RTL\osc_env.v", "$RTL\i2s_tx.v", "$RTL\tdm_engine.v",
  "$RTL\pitch_mod.v", "$RTL\note_map.v", "$RTL\reg_bank.v", "$RTL\uart_rx.v", "$RTL\uart_tx.v",
  "$RTL\fx_delay.v", "$RTL\song_seq.v", "$RTL\pad_scan.v", "$RTL\tdm_top.v",
    "$RTL\pad_pitch.v", "$RTL\strip_ctrl.v", "$RTL\led_ind.v"
)
$S_PAR = @("$RTL\osc_core.v", "$RTL\osc_env.v", "$RTL\osc_additive.v", "$RTL\mixer.v", "$RTL\synth_top.v")
$S_NM = @("$RTL\osc_core.v", "$RTL\osc_env.v", "$RTL\tdm_engine.v", "$RTL\pitch_mod.v", "$RTL\note_map.v")

$targets = @(
  @{ n = 'R0 tdm_equiv'; o = 'sim_build\_recheck\tdm.vvp';     t = 'tb_tdm_equiv';   s = ($S_PAR + @("$RTL\tdm_engine.v", "$RTL\pitch_mod.v", 'src\sim\tb_tdm_equiv.v')) },
  @{ n = '128 pitch_mod'; o = 'sim_build\pitchmod\pm.vvp';     t = 'tb_pitch_mod';   s = ($S_COMMON + @("$RTL\note_map.v", 'src\sim\tb_pitch_mod.v')) },
  @{ n = '512 pitch_mod'; o = 'sim_build\pitchmod512\pm512.vvp'; t = 'tb_pitch_mod512'; s = ($S_COMMON + @("$RTL\note_map.v", 'src\sim\tb_pitch_mod512.v')) },
  @{ n = 'reg ctl';      o = 'sim_build\latency\rc.vvp';       t = 'tb_reg_ctl';     s = ($S_TOP + @('src\sim\tb_reg_ctl.v')) },
  @{ n = 'power-on VP7'; o = 'sim_build\vp7\vp7.vvp';         t = 'tb_vp7';         s = ($S_TOP + @('src\sim\tb_vp7.v')) },
  @{ n = 'top e2e';      o = 'sim_build\_recheck\top3.vvp';    t = 'tb_tdm_top';     s = ($S_TOP + @('src\sim\tb_tdm_top.v')) },
  @{ n = 'latency';      o = 'sim_build\latency\lat.vvp';      t = 'tb_latency';     s = ($S_TOP + @('src\sim\tb_latency.v')) },
  @{ n = 'note_map';     o = 'sim_build\_recheck\nm2.vvp';     t = 'tb_note_map';    s = ($S_NM + @('src\sim\tb_note_map.v')) },
  @{ n = 'note_music';   o = 'sim_build\_recheck\mu2.vvp';     t = 'tb_note_music';  s = ($S_NM + @('src\sim\tb_note_music.v')) },
  @{ n = 'tdm_demo';     o = 'sim_build\_recheck\dm2.vvp';     t = 'tb_tdm_demo';    s = ($S_NM + @('src\sim\tb_tdm_demo.v')) },
  @{ n = 'sequencer';    o = 'sim_build\seq\seq.vvp';         t = 'tb_seq';         s = @("$RTL\song_seq.v", 'src\sim\tb_seq.v') },
  @{ n = 'fx ir';        o = 'sim_build\fx\fx.vvp';           t = 'tb_fx';          s = @("$RTL\fx_delay.v", 'src\sim\tb_fx.v') },
  @{ n = 'e8 protocol';  o = 'sim_build\e8\e8.vvp';           t = 'tb_e8';          s = ($S_TOP + @('src\sim\tb_e8.v')) },
  @{ n = 'interaction';  o = 'sim_build\perf\perf.vvp';       t = 'tb_perf';        s = ($S_TOP + @("$RTL\perf_ctrl.v", 'src\sim\sensor_sim.v', 'src\sim\tb_perf.v')) },
  @{ n = 'fx sign/x';    o = 'sim_build\audio\fxinit.vvp';    t = 'tb_fxinit';      s = ($S_TOP + @('src\sim\tb_fxinit.v')) },
  @{ n = 'nyquist';      o = 'sim_build\nyq\nyq.vvp';         t = 'tb_nyq';         s = ($S_TOP + @('src\sim\tb_nyq.v')) },
  @{ n = 'event vp6';    o = 'sim_build\ev\ev.vvp';         t = 'tb_ev';          s = ($S_TOP + @('src\sim\tb_ev.v')) },
  @{ n = 'pad scan';     o = 'sim_build\pad\pad.vvp';       t = 'tb_pad';         s = (@("$RTL\pad_scan.v", 'src\sim\tb_pad.v')) },
  @{ n = 'pad ps4 inc';  o = 'sim_build\padtop\pt.vvp';     t = 'tb_padtop';      s = ($S_TOP + @('src\sim\tb_padtop.v')) },
  @{ n = 'spectrum vp';  o = 'sim_build\vp\vp.vvp';         t = 'tb_vp';          s = ($S_TOP + @('src\sim\tb_vp.v')) },
  @{ n = 'pad harm vp5'; o = 'sim_build\ps5\ps5.vvp';       t = 'tb_ps5';         s = ($S_TOP + @('src\sim\tb_ps5.v')) },
  @{ n = 'pad telemetry'; o = 'sim_build\padmon\pm.vvp';    t = 'tb_padmon';      s = ($S_TOP + @('src\sim\tb_padmon.v')) },
  @{ n = 'reverb t60';   o = 'sim_build\t60\t60.vvp';       t = 'tb_t60';         s = (@("$RTL\fx_delay.v", "$RTL\reg_bank.v", "$RTL\uart_rx.v", 'src\sim\tb_t60.v')) }
)
$fail = 0
foreach ($tg in $targets) {
    $a = @('-g2005', '-DSIM_INIT', '-o', $tg.o, '-s', $tg.t) + $tg.s
    $out = & $iverilog @a 2>&1
    $err = $out | Select-String -Pattern '\berror\b'
    if ($err) {
        Write-Output ("FAIL {0}" -f $tg.n)
        $err | Select-Object -First 4 | ForEach-Object { Write-Output ("     " + $_) }
        $fail = $fail + 1
    }
    else {
        Write-Output ("ok   {0}" -f $tg.n)
    }
}

Write-Output ""
Write-Output "=== timestamp check: every .vvp must be newer than every .v ==="
$newest = Get-ChildItem "$RTL\*.v", 'src\sim\*.v' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Output ("newest source: {0}  {1}" -f $newest.Name, $newest.LastWriteTime)

$stale = 0
foreach ($tg in $targets) {
    if (Test-Path $tg.o) {
        $v = Get-Item $tg.o
        if ($v.LastWriteTime -lt $newest.LastWriteTime) {
            $stale = $stale + 1
            Write-Output ("  {0,-16} {1}  STALE" -f $tg.n, $v.LastWriteTime)
        }
        else {
            Write-Output ("  {0,-16} {1}  ok" -f $tg.n, $v.LastWriteTime)
        }
    }
}
if ($stale -gt 0) { Write-Output ("WARNING: {0} stale vvp -- do not use their data" -f $stale) }
if ($fail -gt 0) { Write-Output ("ERROR: {0} compile failures" -f $fail); exit 1 }
exit 0
