#!/usr/bin/env python3
"""board_velocity_check.py —— 力度通路的板级验证与标定工具（一条命令）

为什么需要它
------------
力度这条路有【两个必须上板才能定的数】：
  1. 电极的 RC 量程：未触摸时 base 落在几百还是几千拍？
  2. 由此推出的 vel_shift（0x6F）：每档多少拍。

这两个数在仿真里永远是"我假设的值"。VELOCITY-PATH 文档 §4 写了公式，
但公式里的 base 必须实测。这个脚本就是干这件事的。

协议（19 号 UART v1.0）
----------------------
  写：  [addr, data]          两个字节
  读：  [0x0F, addr]          板子回 [addr, data] 两个字节
  注意：波特率由固件的 UART_BAUD 决定，默认 115200。
        2026-10-23 踩过：旧固件 tdm_live_test 用的是 460800，
        在 115200 下完全静默 —— 所以本脚本会自动扫波特率。

相关寄存器
----------
  0x6E VEL_SENS   力度灵敏度（四段：0=关 / <0x40→128 / <0xC0→256 / 其它→511）
  0x6F VEL_SHIFT  每档右移位数（默认 5 ⇒ 每档 32 拍）
  0x66 PAD_SEL    遥测通道选择 0..15
  0x64/0x65       该通道基线 base（低/高 4 位）
  0x67/0x68       该通道裸计数 raw（低/高 4 位）
  0x69/0x6A       触摸位图 state（低/高 8 位）

用法
----
  python board_velocity_check.py --list
  python board_velocity_check.py --port COM6 selftest
  python board_velocity_check.py --port COM6 calib
  python board_velocity_check.py --port COM6 watch          # 实时看 16 路
  python board_velocity_check.py --port COM6 write 0x6E 0x80
"""
import argparse
import sys
import time

try:
    import serial
    import serial.tools.list_ports as list_ports
except ImportError:
    print("需要 pyserial：pip install pyserial")
    sys.exit(2)

BAUDS = [115200, 460800, 921600, 230400, 1000000]


# ---------------------------------------------------------------------------
# 链路层
# ---------------------------------------------------------------------------
class Link:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.ser = serial.Serial(port, baud, timeout=0.35, write_timeout=0.5)
        time.sleep(0.15)
        self.ser.reset_input_buffer()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def read_reg(self, addr):
        """读一个寄存器；失败返回 None。"""
        self.ser.reset_input_buffer()
        self.ser.write(bytes([0x0F, addr & 0xFF]))
        time.sleep(0.06)
        n = self.ser.in_waiting
        if not n:
            return None
        data = self.ser.read(n)
        # 期望 [addr, value]；容错：丢掉前面的杂字节
        for i in range(len(data) - 1):
            if data[i] == (addr & 0xFF):
                return data[i + 1]
        return None

    def write_reg(self, addr, value):
        self.ser.reset_input_buffer()
        self.ser.write(bytes([addr & 0xFF, value & 0xFF]))
        time.sleep(0.03)


