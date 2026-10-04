# -*- coding: utf-8 -*-
"""
dsp_host.py —— PC 上位机（UART 协议 v0.9）

【它是什么】
  把"人想做的事"翻译成 FPGA 听得懂的**两字节帧**：[地址][数据]。
  同一个脚本三种用法，**都不需要先有板子**：
    --dry        只打印将发送的字节流 + 中文注解（"看一下具体是怎么操作的"）
    --emit F     把帧序列写成激励文件（给仿真测试台用；见下方"与仿真的对应"）
    --port COMx  真串口发送（板子到手后直接用；需要 pyserial）

【与仿真的对应】
  src/sim/tb_audio.v 的 +test=0 里那 22 个帧，就是本脚本 `demo-score` 这条命令
  生成的同一串字节 —— 也就是说：**仿真里验证过的操作序列，上板时原样重放**。

【寄存器地址】
  与 `python tools/scripts/regmap_dump.py --dump` 的输出**必须一致**（那是唯一事实源）。
  本脚本的地址表若与之不符，`--check-map` 会报错（防"各改各的"）。

用法示例：
  python tools/scripts/dsp_host.py --dry demo-score            # 看曲谱下载全流程
  python tools/scripts/dsp_host.py --dry fx reverb             # 只开混响
  python tools/scripts/dsp_host.py --port COM5 demo-score      # 上板真发（还没板子时别用）
  python tools/scripts/dsp_host.py --check-map                 # 地址表对账
"""
import argparse
import os
import sys
import time

# ---------------------------------------------------------------------------
# 寄存器地图 —— 按 19 号《UART 协议 v1.0（已冻结）》§3 的地址表
#   唯一事实源：docs/02-技术方案/19-UART协议v1.0草案.md §3
#   `--check-map` 会与 RTL 实际抽取结果对账（防"各改各的"）
# ---------------------------------------------------------------------------
REG = {
    "CTRL":         0x00,     # 【A4 裁定：以实现为准】[0]测试 [1]VIB_EN [2]GLIDE_EN [3]preset_src(0=引脚/1=寄存器)
                              #   默认 0x02（VIB/GLIDE 深度步长默认 0 ⇒ inert）；包络使能将来回归 0x38
    "RD_REQ":       0x0F,     # 【A3】写 [0x0F][src_addr] → tx 依次回 [src_addr][value] 两字节
                              #   （取代草案 §1 的 [0x80|addr] 单字节方案，贴合既有两字节组帧）
    "VIB_INC":      0x30,     # 24 位小端：f × 2^24 / fs
    "VIB_DEPTH":    0x33,     # 16 位小端（音分×100 尺度，26.3 音分 ≈ 1000）
    "GLIDE_STEP":   0x35,     # 16 位小端（线性滑音每样本步进）
    "PRESET":       0x37,     # [1:0] 音色 0–3；默认 0
    "FX_CTRL":      0x40,     # [0]干 [1]延迟 [2]合唱 [5:3]湿声右移；默认 0x01
    "DELAY_LEN":    0x41,     # 16 位小端；冻结表写默认 2048
                              #   冲突：线缓冲 AW=11 ⇒ 2048 截断成 0（抽头读到刚写入的样本）。
                              #   我已把 RTL 默认改 1500；请 复核 决定是改表还是改 AW。
    "FEEDBACK":     0x43,     # Q8；默认 0x60
    "CHORUS_RATE":  0x44,     # 16 位小端；默认 430
    "CHORUS_DEPTH": 0x46,     # 16 位小端；默认 64
    "RV_FB":        0x48,
    "RV_DAMP":      0x49,
    "SEQ_CTRL":     0x50,     # 冻结语义：[0]使能 [1]保持
                              #   冲突：本 RTL 还有 [2]=用下载曲谱，冻结表里没有这一位
    "TEMPO":        0x51,     # 24 位小端 = 每拍时钟数（不是 BPM！）
    "SEQ_VEL":      0x54,
    # ---- 塑谱（步③）----
    "SPEC_IDX":     0x58,     # 谱 RAM 写指针 0–15（写后自动 +1）
    "SPEC_VAL":     0x59,     # 谱 RAM 数据
    "SPEC_MODE":    0x5A,     # [0]0=替换/1=叠加 [1]写 0x59/0x5B 后自动刷新在响声部；默认 0x02
    "HARM_PADS":    0x5B,     # 右手键排位掩码 bit0–7 ↔ 泛音 1–8
    # ---- 左手事件（步①，串行化）----
    "NOTE_NUM":     0x60,     # [7]=on/off，[6:0] MIDI 音符号
    "NOTE_TRIG":    0x61,     # [3:0] 力度；**写入即触发事件**
    "SPEC_REFRESH": 0x63,     # 修正案 A1：写 0–31 刷新该声部谱形，0xFF 全刷
    # ---- (本次)：电极遥测（19 号 §5 的 0x64+ 预留区；只读遥测 + 一个选择器）----
    #   用途：上板 bring-up 第一件事 —— 量 RC 绝对量程（步骤16 §1）
    #   命令：python tools/scripts/dsp_host.py --port COMx padmon
    "PAD_BASE_LO":  0x64,     # 所选通道的基线（低 8 位）
    "PAD_BASE_HI":  0x65,     # 基线（高 4 位在 [3:0]）
    "PAD_SEL":      0x66,     # [3:0] 选通道 0–15（**主机写**）
    "PAD_RAW_LO":   0x67,     # 所选通道的裸放电计数（低 8 位）
    "PAD_RAW_HI":   0x68,     # 裸计数（高 4 位在 [3:0]）
    "PAD_ST_LO":    0x69,     # 16 路触摸位图低字节
    "PAD_ST_HI":    0x6A,     # 16 路触摸位图高字节
    # ---- 曲谱（步④后 0x72 变保留，索引由硬件管理）----
    "SCORE_NOTE":   0x70,
    "SCORE_BEATS":  0x71,
    "SCORE_LEN":    0x73,
    "PROTO_VER":    0x7F,     # 只读语义，= 0x10（v1.0）默认值在 reg_bank 初值块
}

