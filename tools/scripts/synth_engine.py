#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synth_engine.py -- 加法合成引擎（与 Verilog RTL 逐位一致）

三个用途：
  verify  逐位比对：证明本模型与 src/rtl/osc_additive.v 的仿真输出完全一致
  demo    渲染长音频（几十秒）到 WAV，可以直接听
  play    实时键盘演奏（用电脑声卡，第一次"弹"这个引擎）

之所以要做到"逐位一致"：
  这样才能说"你在电脑上听到的，就是 RTL 会发出的声音"。
  否则就只是"一个听起来差不多的软件合成器"，与本项目无关。

RTL 行为（src/rtl/osc_additive.v）：
  · 8 个独立 24 位相位累加器
  · 正弦表 256 项 × 16 bit（Q1.15），来自 sine256.hex
  · 每个泛音贡献 = (sine_tab[phase >> 16] * amp) >> 8      （算术右移）
  · 求和后饱和到 ±(2^23)
  · 每个时钟推进一次相位，输出样本 = f(推进前的相位)

采样率：
  RTL 仿真用 fs = 50 kHz（1 时钟 = 1 样本）
  实时演奏用声卡采样率（通常 48 kHz）—— 只是 inc 值不同，算法完全一样
"""
import argparse
import json
import os
import sys
import time
import wave

import numpy as np

# ------------------------------------------------------------------ 常量
PHASE_W = 24
PHASE_MASK = (1 << PHASE_W) - 1
TAB_AW = 8
TAB_N = 1 << TAB_AW
OUT_MIN = -(1 << 23)
OUT_MAX = (1 << 23) - 1

NUM_PARTIALS = 8
AMP_MAX = 255

# 谐波比例（1..8 次谐波）
RATIOS_HARMONIC = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
# 非谐波比例（第 3 个泛音改成 2.76 倍，钟/锣类）
RATIOS_INHARMONIC = [1.0, 2.0, 2.76, 4.0, 5.0, 6.0, 7.0, 8.0]
# 各泛音幅度（0..255），约 1/n 衰减
AMPS_DEFAULT = [200, 120, 80, 60, 45, 36, 30, 26]


def build_sine_table():
    """与 Python 生成 sine256.hex 时完全相同的算法"""
    i = np.arange(TAB_N)
    v = np.round(32767.0 * np.sin(2 * np.pi * i / TAB_N)).astype(np.int64)
    return np.clip(v, -32768, 32767).astype(np.int64)


def load_sine_table(path):
    """从 .hex 文件读表（与 $readmemh 等价）"""
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            v = int(line, 16)
            if v >= 0x8000:
                v -= 0x10000
            vals.append(v)
    return np.array(vals, dtype=np.int64)


def freq_to_inc(f_hz, fs):
    return int(round(f_hz * (1 << PHASE_W) / fs))


# ------------------------------------------------------------------ 核心渲染
class AdditiveEngine:
    """
    与 RTL 逐位一致的加法合成核心。
    只负责"给定相位与参数，算出样本"；发声管理（包络/声部）在外面。
    """

    def __init__(self, sine_tab, fs):
        self.tab = sine_tab
        self.fs = fs

    def render(self, phase, inc, amp, n_samples):
        """
        phase : (P,) int64  当前相位（每个泛音一个）
        inc   : (P,) int64  频率增量
        amp   : (P,) int64  幅度 0..255
        n     : 样本数
        返回 (out, new_phase)
        """
        p = phase.shape[0]
        # 每个样本的相位：phase + n*inc  （模 2^24）
        n = np.arange(n_samples, dtype=np.int64)
        ph = (phase[:, None] + inc[:, None] * n[None, :]) & PHASE_MASK   # (P, N)
        idx = ph >> (PHASE_W - TAB_AW)                                   # 高 8 位做表地址
        s = self.tab[idx]                                                # (P, N)
        # amp 可以是 (P,) 固定值，也可以是 (P, N) 逐样本变化（用于幅度斜坡）
        if amp.ndim == 1:
            contrib = (s * amp[:, None]) >> 8
        else:
            contrib = (s * amp) >> 8
        out = contrib.sum(axis=0)
        out = np.clip(out, OUT_MIN, OUT_MAX)
        new_phase = (phase + inc * n_samples) & PHASE_MASK
        return out.astype(np.int64), new_phase


# ------------------------------------------------------------------ verify
def cmd_verify(args):
    """把模型输出与 RTL 仿真 dump 的样本逐位比对"""
    print("=== 逐位一致性验证 ===")
    meta = json.load(open(args.meta))
    fs = meta["fs"]

    tab_file = os.path.join(args.simdir, "sine256.hex")
    tab = load_sine_table(tab_file)
    eng = AdditiveEngine(tab, fs)

    inc_h = np.array(meta["inc_harmonic"], dtype=np.int64)
    inc_i = np.array(meta["inc_inharmonic"], dtype=np.int64)
    amp = np.array(meta["amps"], dtype=np.int64)
    n = meta["n_samples"]

    # 按 RTL 时序：第 m 个输出样本 = f(m * inc)
    phase0 = np.zeros(NUM_PARTIALS, dtype=np.int64)

    all_ok = True
    for tag, inc in (("harmonic", inc_h), ("inharmonic", inc_i)):
        rtl_path = os.path.join(args.simdir, "samples_%s.txt" % tag)
        rtl = np.array([int(x) for x in open(rtl_path) if x.strip()], dtype=np.int64)
        m = min(len(rtl), n)

        # RTL 的输出与模型之间可能有两处错位，都要扫出来：
        #   ① 起始相位：RTL 复位序列会多推进几拍 → 用 "起始相位 = k × inc" 补偿
        #   ② 流水线填充：v2 版 RTL 有 6 级流水线，输出开头是一串 0 → 跳过 skip 个样本
        # 只扫其中一个是不够的（加了流水线之后就匹配不上了）。
        K = min(len(rtl), n, 3000)
        best = None
        for skip in range(0, 14):
            if skip + K > len(rtl):
                break
            for k in range(0, 14):
                ph0 = (inc * k) & PHASE_MASK
                model, _ = eng.render(ph0, inc, amp, K)
                d = int(np.count_nonzero(model - rtl[skip:skip + K]))
                if best is None or d < best[2]:
                    best = (skip, k, d)
                    if d == 0:
                        break
            if best is not None and best[2] == 0:
                break
        skip0, k0, _ = best

        ph0 = (inc * k0) & PHASE_MASK
        model, _ = eng.render(ph0, inc, amp, m - skip0)
        rtl_cmp = rtl[skip0:m]

        diff = model - rtl_cmp
        nz = int(np.count_nonzero(diff))
        maxd = int(np.max(np.abs(diff))) if len(diff) else 0

        print("  测试 %-11s : RTL %d 样本 / 模型 %d 样本" % (tag, len(rtl), len(model)))
        print("                 流水线填充 = %d 个样本（跳过）" % skip0)
        print("                 起始相位补偿 = %d × inc" % k0)
        print("                 不一致样本数 = %d   最大差异 = %d" % (nz, maxd))
        if nz != 0:
            bad = np.nonzero(diff)[0][:5]
            for b in bad:
                print("                 样本[%d]: RTL=%d 模型=%d" % (b, rtl_cmp[b], model[b]))
            all_ok = False

    print()
    if all_ok:
        print("  [PASS] Python 模型与 Verilog RTL **逐位完全一致**")
        print("         => 你在电脑上听到的，就是 RTL 会发出的声音")
    else:
        print("  [FAIL] 存在不一致，模型不能代表 RTL")
    return 0 if all_ok else 1


# 包络结束后归零的阈值。
# 指数淡出是渐近的，永远到不了 0，必须显式定一个"到此为止"的门槛。
# 门槛定得太高（例如 -60 dB）会在收尾留下一个几十 LSB 的台阶 —— 安静环境下
# 能听到极轻的"嗒"。取 -80 dB(1e-4)，16 bit 下只有约 3 个 LSB，听不出来。
ENV_CUTOFF = 1e-4


# ------------------------------------------------------------------ 发声管理
class Voice:
    """
    一个声部：8 个泛音 + 一个包络。

    ★ 支持【演奏中途】改变频谱参数 —— 这是"塑谱"这个产品概念的核心。
      · 频率改：立即生效，且相位连续（不会咔哒）
      · 幅度改：用约 10 ms 的线性斜坡过渡（直接跳变会有咔哒声）
    """

    def __init__(self, engine, f0, ratios, amps, fs):
        self.eng = engine
        self.fs = fs
        self.f0 = f0

        # 当前值 / 目标值 分离 —— 目标值由 set_spectrum() 更新
        self.ratio   = np.array(ratios, dtype=np.float64)
        self.ratio_t = self.ratio.copy()
        self.amp     = np.array(amps, dtype=np.float64)
        self.amp_t   = self.amp.copy()

        self.phase = np.zeros(NUM_PARTIALS, dtype=np.int64)
        self._recalc_inc()

        self.active = True
        self.attack = int(0.006 * fs)
        # release_s 的含义是"指数淡出到 -60 dB 所用的时间"，也就是听感上的释放长度。
        # 之后还会继续衰到 ENV_CUTOFF(-80 dB) 才归零，实际尾巴约为 1.33 × release_s。
        # 200 ms 太短：指数是匀速掉 dB，-14 dB/50 ms 意味着从满音量到听不见只要 70 ms，
        # 听感就是"一松手就没了"。默认给 400 ms。
        self.release_s = 0.40
        self.release_len = max(1, int(self.release_s * fs))
        self.env = 0.0
        self.stage = "attack"     # attack -> sustain -> release -> done
        self.gain = 1.0
        self.ramp_len = max(1, int(0.010 * fs))    # 幅度斜坡 10 ms

        # 余韵：sustain 阶段若 decay<1，包络会自己往下掉。
        # 1.0 = 不衰减（按键按住就一直响，松开才收声）—— 弦乐/管风琴
        # <1.0 = 打击/弹拨/钟：一次击发后自然消失，不需要松手
        self.decay = 1.0

        # 释放曲线：
        #   "exp" = 指数淡出。每样本乘固定系数 → 每秒固定掉多少 dB，听感均匀自然。
        #           钢琴/钟/吉他的自然衰减都是这个形状。
        #   "lin" = 线性淡出。每样本减固定量 → 前 100 ms 只掉 6 dB，最后 50 ms
        #           掉 26 dB，听感像"松开就被一刀切断"。这是旧行为，保留用于对比。
        self.curve = "exp"
        self._calc_r_coef()

    def _calc_r_coef(self):
        """指数淡出系数：release_len 个样本内衰到 -60 dB（千分之一）"""
        self.r_coef = 0.001 ** (1.0 / max(1.0, float(self.release_len)))

    def set_release_seconds(self, sec):
        """设置释放长度（指衰到 -60 dB 的时间，也就是听感上的释放长度）"""
        self.release_s = float(sec)
        self.release_len = max(1, int(self.release_s * self.fs))
        self._calc_r_coef()

    def set_curve(self, curve):
        """切换释放曲线："exp" 指数 / "lin" 线性"""
        if curve in ("exp", "lin"):
            self.curve = curve

    def set_decay_seconds(self, sec):
        """
        余韵长度 sec 秒（包络衰到 -60 dB 所需时间）。
        sec 为 None 或 <=0 表示【不衰减】—— 持续音，靠松开按键收声。
        """
        if sec is None or sec <= 0:
            self.decay = 1.0
        else:
            # 0.001 ** (1/N) 就是"每采样乘这么多，乘 N 次后到千分之一"
            self.decay = 0.001 ** (1.0 / max(1.0, sec * self.fs))

    def _recalc_inc(self):
        self.inc = np.array([freq_to_inc(self.f0 * r, self.fs) for r in self.ratio],
                            dtype=np.int64)

    def set_spectrum(self, ratios=None, amps=None):
        """演奏中途更新频谱（这一步就是"塑谱"）"""
        if ratios is not None:
            self.ratio_t = np.array(ratios, dtype=np.float64)
            self.ratio = self.ratio_t.copy()
            self._recalc_inc()
        if amps is not None:
            self.amp_t = np.array(amps, dtype=np.float64)

    def render(self, n):
        # ---- 幅度斜坡：从当前值滑向目标值 ----
        if not np.array_equal(self.amp, self.amp_t):
            r = np.minimum(1.0, (np.arange(n, dtype=np.float64) + 1.0) / self.ramp_len)
            amp_m = self.amp[:, None] * (1.0 - r)[None, :] + self.amp_t[:, None] * r[None, :]
            self.amp = amp_m[:, -1].copy()
            amp_in = np.clip(np.round(amp_m), 0, AMP_MAX).astype(np.int64)
        else:
            amp_in = np.clip(np.round(self.amp), 0, AMP_MAX).astype(np.int64)

        x, self.phase = self.eng.render(self.phase, self.inc, amp_in, n)

        # ---- 包络（向量化，避免逐样本 python 循环）----
        e = self._env_block(n)

        return x.astype(np.float64) * e * self.gain

    def _env_block(self, n):
        """向量化包络生成。用 guard 防止状态机卡死。"""
        e = np.zeros(n, dtype=np.float64)
        i = 0
        a_step = 1.0 / max(1, self.attack)
        r_step = 1.0 / max(1, self.release_len)
        guard = 0
        while i < n and guard < 8:
            guard += 1
            if self.stage == "attack":
                if self.env >= 1.0:
                    self.stage = "sustain"
                    continue
                cnt = int(np.ceil((1.0 - self.env) / a_step))
                cnt = max(1, min(n - i, cnt))
                seg = np.minimum(self.env + a_step * np.arange(1, cnt + 1), 1.0)
                e[i:i + cnt] = seg
                self.env = float(seg[-1])
                i += cnt
            elif self.stage == "sustain":
                k = n - i
                if self.decay < 1.0 and self.env > 0.0:
                    seg = self.env * (self.decay ** np.arange(1, k + 1))
                    e[i:] = seg
                    self.env = float(seg[-1])
                    if self.env < 1e-4:          # 已经听不见了，直接收工
                        self.env = 0.0
                        self.stage = "done"
                else:
                    e[i:] = self.env
                i = n
            elif self.stage == "release":
                if self.env <= 0.0:
                    self.stage = "done"
                    continue
                k = n - i
                if self.curve == "exp":
                    # ---- 指数淡出：每样本乘固定系数 ----
                    # 听感上"每秒掉固定 dB"，均匀自然，末端不会有可闻的硬停。
                    seg = self.env * (self.r_coef ** np.arange(1, k + 1))
                    e[i:] = seg
                    self.env = float(seg[-1])
                    # r_coef 的定义是"release_len 个样本后衰到 -60 dB(1e-3)"。
                    # 但要继续衰到 ENV_CUTOFF(-80 dB) 才归零，否则收尾会留台阶。
                    if self.env < ENV_CUTOFF:
                        self.env = 0.0
                        self.stage = "done"
                    i = n
                else:
                    # ---- 线性淡出：每样本减固定量（旧行为，用于对比）----
                    cnt = int(np.ceil(self.env / r_step))
                    cnt = max(1, min(k, cnt))
                    seg = np.maximum(self.env - r_step * np.arange(1, cnt + 1), 0.0)
                    e[i:i + cnt] = seg
                    self.env = float(seg[-1])
                    i += cnt
            else:                       # done
                e[i:] = 0.0
                i = n
        if self.stage == "done":
            self.active = False
        return e

    def start_release(self):
        if self.stage != "release":
            self.stage = "release"

    def start_fast_release(self, ms=4.0):
        """被抢占时用快速淡出，避免硬切造成的咔哒声"""
        self.stage = "release"
        self.release_len = max(1, int(ms / 1000.0 * self.fs))
        self._calc_r_coef()


# ------------------------------------------------------------------ demo
NOTE_BASE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_hz(name, octave):
    """音名 -> 频率（A4 = 440 Hz）"""
    semi = NOTE_BASE[name] + (octave - 4) * 12 - 9   # 相对 A4
    return 440.0 * (2.0 ** (semi / 12.0))


def cmd_demo(args):
    """渲染长音频到 WAV"""
    fs = args.fs
    tab = build_sine_table()
    eng = AdditiveEngine(tab, fs)
    os.makedirs(args.outdir, exist_ok=True)

    # ---------- 曲目 1：小星星（展示一个音色下的完整旋律）----------
    # (音名, 八度, 拍数)
    twinkle = [
        ("C", 5, 1), ("C", 5, 1), ("G", 5, 1), ("G", 5, 1),
        ("A", 5, 1), ("A", 5, 1), ("G", 5, 2),
        ("F", 5, 1), ("F", 5, 1), ("E", 5, 1), ("E", 5, 1),
        ("D", 5, 1), ("D", 5, 1), ("C", 5, 2),
        ("G", 5, 1), ("G", 5, 1), ("F", 5, 1), ("F", 5, 1),
        ("E", 5, 1), ("E", 5, 1), ("D", 5, 2),
        ("G", 5, 1), ("G", 5, 1), ("F", 5, 1), ("F", 5, 1),
        ("E", 5, 1), ("E", 5, 1), ("D", 5, 2),
        ("C", 5, 1), ("C", 5, 1), ("G", 5, 1), ("G", 5, 1),
        ("A", 5, 1), ("A", 5, 1), ("G", 5, 2),
        ("F", 5, 1), ("F", 5, 1), ("E", 5, 1), ("E", 5, 1),
        ("D", 5, 1), ("D", 5, 1), ("C", 5, 4),
    ]
    render_song(eng, fs, twinkle, bpm=110, out=os.path.join(args.outdir, "demo1_小星星_谐波音色.wav"),
                ratios=RATIOS_HARMONIC, amps=AMPS_DEFAULT, title="小星星 · 谐波音色")

    # ---------- 曲目 2：同一旋律，音色在谐波↔非谐之间渐变 ----------
    render_song(eng, fs, twinkle, bpm=110, out=os.path.join(args.outdir, "demo2_小星星_音色渐变.wav"),
                ratios=None, amps=AMPS_DEFAULT, title="小星星 · 音色从管风琴渐变到钟")

    # ---------- 曲目 3：一段长音，展示"泛音逐个进出" ----------
    render_spectral_sweep(eng, fs, out=os.path.join(args.outdir, "demo3_泛音逐个进出.wav"))

    print()
    print("渲染完成，输出目录:", args.outdir)
    for f in sorted(os.listdir(args.outdir)):
        if f.endswith(".wav"):
            p = os.path.join(args.outdir, f)
            with wave.open(p, "rb") as w:
                dur = w.getnframes() / w.getframerate()
            print("  %-38s %6.2f 秒" % (f, dur))
    return 0


def render_song(eng, fs, song, bpm, out, ratios, amps, title):
    """把音符序列渲染成 WAV；ratios=None 表示随时间在谐波↔非谐之间渐变"""
    beat = 60.0 / bpm
    # 计算总时长
    total_beats = sum(d for _, _, d in song) + 2
    n_total = int(total_beats * beat * fs) + fs // 2
    buf = np.zeros(n_total, dtype=np.float64)

    t = 0.0
    for idx, (name, octv, dur_beats) in enumerate(song):
        f0 = note_hz(name, octv)
        dur = dur_beats * beat
        n = int(dur * fs)
        pos = int(t * fs)
        if pos + n > n_total:
            n = n_total - pos
            if n <= 0:
                break

        # 音色：如果 ratios=None，则随曲目进度从纯谐波渐变到非谐
        if ratios is None:
            prog = idx / max(1, len(song) - 1)          # 0..1
            r3 = 3.0 + (2.76 - 3.0) * prog              # 第 3 泛音 3.00 -> 2.76
            r5 = 5.0 + (4.35 - 5.0) * prog              # 第 5 泛音 5.00 -> 4.35
            r7 = 7.0 + (6.10 - 7.0) * prog              # 第 7 泛音 7.00 -> 6.10
            rr = [1.0, 2.0, r3, 4.0, r5, 6.0, r7, 8.0]
        else:
            rr = ratios

        v = Voice(eng, f0, rr, amps, fs)
        v.attack = int(0.008 * fs)
        v.release_len = int(0.25 * fs)
        x = v.render(n)
        v.start_release()
        # 让释放自然延续到下一个音
        tail = int(0.25 * fs)
        if pos + n + tail <= n_total:
            v2 = Voice(eng, f0, rr, amps, fs)
            v2.phase = v.phase.copy()
            v2.env = v.env
            v2.stage = "release"
            v2.release_len = int(0.25 * fs)
            x2 = v2.render(tail)
            buf[pos:pos + n + tail] += np.concatenate([x, x2])
        else:
            buf[pos:pos + n] += x
        t += dur

    # 归一化
    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.85
    write_wav(out, buf, fs)
    print("  [demo] %-34s %.1f 秒" % (title, len(buf) / fs))


def render_spectral_sweep(eng, fs, out):
    """
    一个 12 秒长音：泛音从 1 个逐个加到 8 个，再逐个退回去。
    正好用来演示新加的 set_spectrum() —— 演奏中途改频谱，音高完全不动。
    （旧版这里有一段算完就丢的死代码，且把整段 8 泛音底噪与扫描段叠加，
      听起来不是"逐个进出"。现在改成单一 voice + 实时改幅度谱，语义正确了。）
    """
    dur = 12.0
    f0 = 220.0
    seg = 24
    segn = int(dur * fs) // seg
    n = segn * seg

    v = Voice(eng, f0, RATIOS_HARMONIC, [0] * NUM_PARTIALS, fs)
    v.attack = int(0.01 * fs)
    v.ramp_len = max(1, int(0.08 * fs))       # 80 ms 斜坡，让泛音进出更平滑

    buf = np.zeros(n, dtype=np.float64)
    for s in range(seg):
        frac = s / (seg - 1)                                   # 0 -> 1
        # 前一半逐个加入（1→8），后一半逐个退出（8→1）
        tri = frac * 2.0 if frac <= 0.5 else (1.0 - frac) * 2.0
        npart = 1 + int(round(tri * (NUM_PARTIALS - 1)))
        amps = [AMPS_DEFAULT[i] if i < npart else 0 for i in range(NUM_PARTIALS)]
        v.set_spectrum(amps=amps)
        buf[s * segn:(s + 1) * segn] = v.render(segn)

    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.85
    write_wav(out, buf, fs)
    print("  [demo] %-34s %.1f 秒" % ("泛音逐个进出（1→8→1 个泛音）", len(buf) / fs))


def write_wav(path, x, fs):
    y = np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(round(fs)))
        w.writeframes(y.tobytes())


# ------------------------------------------------------------------ play
KEYMAP = {
    'a': ("C", 5), 's': ("D", 5), 'd': ("E", 5), 'f': ("F", 5),
    'g': ("G", 5), 'h': ("A", 5), 'j': ("B", 5), 'k': ("C", 6),
    'l': ("D", 6), ';': ("E", 6),
    'w': ("C#", 5), 'e': ("D#", 5), 't': ("F#", 5),
    'y': ("G#", 5), 'u': ("A#", 5),
}


# ------------------------------------------------- 控制台按键（含"松开"事件）
# 为什么不用 msvcrt.getch()：
#   getch() 只在按键【按下】时返回一个字符，【松开时不产生任何事件】。
#   于是"松手就收声"根本无法实现 —— 音符会一直响到被抢占为止。
#   （这就是之前"弹一下响个不停"的根因。)
#
# ReadConsoleInputW 返回的 KEY_EVENT_RECORD 带有 bKeyDown 字段：
#   按下时为 True，松开时为 False，另外还有 wRepeatCount（系统自动重复计数）。
#   有了它，电子乐器该有的【按下发声 / 松开收声】才成立。
try:
    import ctypes
    from ctypes import wintypes as _wt

    class _CharUnion(ctypes.Union):
        _fields_ = [("UnicodeChar", ctypes.c_wchar),
                    ("AsciiChar", ctypes.c_char)]

    class _KeyEventRecord(ctypes.Structure):
        _fields_ = [("bKeyDown", _wt.BOOL),
                    ("wRepeatCount", _wt.WORD),
                    ("wVirtualKeyCode", _wt.WORD),
                    ("wVirtualScanCode", _wt.WORD),
                    ("uChar", _CharUnion),
                    ("dwControlKeyState", _wt.DWORD)]

    class _EventUnion(ctypes.Union):
        # 只需 KEY_EVENT 的大小/对齐；它与 MOUSE_EVENT 同为 16 字节，
        # 所以整个 INPUT_RECORD 的步长与 Windows 的一致（4 + 16 = 20）。
        _fields_ = [("KeyEvent", _KeyEventRecord)]

    class _InputRecord(ctypes.Structure):
        _fields_ = [("EventType", _wt.WORD),
                    ("Event", _EventUnion)]

    _KEY_EVENT              = 0x0001
    _STD_INPUT_HANDLE       = -10
    _ENABLE_PROCESSED_INPUT = 0x0001
    _ENABLE_LINE_INPUT      = 0x0002
    _ENABLE_ECHO_INPUT      = 0x0004
    _GENERIC_READ           = 0x80000000
    _GENERIC_WRITE          = 0x40000000
    _FILE_SHARE_READ        = 0x00000001
    _FILE_SHARE_WRITE       = 0x00000002
    _OPEN_EXISTING          = 3
    _FILE_TYPE_CHAR         = 2
    _INVALID_HANDLE         = ctypes.c_void_p(-1).value
    _HAS_CTYPES = True
except Exception:
    _HAS_CTYPES = False


def _parse_key_records(buf, count):
    """把 INPUT_RECORD 数组翻译成 [(字符, 是否按下, 虚拟键码), ...]。独立出来是为了能单测。"""
    out = []
    for i in range(count):
        rec = buf[i]
        if rec.EventType != _KEY_EVENT:
            continue
        ke = rec.Event.KeyEvent
        ch = ke.uChar.UnicodeChar or ''
        out.append((ch, bool(ke.bKeyDown), int(ke.wVirtualKeyCode)))
    return out


class ConsoleKeyReader:
    """
    非阻塞地读取控制台按键事件，同时给出【按下】和【松开】两种。

    poll() 返回 [(字符, 是否按下, 虚拟键码), ...]
      · 普通字符键：'a' / 'A'（按住 Shift 时）等
      · 功能键（方向键、F1…）：字符为 ''，只能靠虚拟键码区分
      · Ctrl+C：字符为 '\\x03'（我们关掉了 PROCESSED_INPUT，不会被系统吃掉）
    """

    def __init__(self):
        self.ok = False
        self._k32 = None
        self._h = None
        self._own = False
        self._old_mode = None
        self._buf = None
        if not _HAS_CTYPES:
            return
        try:
            k32 = ctypes.WinDLL('kernel32', use_last_error=True)
            k32.GetStdHandle.restype = _wt.HANDLE
            k32.GetStdHandle.argtypes = [_wt.DWORD]
            k32.GetFileType.restype = _wt.DWORD
            k32.GetFileType.argtypes = [_wt.HANDLE]
            k32.GetConsoleMode.argtypes = [_wt.HANDLE, ctypes.POINTER(_wt.DWORD)]
            k32.SetConsoleMode.argtypes = [_wt.HANDLE, _wt.DWORD]
            k32.CloseHandle.argtypes = [_wt.HANDLE]
            k32.CreateFileW.restype = _wt.HANDLE
            k32.CreateFileW.argtypes = [_wt.LPCWSTR, _wt.DWORD, _wt.DWORD,
                                        ctypes.c_void_p, _wt.DWORD, _wt.DWORD,
                                        _wt.HANDLE]
            k32.GetNumberOfConsoleInputEvents.argtypes = [
                _wt.HANDLE, ctypes.POINTER(_wt.DWORD)]
            k32.ReadConsoleInputW.argtypes = [
                _wt.HANDLE, ctypes.POINTER(_InputRecord),
                _wt.DWORD, ctypes.POINTER(_wt.DWORD)]

            # ① 直接打开 CONIN$：stdin 被重定向成管道/文件时，GetStdHandle 拿到的
            #    不是控制台句柄（GetConsoleMode 会报 ERROR_INVALID_HANDLE=6），
            #    而 CONIN$ 永远指向当前进程真正的控制台输入缓冲区。
            h = k32.CreateFileW("CONIN$", _GENERIC_READ | _GENERIC_WRITE,
                                _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                                None, _OPEN_EXISTING, 0, None)
            own = True
            # ② 退而求其次用 stdin
            if not h or h == _INVALID_HANDLE:
                own = False
                h = k32.GetStdHandle(_STD_INPUT_HANDLE)
            if not h or h == _INVALID_HANDLE:
                return
            if k32.GetFileType(h) != _FILE_TYPE_CHAR:
                if own:
                    k32.CloseHandle(h)
                return

            old = _wt.DWORD()
            if not k32.GetConsoleMode(h, ctypes.byref(old)):
                if own:
                    k32.CloseHandle(h)
                return
            # 关掉行缓冲/回显/CTRL-C 拦截：我们要的是"原始"按键流
            new = old.value & ~(_ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT |
                                _ENABLE_PROCESSED_INPUT)
            if not k32.SetConsoleMode(h, new):
                if own:
                    k32.CloseHandle(h)
                return

            self._k32 = k32
            self._h = h
            self._own = own
            self._old_mode = old.value
            self._buf = (_InputRecord * 64)()
            self.ok = True
        except Exception:
            self.ok = False

    def close(self):
        """恢复原控制台模式并释放 CONIN$ —— 不恢复的话退出后终端会变得很奇怪"""
        if self._k32 is not None and self._h:
            try:
                if self._old_mode is not None:
                    self._k32.SetConsoleMode(self._h, self._old_mode)
            except Exception:
                pass
            if self._own:
                try:
                    self._k32.CloseHandle(self._h)
                except Exception:
                    pass
        self._h = None
        self.ok = False

    def poll(self):
        out = []
        if not self.ok:
            return out
        try:
            avail = _wt.DWORD()
            if not self._k32.GetNumberOfConsoleInputEvents(self._h,
                                                           ctypes.byref(avail)):
                return out
            if avail.value == 0:
                return out
            n = min(int(avail.value), 64)
            read = _wt.DWORD()
            if not self._k32.ReadConsoleInputW(self._h, self._buf, n,
                                               ctypes.byref(read)):
                return out
            out = _parse_key_records(self._buf, int(read.value))
        except Exception:
            pass
        return out


def cmd_play(args):
    """实时键盘演奏"""
    import msvcrt
    import sounddevice as sd

    fs = args.fs
    tab = build_sine_table()
    eng = AdditiveEngine(tab, fs)

    # 谱参数（可实时调）
    state = {
        "octave": 0,
        "npartials": 8,        # 参与发声的泛音数
        "rolloff": 1.0,        # 幅度衰减指数（越大越暗）
        "inharm": 0.0,         # 0=纯谐波, 1=非谐（钟）
        "decay_s": 0.0,        # 余韵秒数；0 = 不衰减（靠松手收声）
        "curve": "exp",        # 释放曲线："exp" 指数（自然） / "lin" 线性（旧行为）
        "release_s": 0.40,     # 释放长度（衰到 -60 dB 的时间）
        "voices": [],
        "err": None,           # 音频回调里的异常会被记到这里，而不是让流静默死掉
    }
    MAX_VOICES = 4

    # 余韵档位：0 = 持续音（松手才停），其余是"击发后自然消失"的秒数
    DECAY_STEPS = [0.0, 4.0, 2.0, 1.0, 0.5, 0.25]

    # 释放长度档位（衰到 -60 dB 的时间）。
    # 指数淡出是匀速掉 dB：0.4 s 对应 -7.5 dB/50 ms，从满音量到听不见约 130 ms。
    # 档位拉开是为了让"松手后还留多久"这件事可以用耳朵直接挑。
    RELEASE_STEPS = [0.10, 0.20, 0.30, 0.40, 0.60, 0.90, 1.30]

    def make_amps(npart, rolloff):
        a = []
        for i in range(NUM_PARTIALS):
            if i < npart:
                v = AMPS_DEFAULT[0] / ((i + 1) ** rolloff)
            else:
                v = 0.0
            a.append(int(max(0, min(AMP_MAX, round(v)))))
        return a

    def make_ratios(inharm):
        r = list(RATIOS_HARMONIC)
        # 用 inharm 在谐波与非谐之间插值
        for i in (2, 4, 6):        # 第 3/5/7 个泛音（下标 2/4/6）
            r[i] = RATIOS_HARMONIC[i] + (RATIOS_INHARMONIC[i] - RATIOS_HARMONIC[i]) * inharm
        return r

    def apply_to_sounding():
        """
        ★ 本次修复的核心 ★
        把新的频谱参数推给【正在发声】的声部。
        没有这一步，按住音时改参数完全无效 —— "塑谱"这个产品概念就不成立。
        """
        rr = make_ratios(state["inharm"])
        aa = make_amps(state["npartials"], state["rolloff"])
        for v in state["voices"]:
            if v.active:
                v.set_spectrum(rr, aa)
                v.set_decay_seconds(state["decay_s"])

    def note_on(ch):
        """开一个音（返回该声部，松手时用它收声）"""
        name, octv = KEYMAP[ch]
        f0 = note_hz(name, octv + state["octave"])
        if len(state["voices"]) >= MAX_VOICES:
            # 抢占：让最老的声部快速淡出（4 ms），而不是硬切（会有咔哒声）
            state["voices"][0].start_fast_release(4.0)
            if len(state["voices"]) > MAX_VOICES + 4:
                state["voices"].pop(0)
        v = Voice(eng, f0, make_ratios(state["inharm"]),
                  make_amps(state["npartials"], state["rolloff"]), fs)
        v.set_decay_seconds(state["decay_s"])
        v.set_curve(state["curve"])
        v.set_release_seconds(state["release_s"])
        state["voices"].append(v)
        return v

    def callback(outdata, frames, time_info, status):
        # 音频回调里抛异常会导致整个流停掉（而且是静默的），必须兜住
        try:
            buf = np.zeros(frames, dtype=np.float64)
            dead = []
            for v in state["voices"]:
                buf += v.render(frames)
                if not v.active:
                    dead.append(v)
            for d in dead:
                try:
                    state["voices"].remove(d)
                except ValueError:
                    pass
            peak = np.max(np.abs(buf)) if frames else 0.0
            if peak > 1.0:
                buf = buf / peak
            outdata[:, 0] = buf
            if outdata.shape[1] > 1:
                outdata[:, 1] = buf
        except Exception as ex:
            outdata.fill(0.0)
            if state["err"] is None:
                state["err"] = repr(ex)

    stream = sd.OutputStream(samplerate=fs, channels=2, dtype='float32',
                             blocksize=512, callback=callback)
    stream.start()

    def banner():
        print("\n" + "=" * 62)
        print("  实时演奏模式 —— 用键盘弹这个加法合成引擎")
        print("=" * 62)
        print("  音高    : A S D F G H J K L ;   (白键 C D E F G A B C D E)")
        print("            W E T Y U             (黑键)")
        print("  八度    : Z / X")
        print("  谱宽    : [ / ]   参与发声的泛音数 1..8")
        print("  谱心    : - / =   泛音衰减快慢（= 更暗，- 更亮）")
        print("  非谐度  : , / .   0=管风琴音色  1=钟声")
        print("  余韵    : 1 / 2   1=更持续(0=按住一直响)  2=更短(0.25s 打击感)")
        print("  释放长度: 3 / 4   松手后余音留多久  0.10s ── 1.30s（默认 0.40s）")
        print("  淡出曲线: 0       指数(自然渐弱) ⇄ 线性(旧行为，末端像被切断)")
        print("  退出    : ESC")
        print()

    def show():
        ds = state["decay_s"]
        dstr = "持续" if ds <= 0 else ("%.2fs" % ds)
        cstr = "指数" if state["curve"] == "exp" else "线性"
        sys.stdout.write("\r  八度=%+d  泛音=%d  谱心=%.1f  非谐=%.2f  "
                         "余韵=%-5s  释放=%.2fs  %s  声部=%d/%d   "
                         % (state["octave"], state["npartials"], state["rolloff"],
                            state["inharm"], dstr, state["release_s"], cstr,
                            len(state["voices"]), MAX_VOICES))
        sys.stdout.flush()

    def bump_decay(delta):
        try:
            i = DECAY_STEPS.index(state["decay_s"])
        except ValueError:
            i = 0
        state["decay_s"] = DECAY_STEPS[max(0, min(len(DECAY_STEPS) - 1, i + delta))]
        apply_to_sounding()

    def bump_release(delta):
        try:
            i = RELEASE_STEPS.index(state["release_s"])
        except ValueError:
            i = 3
        state["release_s"] = RELEASE_STEPS[
            max(0, min(len(RELEASE_STEPS) - 1, i + delta))]
        # 已经进入 release 的声部也能立刻感受到新长度
        for v in state["voices"]:
            if v.active and v.stage == "release":
                v.set_release_seconds(state["release_s"])

    def param_key(ch):
        """非音高的参数键。返回 True 表示已处理。"""
        if ch == 'z':
            state["octave"] = max(-2, state["octave"] - 1)
        elif ch == 'x':
            state["octave"] = min(+2, state["octave"] + 1)
        elif ch == '[':
            state["npartials"] = max(1, state["npartials"] - 1)
            apply_to_sounding()
        elif ch == ']':
            state["npartials"] = min(NUM_PARTIALS, state["npartials"] + 1)
            apply_to_sounding()
        elif ch == '-':
            state["rolloff"] = max(0.3, state["rolloff"] - 0.2)
            apply_to_sounding()
        elif ch == '=':
            state["rolloff"] = min(3.0, state["rolloff"] + 0.2)
            apply_to_sounding()
        elif ch == ',':
            state["inharm"] = max(0.0, state["inharm"] - 0.1)
            apply_to_sounding()
        elif ch == '.':
            state["inharm"] = min(1.0, state["inharm"] + 0.1)
            apply_to_sounding()
        elif ch == '1':
            bump_decay(-1)
        elif ch == '2':
            bump_decay(+1)
        elif ch == '3':
            bump_release(-1)
        elif ch == '4':
            bump_release(+1)
        elif ch == '0':
            # 切换释放曲线，用于现场 A/B 对比同一个音的两种淡出手感
            state["curve"] = "lin" if state["curve"] == "exp" else "exp"
            for v in state["voices"]:
                if v.active:
                    v.set_curve(state["curve"])
        else:
            return False
        show()
        return True

    reader = ConsoleKeyReader()
    held = {}          # 键 -> 声部（松开这个键时让它收声）

    banner()
    if reader.ok:
        print("  [OK] 已拿到【按下 + 松开】两种按键事件：按住发声，松手收声。")
    else:
        print("  [警告] 读不到按键松开事件，退化为固定 1.5 s 后自动收声。")
    print()
    show()

    FALLBACK_HOLD = 1.5      # 退化模式下每个音最多响多久（秒）

    try:
        while True:
            if reader.ok:
                for ch, is_down, vk in reader.poll():
                    if ch == '\x1b' or ch == '\x03':       # ESC / Ctrl+C
                        raise KeyboardInterrupt
                    if not ch:
                        continue                           # 方向键等功能键
                    key = ch.lower()
                    if is_down:
                        if key in held:
                            continue                       # 系统自动重复，忽略
                        if key in KEYMAP:
                            held[key] = note_on(key)
                            show()
                        elif param_key(key):
                            pass
                    else:
                        # ★★ 关键修复 ★★ 松开 → 进入 release 段，音符真正停下来
                        v = held.pop(key, None)
                        if v is not None and v.active:
                            v.start_release()
                            show()
            else:
                if msvcrt.kbhit():
                    c = msvcrt.getch()
                    # 方向键/F 键等功能键是两个字节（\xe0 或 \x00 打头）。
                    # 不处理的话，第二个字节会被当成普通字母 —— 方向键会弹出音符。
                    if c in (b'\x00', b'\xe0'):
                        msvcrt.getch()          # 吃掉第二个字节
                        continue
                    try:
                        key = c.decode('ascii').lower()
                    except Exception:
                        continue
                    if key == '\x1b':            # ESC
                        break
                    if key in KEYMAP:
                        v = note_on(key)
                        v.auto_release_at = time.time() + FALLBACK_HOLD
                        show()
                    else:
                        param_key(key)

                now = time.time()
                for v in state["voices"]:
                    t = getattr(v, "auto_release_at", None)
                    if t is not None and now >= t:
                        v.auto_release_at = None
                        if v.active:
                            v.start_release()
                            show()

            if state["err"]:
                print("\n\n  [音频回调出错] " + state["err"])
                print("  已退出，避免问题被掩盖。")
                break
            time.sleep(0.004)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()
        stream.stop()
        stream.close()
        print("\n\n  已退出实时演奏模式。")
    return 0


# ------------------------------------------------------------------ main
def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify")
    v.add_argument("--simdir", required=True)
    v.add_argument("--meta", required=True)

    d = sub.add_parser("demo")
    d.add_argument("--outdir", required=True)
    d.add_argument("--fs", type=int, default=48000)

    p = sub.add_parser("play")
    p.add_argument("--fs", type=int, default=48000)

    args = ap.parse_args()
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "demo":
        return cmd_demo(args)
    if args.cmd == "play":
        return cmd_play(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