def find_board(port=None):
    """找到能正确回 [addr, data] 的端口 + 波特率。"""
    ports = [port] if port else [p.device for p in list_ports.comports()]
    for dev in ports:
        for baud in BAUDS:
            try:
                link = Link(dev, baud)
            except Exception:
                continue
            v = link.read_reg(0x00)
            if v is not None:
                print(f"找到板子：{dev} @ {baud}")
                return link
            link.close()
    return None


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------
def cmd_selftest(link):
    print("\n=== 寄存器回读自检 ===")
    ok = True

    # [1] 0x6E 默认值必须是 0x80（2026-10-23 修的那个 bug）
    v = link.read_reg(0x6E)
    if v is None:
        print("  [FAIL] 0x6E 读不到")
        ok = False
    elif v == 0x00:
        print("  [FAIL] 0x6E = 0x00 ⇒ 力度灵敏度是【关】状态")
        print("         说明板上固件还没有 2026-10-23 的初值修复（reg_bank 缺 mem[8'h6E]）")
        ok = False
    else:
        print(f"  [OK]   0x6E = 0x{v:02X}（vscale 生效）")

    # [2] 0x6F 默认 5
    v = link.read_reg(0x6F)
    if v is None:
        print("  [FAIL] 0x6F 读不到")
        ok = False
    elif v == 0x00:
        print("  [WARN] 0x6F = 0 ⇒ 每档 1 拍，会极度灵敏（几乎一碰就 15）")
    else:
        print(f"  [OK]   0x6F = 0x{v:02X}（每档 {1 << min(v, 15)} 拍）")

    # [3] 写-读回：0x6E 在四段里换档
    print("\n  写-读回（0x6E 四段映射）：")
    for name, val in [("关", 0x00), ("半灵敏", 0x20), ("一等一", 0x80), ("最灵敏", 0xC8)]:
        link.write_reg(0x6E, val)
        time.sleep(0.05)
        rb = link.read_reg(0x6E)
        mark = "OK" if rb == val else "FAIL"
        if rb != val:
            ok = False
        print(f"    写 0x{val:02X}（{name}）→ 读 0x{rb:02X}  [{mark}]")

    # [4] 逻辑侧可达性 —— 回读正确 ≠ 配置生效
    #     0x6E/0x6F 的回读走 reg_bank 的 mem，逻辑走 regs_flat（只有
    #     FLAT_MASK 选中的字节才有）。两条路可以不一致，实测踩过：
    #     0x6F 不在 mask 里时回读 0x05 全绿，但 r_vel_shift 恒 0。
    #     0x7D/0x7E 是逻辑侧回显，专门用来区分这两种情况。
    print("\n  逻辑侧可达性（0x7D/0x7E 回显 vs 0x6F/0x6E 回读）：")
    for reg, echo, val, name in [(0x6F, 0x7D, 0x07, "VEL_SHIFT"),
                                 (0x6E, 0x7E, 0xC8, "VEL_SENS")]:
        link.write_reg(reg, val)
        time.sleep(0.05)
        rb = link.read_reg(reg)
        lv = link.read_reg(echo)
        if lv is None:
            print(f"    0x{reg:02X} {name}: 0x{echo:02X} 回显读不到 —— 固件可能还没加 0x7D/0x7E")
            ok = False
        elif lv != val:
            print(f"    0x{reg:02X} {name}: 回读 0x{rb:02X} 但逻辑侧 0x{lv:02X}"
                  f"  ⇒ **DEAD READ**（该地址不在 REG_LIVE_MASK 里）")
            ok = False
        else:
            print(f"    0x{reg:02X} {name}: 回读 0x{rb:02X} = 逻辑侧 0x{lv:02X}  [OK]")

    # 恢复默认
    link.write_reg(0x6E, 0x80)
    link.write_reg(0x6F, 0x05)

    print("\n  结论：", "全部通过" if ok else "有失败项，见上")
    return ok


# ---------------------------------------------------------------------------
# 电极通道分类阈值（12 位 RC 计数，0..4095）
#
# 为什么需要分类：2026-10-23 在裸 Tang Nano 20K 上实测，16 路读数分成三类：
#   ch 0-5,11,14,15  base = 12..56     放电过快 ⇒ 电极未接 / 面积过小
#   ch 6,7,8,10,12,13 base = 3000..4095 充不满   ⇒ 短路 / 电容过大 / 下拉过强
#   ch 9             base = 581        唯一落在中间
# 裸板上排针什么都没接，所以这是"空板读数"。把它平均成一个数再据此推
# vel_shift 是**错的** —— 会把两类失效通道混进结果，得出 shift=0 这种荒谬建议。
# 所以：先分类，只用【可用】通道标定；一条可用通道都没有就明确说"标不了"。
# ---------------------------------------------------------------------------
BASE_OPEN_MAX = 100     # <= 100  ⇒ 放电极快，电极基本没接上
BASE_SAT_MIN  = 4000    # >= 4000 ⇒ 一直充不满，饱和
CNT_MAX       = 4095    # RC 计数器是 12 位（pad_scan 的 cnt 是 [CW:0]，CW=11）


def classify_base(base):
    """返回 (类别, 说明)。类别: OPEN / SAT / OK"""
    if base >= BASE_SAT_MIN:
        return 'SAT', '饱和：短路 / 电容过大 / 下拉过强'
    if base <= BASE_OPEN_MAX:
        return 'OPEN', '放电过快：电极未接或面积过小'
    return 'OK', '可用'