# v2 规划中、**当前 RTL 未实现**的地址：放在这里，避免 --check-map 误报
#（对应 19 号 §4 的"精细塑形"可选项；实现后搬回 REG）
REG_V2 = {
    "TILT":         0x5C,     # 谱形倾斜（v2）
    "SPREAD":       0x5D,     # 谱形展开（v2）
    "ANHARM":       0x5E,     # 非谐度 0=纯谐波 ↔ 255=钟列插值（v2）
}
FS = 52734.375

# 欢乐颂开头 8 步（与 tb_audio.v test=0 完全一致）
DEMO_SCORE = [(64, 1), (64, 1), (65, 1), (67, 1), (67, 1), (65, 1), (64, 1), (62, 2)]


def tempo_inc(bpm):
    """BPM → 每样本拍数（Q24）。RTL 只做加法看进位，除法在这里做掉。"""
    return int(round((bpm / 60.0) * (1 << 24) / FS))


def le_bytes(value, n):
    return [(value >> (8 * i)) & 0xFF for i in range(n)]


class Frames(object):
    """帧序列 + 中文注解（注解只给人看，不上线）"""

    def __init__(self):
        self.items = []          # [(addr, data, note)]

    def w(self, name, data, note=""):
        a = REG[name] if isinstance(name, str) else name
        self.items.append((a, data & 0xFF, note or name))

    def w16(self, name, value, note=""):
        for i, b in enumerate(le_bytes(value, 2)):
            self.w(name, b, "%s[%d]" % (note or name, i))

    def w24(self, name, value, note=""):
        for i, b in enumerate(le_bytes(value, 3)):
            self.w(name, b, "%s[%d]" % (note or name, i))

    def score(self, notes):
        # 冻结表里 0x72 是"保留"，索引由硬件自动管理：
        #   先写 SCORE_LEN=0 让索引归零，再逐对写 音高/拍数，最后写长度。
        self.w("SCORE_LEN", 0, "长度写 0 → 索引归零（0x72 已冻结为保留，不能再用）")
        for n, b in notes:
            self.w("SCORE_NOTE", n, "音高 MIDI %d" % n)
            self.w("SCORE_BEATS", b, "拍数 %d（写完索引自动 +1）" % b)
        self.w("SCORE_LEN", len(notes), "曲谱步数 = %d" % len(notes))

    def dump(self):
        print("将发送 %d 个两字节帧 = %d 字节" % (len(self.items), 2 * len(self.items)))
        print("序号  地址  数据   含义")
        print("-" * 62)
        for i, (a, d, note) in enumerate(self.items):
            print("%4d  0x%02X  0x%02X   %s" % (i, a, d, note))
        print("-" * 62)
        print("线上字节流（十六进制）：%s" % " ".join("%02X" % b
              for a, d, _ in self.items for b in (a, d)))


