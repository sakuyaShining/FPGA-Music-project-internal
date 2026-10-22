# -*- coding: utf-8 -*-
"""
回归测试：实时演奏模式必须做到【按下发声 / 松开收声】。

背景（这个测试为什么存在）
---------------------------------------------------------------
早期版本用 msvcrt.getch() 读键盘。它只在按键【按下】时返回字符，
【松开时不产生任何事件】—— 所以"松手就停"根本无法实现。
结果：音符进入 sustain 后永远不停，弹一下就响到被抢占为止。
用户当时的反馈是"为什么弹出来的音频会一直响"。

本测试不依赖真人按键：
  · 用"按时间轴回放"的假 ConsoleKeyReader 注入按下/松开事件
  · 用假 sounddevice 在后台线程按真实速率驱动真实的 cmd_play 音频回调
  · 逐块记录输出峰值，断言"松开之后必须静音"
这个 bug 一旦复发，跑一次测试就能抓到。
"""
import os
import sys
import time
import types
import argparse
import threading

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import synth_engine as S            # noqa: E402

FS = 48000
BLK = 512
BLK_S = BLK / float(FS)             # 每块约 10.667 ms
ESC = '\x1b'


# ---------------------------------------------------------------- 假音频设备
class FakeStream:
    """替身 sounddevice.OutputStream：后台线程按真实速率跑音频回调。"""

    def __init__(self, samplerate=None, channels=2, dtype=None,
                 blocksize=None, callback=None, **kw):
        self.cb = callback
        self.channels = channels or 2
        # 记 (墙上时间, 该块峰值)。不能只用下标 —— 回调本身的耗时会让
        # 线程周期略长于 BLK_S，块下标和真实时间会越差越远。
        self.marks = []
        self._run = False
        self._th = None
        self._t0 = None

    def start(self):
        self._run = True
        self._t0 = time.time()
        self._out = np.zeros((BLK, self.channels), dtype=np.float32)
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    def _loop(self):
        # 按"已渲染样本数"对齐墙上时间。
        # 不能简单地 sleep(BLK_S)：Windows 上 sleep 的实际粒度会让线程跑得比实时慢，
        # 于是"音频时间"和"墙上时间"越差越远，按秒断言的窗口就全错位了。
        n = 0
        while self._run:
            self._out.fill(0.0)
            try:
                self.cb(self._out, BLK, None, None)
            except Exception:
                pass
            # 用音频时刻(样本数/采样率)而不是墙上时刻做标记
            self.marks.append((n / float(FS),
                               float(np.max(np.abs(self._out)))))
            n += BLK
            target = self._t0 + n / float(FS)
            while self._run:
                d = target - time.time()
                if d <= 0.0:
                    break
                time.sleep(min(d, 0.002))

    def stop(self):
        self._run = False
        if self._th is not None:
            self._th.join(timeout=1.0)

    def close(self):
        pass

    def peak_between(self, t0, t1):
        seg = [p for (t, p) in self.marks if t0 <= t < t1]
        return max(seg) if seg else 0.0

    @property
    def peaks(self):
        return [p for (_, p) in self.marks]


# ------------------------------------------------------- 假按键读取器（回放）
class ScriptedReader:
    """按墙上时间回放脚本事件。ok=True 表示"能拿到松开事件"。"""

    def __init__(self, script, ok=True, deadline=None):
        self.script = script        # [(t, 字符, 是否按下), ...]
        self.ok = ok
        self.deadline = deadline
        self.i = 0
        self.t0 = None
        self._esc = False

    def close(self):
        pass

    def poll(self):
        if self.t0 is None:
            self.t0 = time.time()
        now = time.time() - self.t0
        out = []
        while self.i < len(self.script) and self.script[self.i][0] <= now:
            _, ch, down = self.script[self.i]
            out.append((ch, down, 0))
            self.i += 1
        # 安全阀：脚本放完后如果主循环还没退出，补一个 ESC，避免测试挂死
        if (not out and self.i >= len(self.script) and not self._esc
                and self.deadline is not None and now > self.deadline):
            self._esc = True
            out.append((ESC, True, 0))
        return out


# ------------------------------------------------------------------ 驱动一次
def drive(script, ok=True, total_s=2.0, patch_msvcrt=None):
    """跑一次真实的 cmd_play，返回 (假音频流, 新建声部计数)。"""
    box = {}

    class Cap(FakeStream):
        def __init__(self, **kw):
            FakeStream.__init__(self, **kw)
            box['s'] = self

    fake_sd = types.ModuleType('sounddevice')
    fake_sd.OutputStream = Cap
    sys.modules['sounddevice'] = fake_sd

    created = []
    orig_init = S.Voice.__init__

    def spy(self, *a, **k):
        created.append(1)
        return orig_init(self, *a, **k)

    orig_reader = S.ConsoleKeyReader
    S.Voice.__init__ = spy
    S.ConsoleKeyReader = lambda: ScriptedReader(script, ok=ok, deadline=total_s)
    undo = None
    if patch_msvcrt is not None:
        import msvcrt
        undo = (msvcrt.kbhit, msvcrt.getch)
        msvcrt.kbhit, msvcrt.getch = patch_msvcrt
    try:
        rc = S.cmd_play(argparse.Namespace(fs=FS))
    finally:
        S.Voice.__init__ = orig_init
        S.ConsoleKeyReader = orig_reader
        if undo is not None:
            import msvcrt
            msvcrt.kbhit, msvcrt.getch = undo
    return box['s'], created, rc