def shift_for_span(span):
    """给出让 [hi, 4095] 刚好铺满 0..15 的右移位数。

    条件：最大 shift 使 span >> shift >= 15（于是 15 档全用得上）。
    span >> shift 落在 [15, 30) 时，物理行程的利用最充分。
    """
    shift = 0
    while shift < 15 and (span >> (shift + 1)) >= 15:
        shift += 1
    return shift


def cmd_calib(link):
    """逐通道量 base，分类，并给出 vel_shift 建议。"""
    print("\n=== 逐通道标定（未触摸状态）===")
    print("  通道   base    hi     类别   建议shift  说明")
    rows = []
    for ch in range(16):
        link.write_reg(0x66, ch)
        time.sleep(0.08)
        lo = link.read_reg(0x64)
        hi4 = link.read_reg(0x65)
        if lo is None or hi4 is None:
            print(f"  {ch:4d}   (读不到遥测)")
            continue
        base = ((hi4 & 0x0F) << 8) | lo
        hi = base + (base >> 3) + (base >> 5)      # 触控阈值 ≈ 1.156 x base
        kind, why = classify_base(base)
        span = max(0, CNT_MAX - hi)
        shift = shift_for_span(span)
        rows.append((ch, base, hi, kind, shift, span))
        mark = {'OK': 'OK', 'OPEN': '未接', 'SAT': '饱和'}[kind]
        print(f"  {ch:4d}   {base:5d}   {hi:5d}   {mark:4s}   "
              f"{shift:2d}        {why}")

    ok_rows = [r for r in rows if r[3] == 'OK']
    n_open = sum(1 for r in rows if r[3] == 'OPEN')
    n_sat = sum(1 for r in rows if r[3] == 'SAT')

    print(f"\n  分类汇总：可用 {len(ok_rows)} 路 / 未接 {n_open} 路 / 饱和 {n_sat} 路")

    if not ok_rows:
        print("\n  [无法标定] 没有任何一路落在可用区间（100 < base < 4000）。")
        print("      · 若这是裸开发板：排针上没接电极板，读数是空的，属正常。")
        print("      · 若已接电极板：检查接线、公共地、以及是否有通道短路。")
        print("      ⇒ 此时**不要**去改 0x6F。保持默认 5，等接上真实电极板再标。")
        return

    shifts = [r[4] for r in ok_rows]
    avg_base = sum(r[1] for r in ok_rows) // len(ok_rows)
    avg_shift = sum(shifts) // len(shifts)
    print(f"\n  可用通道平均 base = {avg_base}")
    print(f"  可用通道 shift 建议 = {shifts}（中位/均值 {avg_shift}）")
    cur = link.read_reg(0x6F)
    print(f"  建议 0x6F = {avg_shift}（当前 {cur}）")
    print(f"  写入命令：python board_velocity_check.py --port {link.port} write 0x6F {avg_shift}")
    if len(set(shifts)) > 1:
        print("  [NOTE] 各路 shift 不一致 ⇒ 电极一致性差；量产时应逐路标定后取统一值，")
        print("         或接受最灵敏那一路决定整体手感。")


def cmd_watch(link, seconds=10):
    print(f"\n=== 实时观察（{seconds}s，按 Ctrl+C 提前结束）===")
    print("  每行：raw[0..7] / state / 触发的力度")
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            row = []
            for ch in range(8):
                link.write_reg(0x66, ch)
                time.sleep(0.01)
                lo = link.read_reg(0x67)
                hi4 = link.read_reg(0x68)
                row.append(((hi4 or 0) & 0x0F) << 8 | (lo or 0))
            st_lo = link.read_reg(0x69) or 0
            st = "".join("#" if (st_lo >> i) & 1 else "." for i in range(8))
            print("  " + " ".join(f"{v:4d}" for v in row) + f"   [{st}]")
    except KeyboardInterrupt:
        print("  (中止)")