def cmd_fx(which):
    f = Frames()
    m = {"dry": 0x01, "delay": 0x03, "chorus": 0x05, "reverb": 0x41,
         "delay+reverb": 0x43, "all": 0x47}.get(which)
    if m is None:
        print("未知效果组合：%s（可选 %s）" % (which, "/".join(
            ["dry", "delay", "chorus", "reverb", "delay+reverb", "all"])))
        return None
    f.w("FX_CTRL", m, "效果器 = %s" % which)
    if m & 0x40:
        f.w("RV_FB", 0x80, "混响反馈 0.5（安全默认；高反馈档需做满幅削顶复核）")
        f.w("RV_DAMP", 0x03, "混响阻尼 3（高频先死）")
    if m & 0x02:
        f.w16("DELAY_LEN", 1500, "延迟抽头 1500 样本 ≈ 28 ms")
        f.w("FEEDBACK", 0x60, "延迟反馈 0.375")
    if m & 0x04:
        f.w16("CHORUS_RATE", 430, "合唱 LFO ≈ 1.35 Hz")
        f.w16("CHORUS_DEPTH", 64, "合唱深度 64 样本")
    return f


def cmd_demo_score(bpm=171.4, vel=0xC0):
    f = Frames()
    # 关滑音/颤音：滑音是按【时隙】的，时隙复用时会从残留旧音高滑过来，
    #   旋律演示里会听到"上个占用该时隙的音"的痕迹。演奏时才需要 portamento。
    f.w("CTRL", 0x00, "关滑音/颤音（曲目演示不需要 portamento）")
    f.w("FX_CTRL", 0x41, "干声 + 混响")
    f.w("RV_FB", 0xC0, "混响反馈 0.75")
    f.w("RV_DAMP", 0x03, "混响阻尼 3")
    f.w24("TEMPO", tempo_inc(bpm),
          "节拍 %g BPM（编码 = Q24 每样本增量 %d；冻结表写'每拍时钟数'，两者互为倒数）"
          % (bpm, tempo_inc(bpm)))
    f.w("SEQ_VEL", vel, "力度 0xC0")
    f.score(DEMO_SCORE)
    f.w("SEQ_CTRL", 0x05, "使能定序器 + 使用下载曲谱")
    return f


def cmd_stop():
    f = Frames()
    f.w("SEQ_CTRL", 0x00, "停定序器")
    f.w("FX_CTRL", 0x01, "效果器全关（仅干声）")
    return f


def cmd_note(spec):
    """左手音符事件（冻结表 §4：先写 0x60，再写 0x61 触发）
    spec = "on:64:12,on:67:10,off:64" 之类；力度 0–15
    """
    f = Frames()
    for item in spec.split(","):
        p = item.strip().split(":")
        on = (p[0] == "on")
        n = int(p[1]) & 0x7F
        f.w("NOTE_NUM", (0x80 if on else 0x00) | n,
            "音符 %s MIDI %d" % ("on" if on else "off", n))
        v = (int(p[2]) & 0x0F) if (on and len(p) > 2) else 0
        f.w("NOTE_TRIG", v, "写入即触发（力度 %d/15）" % v)
    return f


def cmd_spectrum(mode, vals):
    """右手塑谱：PC 算好 16 字节谱 → 连写 0x59（自动步进）→ 0x5A 触发刷新
    mode: replace / add ；vals: 16 个 0–255（省略则用示例谱）
    """
    f = Frames()
    if not vals:
        vals = [255, 0, 160, 0, 120, 0, 90, 0, 70, 0, 55, 0, 40, 0, 30, 0]
    f.w("SPEC_IDX", 0, "谱 RAM 写指针归零")
    for i, v in enumerate(vals[:16]):
        f.w("SPEC_VAL", v, "泛音 %d 幅度 %d（写后指针自动 +1）" % (i + 1, v))
    f.w("SPEC_MODE", 0x00 if mode == "replace" else 0x02,
        "谱模式 = %s + 自动刷新在响声部" % ("替换" if mode == "replace" else "叠加"))
    return f


