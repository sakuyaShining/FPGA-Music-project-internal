@echo off
REM ===========================================================================
REM  play.cmd -- 用键盘实时演奏加法合成引擎
REM
REM  操作说明（进入后屏幕上也会显示）：
REM    A S D F G H J K L ;   白键：C D E F G A B C D E
REM    W E T Y U             黑键
REM    Z / X                 八度 -/+
REM    [ / ]                 谱宽：参与发声的泛音数 1..8
REM    - / =                 谱心：泛音衰减快慢（= 更暗，- 更亮）
REM    , / .                 非谐度：0=管风琴音色  1=钟声
REM    1 / 2                 余韵：1=更持续(0=按住一直响)  2=更短(0.25s 打击感)
REM    3 / 4                 释放长度：松手后余音留多久  0.10s ── 1.30s（默认 0.40s）
REM    0                     淡出曲线：指数(自然渐弱) ⇄ 线性(旧行为，末端像被切断)
REM    ESC                   退出
REM
REM  ★ 按住琴键发声，松开即收声。
REM    这里用 ReadConsoleInputW 拿的是【按下 + 抬起】两种事件。
REM    旧版用 msvcrt.getch() —— 它只有按下、没有抬起，
REM    于是音符进了 sustain 就永远不停，弹一下会一直响。
REM    回归测试：python tools\scripts\test_play_release.py
REM
REM  这个引擎与 src\rtl\osc_additive.v **逐位一致**（已验证 0 个样本差异），
REM  所以你听到的，就是 RTL 综合到 FPGA 后会发出的声音。
REM ===========================================================================
setlocal
chcp 65001 >nul

set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\tools\pylib"
set "PYTHONIOENCODING=utf-8"

echo.
echo   正在启动实时演奏引擎...
echo   （第一次启动需要 1-2 秒初始化音频设备）
echo.

python "%ROOT%\tools\scripts\synth_engine.py" play --fs 48000
if errorlevel 1 (
    echo.
    echo [出错] 启动失败。可能的原因：
    echo   1. 没有可用的音频输出设备
    echo   2. sounddevice 的 DLL 缺失（检查 tools\pylib\_sounddevice_data\）
    echo.
    pause
)
endlocal