def cmd_dump(link):
    print("\n=== 关键寄存器 ===")
    names = {
        0x00: "CTRL", 0x37: "PRESET", 0x5C: "TILT",
        0x6B: "TILT_VLO", 0x6C: "TILT_VHI", 0x6D: "TILT_VGAIN",
        0x6E: "VEL_SENS", 0x6F: "VEL_SHIFT", 0x66: "PAD_SEL",
        0x38: "ARTIC_CTL", 0x3B: "STRIKE_DM_CURVE", 0x3C: "STRIKE_DK_BASE",
    }
    for a in sorted(names):
        v = link.read_reg(a)
        print(f"  0x{a:02X} {names[a]:<11} = " + ("(读不到)" if v is None else f"0x{v:02X}  ({v})"))


# ---------------------------------------------------------------------------
# 激发模式（0x38–0x3F）板级验证
# ---------------------------------------------------------------------------
# 判据的立场：板子只能回读寄存器，听不到声音。所以本命令验证的是
#   "寄存器写进去、回读对、且逻辑侧真的按这组值算出来的梯度"
# 最后一项用**与 RTL 同一套公式**在主机侧算一遍并打印出来 ——
# 公式的一致性由 sim/tb_strike.v 的 160 组向量兜住（Python vs Verilog 逐位）。
ARTIC_BOOT = {
    0x38: 0x22,   # enable=0 / auto_rel=1 / s_lvl=2
    0x39: 0xFF,   # mask lo
    0x3A: 0xFF,   # mask hi
    0x3B: 0x2B,   # d_m=3, curve=10
    0x3C: 0x0E,   # d_k_base=14
    0x3D: 0xFE,   # hold lo   79102 = 0x0134FE
    0x3E: 0x34,   # hold mid
    0x3F: 0x01,   # hold hi
}

FS = 27000000 / 512.0          # 52734.375 Hz


def exp_steps(floor, m, k):
    """与 osc_env.v / articulation_v2.exp_steps 逐位一致。"""
    level, n = 32768, 0
    while level > floor:
        step = max(1, ((level * m) >> k) & 0xFFFF)
        level = floor if level <= floor + step else level - step
        n += 1
        if n > 32768:
            return 32768
    return max(1, n)


def decode_strike(r):
    """把 8 个回读字节解成字段。"""
    return dict(
        enable=r[0x38] & 1, auto_rel=(r[0x38] >> 1) & 1, s_lvl=(r[0x38] >> 4) & 0xF,
        mask=r[0x39] | (r[0x3A] << 8),
        d_m=r[0x3B] & 3, curve=(r[0x3B] >> 2) & 0xF,
        base=r[0x3C] & 0x1F,
        hold=r[0x3D] | (r[0x3E] << 8) | ((r[0x3F] & 0xF) << 16),
    )


def print_strike_table(f):
    """按 RTL 的公式算每泛音的 d_k / s_lvl / 衰减时长。"""
    print(f"  enable={f['enable']} auto_rel={f['auto_rel']} mask=0x{f['mask']:04X} "
          f"base={f['base']} curve={f['curve']} d_m={f['d_m']} s_lvl={f['s_lvl']} "
          f"hold={f['hold']} 拍 = {f['hold'] / FS * 1000:.0f} ms")
    print("   k  strike?  d_k  s_lvl    衰减")
    for k in range(16):
        sel = f["enable"] and ((f["mask"] >> k) & 1)
        if not sel:
            print(f"  {k:2d}    -      -     -    （走音色自带包络）")
            continue
        d_k = max(0, f["base"] - ((k * f["curve"]) >> 4))
        q15 = (f["s_lvl"] << 11) if (k < 4 and f["s_lvl"]) else 0
        ms = exp_steps(q15, f["d_m"], d_k) * 1000.0 / FS
        print(f"  {k:2d}   YES    {d_k:2d}  {q15:5d}  {ms:8.1f} ms")