# ------------------------------------------------------------------ 测试本体
def main():
    print("=" * 64)
    print("  回归测试: 实时演奏的【松手收声】")
    print("=" * 64)
    failures = []

    def check(cond, msg):
        print("    %s %s" % ("[OK]  " if cond else "[FAIL]", msg))
        if not cond:
            failures.append(msg)

    # ---------------- 用例 1: 按下 -> 松开 -> 再按 -> 松开 ----------------
    # 先用 '3' 把释放长度压到最短档(0.10 s)，让窗口断言不依赖默认值。
    # 注意 '3' 必须在起音之前按 —— 释放长度是在建声部时传给它的。
    script1 = [
        (0.00, '3', True), (0.02, '3', True), (0.04, '3', True), (0.06, '3', True),
        (0.10, 'a', True),
        (0.15, 'a', True),      # 系统自动重复，必须被忽略
        (0.20, 'a', True),      # 自动重复
        (0.25, 'a', True),      # 自动重复
        (0.50, 'a', False),     # 松手 -> 0.10 s 后静音(约 0.63 s)
        (0.95, 's', True),
        (1.30, 's', False),     # 松手 -> 约 1.43 s 静音
    ]
    st, created, _ = drive(script1, total_s=1.85)
    print("\n  用例1 按下→松开→再按→松开   共 %d 块音频, 新建声部 %d 个"
          % (len(st.peaks), len(created)))
    check(st.peak_between(0.25, 0.45) > 0.05,
          "按住期间有声音 (峰值 %.3f)" % st.peak_between(0.25, 0.45))
    check(st.peak_between(0.75, 0.90) == 0.0,
          "★ 第一次松手后已静音 (峰值 %.3f)" % st.peak_between(0.75, 0.90))
    check(st.peak_between(1.05, 1.25) > 0.05,
          "第二次按下又有声音 (峰值 %.3f)" % st.peak_between(1.05, 1.25))
    check(st.peak_between(1.55, 1.80) == 0.0,
          "★ 第二次松手后已静音 (峰值 %.3f)" % st.peak_between(1.55, 1.80))
    check(len(created) == 2,
          "自动重复被忽略: 4 次按下只建了 2 个声部 (实际 %d)" % len(created))

    # ---------------- 用例 2: 余韵（不松手也自然消失）----------------
    script2 = [
        (0.00, 'a', True),      # 按住不放
        (0.03, '2', True), (0.06, '2', True), (0.09, '2', True),
        (0.12, '2', True), (0.15, '2', True),   # 余韵 -> 0.25 s
    ]
    st2, _, _ = drive(script2, total_s=1.10)
    print("\n  用例2 短余韵: 击发后自然消失   共 %d 块音频" % len(st2.peaks))
    check(st2.peak_between(0.16, 0.24) > 0.02,
          "改余韵瞬间还在响 (峰值 %.3f)" % st2.peak_between(0.16, 0.24))
    check(st2.peak_between(0.70, 1.00) == 0.0,
          "余韵走完后静音，尽管键还按着 (峰值 %.3f)" % st2.peak_between(0.70, 1.00))

    # ---------------- 用例 3: 退化模式也要有兜底 ----------------
    t0 = [time.time()]
    state = {'n': 0}

    def fake_kbhit():
        if state['n'] == 0:
            return True
        return (time.time() - t0[0]) > 2.90

    def fake_getch():
        if state['n'] == 0:
            state['n'] = 1
            return b'a'
        return ESC.encode()

    st3, _, _ = drive([], ok=False, total_s=9.0,
                      patch_msvcrt=(fake_kbhit, fake_getch))
    print("\n  用例3 退化模式(拿不到松开事件)   共 %d 块音频" % len(st3.peaks))
    check(st3.peak_between(0.05, 1.20) > 0.05,
          "退化模式仍然能发声 (峰值 %.3f)" % st3.peak_between(0.05, 1.20))
    check(st3.peak_between(2.15, 2.85) == 0.0,
          "★ 退化模式兜底自动收声 (峰值 %.3f)" % st3.peak_between(2.15, 2.85))

    print()
    if failures:
        print("  [FAIL] %d 项未通过:" % len(failures))
        for f in failures:
            print("         - " + f)
        return 1
    print("  [PASS] 松手收声 / 自动重复抑制 / 余韵 / 退化兜底 全部通过")
    return 0


if __name__ == '__main__':
    sys.exit(main())