def cmd_refresh(voice):
    """修正案 A1：逐声部刷新谱形（写 0–31 刷新该声部，0xFF 全刷）"""
    f = Frames()
    f.w("SPEC_REFRESH", 0xFF if voice == "all" else (int(voice) & 0x1F),
        "刷新%s谱形" % ("全部声部" if voice == "all" else "声部 %s" % voice))
    return f


def cmd_read(addrs):
    """读帧【A3 裁定】：写 [0x0F][src_addr] → FPGA 从 tx 依次回 [src_addr][value] 两字节。
    用途：上板调试时确认"写进去了没有"；也是 VP7（上电行为）的直接观测手段 ✓
    """
    f = Frames()
    for a in addrs.split(","):
        a = a.strip()
        v = int(a, 0) if a.lower().startswith("0x") else int(a)
        f.w("RD_REQ", v & 0xFF, "读 0x%02X → tx 回 [0x%02X][值] 两字节" % (v, v))
    return f


def cmd_padmon(port, baud=115200, nch=16):
    """⑤ 电极遥测（第 7 轮）：逐通道读回 base/raw，**直接判定 RC 量程能不能用**。

    为什么这是"上板第一件事"（refs/素材库/步骤16_上板风险审计.md §1）：
      内部下拉电阻与电极电容都未知 ⇒ 放电可能**太快**（分辨不出）或
      **计数器封顶**（永远摸不着）✗✗ —— 这两种情况下后面所有调试都是白费功夫。
      判据（可证伪）：
        ① 松手时 raw ∈ [20, 2000]（既没快到底、也没封顶）✓
        ② 手指按住该电极时 raw ≥ 1.3 × base ✓
      不满足就先去调外接 R/C（建议每根 1 MΩ + 22 pF ⇒ RC ≈ 594 拍）✓

    寄存器（19 号 §5 的 0x64+ 保留区）：
      0x66 PAD_SEL 选通道；0x64/65 PAD_BASE 低/高；0x67/68 PAD_RAW 低/高
      读法（A3 冻结协议）：写 [0x0F][addr] ⇒ 回 [addr][value] 两字节
    """
    if not port:
        print("padmon 需要 --port COMx（它要交互读回，不能只 --dry）")
        print("用法：python tools/scripts/dsp_host.py --port COM5 padmon")
        return 2
    try:
        import serial
    except ImportError:
        print("需要 pyserial：pip install pyserial"); return 1

    ser = serial.Serial(port, baud, timeout=1)

    def ask(addr):
        ser.reset_input_buffer()
        ser.write(bytes([0x0F, addr]))
        r = ser.read(2)
        if len(r) < 2:
            return None
        return r[1]                      # 第 1 字节是回显地址，第 2 字节才是值

    print("=" * 62)
    print(" 电极遥测：逐通道量 RC 量程（上板 bring-up 第一步）")
    print("=" * 62)
    print("  切通道前请【松开所有电极】；量到哪一路就把手指按上去看 raw 是否变大")
    print("  %-4s %-8s %-8s %-8s %s" % ("通道", "base", "raw", "raw/base", "判定"))
    bad = 0
    for ch in range(nch):
        ser.write(bytes([0x66, ch]))
        time.sleep(0.05)                 # 遥测节流 ≈152 µs，50 ms 足够
        bl, bh = ask(0x64), ask(0x65)
        rl, rh = ask(0x67), ask(0x68)
        if None in (bl, bh, rl, rh):
            print("  %-4d  ✗ 回读超时（检查串口/波特率/接线）" % ch); bad += 1; continue
        base = (bh << 8) | bl
        raw = (rh << 8) | rl
        ratio = (raw / base) if base else 0.0
        if raw > 2000:
            verdict = "✗ 封顶风险（RC 太慢 ⇒ 减 R/C 或加外接电阻）"
            bad += 1
        elif raw < 20:
            verdict = "✗ 太快（分辨率不足 ⇒ 加电容）"
            bad += 1
        else:
            verdict = "✓ 量程可用"
        print("  %-4d %-8d %-8d %-8.2f %s" % (ch, base, raw, ratio, verdict))
    ser.close()
    print("-" * 62)
    if bad:
        print(" ★ %d 路有问题：先调外接 R/C（建议 1 MΩ + 22 pF ⇒ RC≈594 拍）再继续 ✗" % bad)
        return 1
    print(" ★ 16 路量程都在可用区间 ✓ —— 然后逐个按上去，确认 raw ≥ 1.3×base ✓")
    return 0