def cmd_strike(link, args):
    # 1) 上电默认值（引导序列写的）—— 这一条同时验证 0x38–0x3F 的回读通路
    print("\n=== 激发模式寄存器（0x38–0x3F）===")
    r = {}
    bad = []
    for a in sorted(ARTIC_BOOT):
        v = link.read_reg(a)
        if v is None:
            print(f"  0x{a:02X} 读不到 —— 板子可能不是产品顶层，或 UART 没通")
            return False
        r[a] = v
        mark = "OK " if v == ARTIC_BOOT[a] else "DIFF"
        if v != ARTIC_BOOT[a]:
            bad.append(a)
        print(f"  0x{a:02X} = 0x{v:02X}  期望 0x{ARTIC_BOOT[a]:02X}  [{mark}]")

    if bad:
        print(f"  ⚠ 0x{min(bad):02X}..0x{max(bad):02X} 与引导序列不一致。")
        print("    可能原因：板子上烧的是旧码流（没有 0x38–0x3F 的引导写入），")
        print("    或者你手动改过这些寄存器（改过就是对的，重启后应恢复）。")

    f = decode_strike(r)
    print("\n--- 当前生效的 strike 配置 ---")
    print_strike_table(f)
    if not f["enable"]:
        print("  ⇒ enable=0：以上配置【不生效】，整机是 sustain（向后兼容的默认态）")

    # 2) 写一组新值再读回（证明写通路通）
    print("\n--- 写入 0x38=0x23（enable=1, auto_rel=1, s_lvl=2）并读回 ---")
    link.write_reg(0x38, 0x23)
    time.sleep(0.05)
    v = link.read_reg(0x38)
    ok_write = (v == 0x23)
    print(f"  读回 0x{v:02X}  [{'OK' if ok_write else 'FAIL'}]" if v is not None else "  读不到")

    if v is not None:
        r[0x38] = v
        f = decode_strike(r)
        print("\n--- 开启后的预测（公式与 RTL 一致，由 tb_strike 的 160 组向量保证）---")
        print_strike_table(f)

    # 3) 恢复成上电态：不留"开着 strike"的板子给下一个人
    link.write_reg(0x38, ARTIC_BOOT[0x38])
    time.sleep(0.05)
    v = link.read_reg(0x38)
    print(f"\n--- 已恢复 0x38=0x{v:02X}（enable=0，回到 sustain）---"
          if v is not None else "\n--- 恢复 0x38 时读不到 ---")

    ok = ok_write and not bad
    print("\n结论：" + ("全部一致" if ok else
                      ("写通路通，但上电值与引导不一致（见上）" if ok_write else "写通路不通")))
    return ok


def cmd_write(link, addr, value):
    link.write_reg(addr, value)
    time.sleep(0.05)
    rb = link.read_reg(addr)
    print(f"写 0x{addr:02X} = 0x{value:02X} ⇒ 读回 0x{rb:02X}" if rb is not None
          else f"写 0x{addr:02X} = 0x{value:02X} ⇒ 读不到")


def main():
    ap = argparse.ArgumentParser(description="力度通路板级验证与标定")
    ap.add_argument("--port", help="串口，如 COM6；省略则自动扫")
    ap.add_argument("--list", action="store_true", help="只列串口")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "calib", "watch", "dump", "write", "strike"])
    ap.add_argument("args", nargs="*", help="write 用：ADDR VALUE（可写 0x6E 或 110）")
    ns = ap.parse_args()

    if ns.list:
        for p in list_ports.comports():
            print(f"  {p.device}  {p.description}")
        return 0

    link = find_board(ns.port)
    if link is None:
        print("没找到板子。检查：")
        print("  · USB 线接的是【板载 BL616】口，不是外置 JTAG 下载器（后者没有 UART 通道）")
        print("  · 固件的 UART_BAUD 是否在 " + "/".join(map(str, BAUDS)) + " 之内")
        print("  · 板子是否已经烧了产品顶层（旧固件可能只做回显）")
        return 1

    try:
        if ns.cmd == "selftest":
            ok = cmd_selftest(link)
            return 0 if ok else 1
        if ns.cmd == "calib":
            cmd_calib(link)
        elif ns.cmd == "watch":
            cmd_watch(link)
        elif ns.cmd == "dump":
            cmd_dump(link)
        elif ns.cmd == "strike":
            ok = cmd_strike(link, ns.args)
            return 0 if ok else 1
        elif ns.cmd == "write":
            if len(ns.args) < 2:
                print("用法：write ADDR VALUE")
                return 2
            cmd_write(link, int(ns.args[0], 0), int(ns.args[1], 0))
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