def check_map():
    """与 regmap_dump.py 的抽取结果对账（防"各改各的"）"""
    p = os.path.join("tools", "scripts", "regmap_dump.py")
    if not os.path.exists(p):
        print("找不到 regmap_dump.py"); return 1
    sys.path.insert(0, os.path.dirname(p))
    import importlib
    r = importlib.import_module("regmap_dump")
    rows = r.extract()
    rtl = set(int(x["addr"], 16) for x in rows)
    bad = [(n, a) for n, a in REG.items() if a not in rtl]
    extra = sorted(rtl - set(REG.values()))
    print("RTL 里有 %d 个地址；本脚本用到 %d 个" % (len(rtl), len(REG)))
    if bad:
        for n, a in bad:
            print("  ✗ 脚本里的 %s = 0x%02X 在 RTL 里【不存在】" % (n, a))
    if extra:
        print("  （RTL 里还有脚本没用到的：%s）"
              % " ".join("0x%02X" % a for a in extra))
    return 1 if bad else 0


def send_serial(frames, port, baud=115200):
    try:
        import serial
    except ImportError:
        print("需要 pyserial：pip install pyserial"); return 1
    ser = serial.Serial(port, baud, timeout=1)
    for a, d, _ in frames.items:
        ser.write(bytes([a, d]))
    ser.close()
    print("已通过 %s 发送 %d 帧" % (port, len(frames.items)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印帧序列与注解")
    ap.add_argument("--emit", help="把帧序列写成激励文件")
    ap.add_argument("--port", help="真串口发送，如 COM5")
    ap.add_argument("--check-map", action="store_true", help="与 RTL 地址表对账")
    ap.add_argument("cmd", nargs="?", default="demo-score",
                    help="demo-score / fx <组合> / note <on:64:12,off:64> / "
                         "spectrum [replace|add] / refresh <0-31|all> / stop")
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("arg2", nargs="?", default="")
    a = ap.parse_args()

    if a.check_map:
        return check_map()

    if a.cmd == "demo-score":
        f = cmd_demo_score()
    elif a.cmd == "fx":
        f = cmd_fx(a.arg or "reverb")
    elif a.cmd == "note":
        f = cmd_note(a.arg or "on:64:12,off:64")
    elif a.cmd == "spectrum":
        f = cmd_spectrum(a.arg or "add", [])
    elif a.cmd == "refresh":
        f = cmd_refresh(a.arg or "all")
    elif a.cmd == "read":
        f = cmd_read(a.arg or "0x00,0x37,0x40,0x50")
    elif a.cmd == "padmon":
        # ⑤ 电极遥测：交互式，必须给 --port（不经过 Frames）
        return cmd_padmon(a.port)
    elif a.cmd == "stop":
        f = cmd_stop()
    else:
        print("未知命令：%s" % a.cmd)
        return 2
    if f is None:
        return 2

    if a.emit:
        with open(a.emit, "w", encoding="utf-8") as fh:
            fh.write("# addr data  （dsp_host.py 生成；仿真测试台可读）\n")
            for ad, d, note in f.items:
                fh.write("%02X %02X   # %s\n" % (ad, d, note))
        print("已写出激励文件 %s（%d 帧）" % (a.emit, len(f.items)))
    if a.port:
        return send_serial(f, a.port)
    f.dump()          # 默认就是 --dry 行为：打印给人看
    return 0


if __name__ == "__main__":
    sys.exit(main())
