#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""play_note.py -- 通过 UART 直接注入音符事件（不需要触控屏 / 不需要 84 节点 MUX）

为什么需要它
------------
四槽分层要上板验证，但现在只有 16 路直连 pad（LEGACY_PAD=1），没有 J10、
没有 84 节点 MUX、没有触控屏。如果只能等硬件到货，RTL 风险就和硬件风险
绑在一起了。

`tdm_top_owned.v:662-665` 的 UART 事件源给了另一条路：

    wire u_ev_valid = wr_en && (wr_addr == 8'h61);
    wire u_ev_on    = r_note_num[7];        // R[0x60] 的 bit7 = 1 开 / 0 关
    wire u_ev_note  = r_note_num[6:0];
    wire u_ev_vel   = wr_data[3:0];         // 写 0x61 的那个字节的低 4 位

⇒ 写 0x60 = note|0x80，再写 0x61 = vel，就是一个 note-ON 事件。
⇒ 写 0x60 = note，再写 0x61 = 任意，就是一个 note-OFF 事件。

这样四层、移调、力度曲线、归一都能纯 UART 验，**与硬件到货解耦**。

协议要点（踩过的坑）
--------------------
1. 必须写 0x60 之后再写 0x61。只写 0x61 会用 R[0x60] 的旧值 —— 本项目在
   曲谱下载上犯过这个错（`tdm_top_owned.v:640` 注释）。
2. 事件队列深度只有 4（`SRCQ_DEPTH = 4`）。连发会丢。本工具每次事件后
   等 `--gap`（默认 40ms），并把写 0x61 当作"该事件已入队"的握手。
3. 力度是 4 位（0..15），不是 8 位。写 0x61 的高 4 位被忽略。

用法
----
    python tools/play_note.py note 60 --vel 9 --dur 1.0
    python tools/play_note.py chord 60 64 67 --dur 1.2
    python tools/play_note.py scale            # 音阶自检
    python tools/play_note.py layers 60        # 分层试听用：同音连打 4 次
    python tools/play_note.py off              # 全关（清音）

    --port COM6     指定串口（省略则自动扫）
    --vel N         力度 0..15（默认 9）
    --dur S         按住时长秒（默认 1.0）
    --gap MS        事件间隔毫秒（默认 40）
"""
import argparse
import sys
import time

sys.path.insert(0, __file__.rsplit('/', 1)[0])

from board_velocity_check import find_board  # noqa: E402

REG_NOTE = 0x60
REG_EV   = 0x61


class Player:
    def __init__(self, link, gap_ms=40):
        self.link = link
        self.gap = gap_ms / 1000.0
        self.open_notes = []

    def _fire(self, note, on, vel):
        val = (note & 0x7F) | (0x80 if on else 0x00)
        self.link.write_reg(REG_NOTE, val)
        time.sleep(self.gap)
        self.link.write_reg(REG_EV, vel & 0x0F)
        time.sleep(self.gap)

    def note_on(self, note, vel=9):
        self._fire(note, True, vel)
        self.open_notes.append(note)

    def note_off(self, note, vel=0):
        self._fire(note, False, vel)
        if note in self.open_notes:
            self.open_notes.remove(note)

    def all_off(self, sweep=False):
        for n in list(self.open_notes):
            self.note_off(n)
        if sweep:
            # 兜底：把 0..107 都关一遍。慢（约 9 s），只在怀疑有残留时用。
            for n in range(0, 108):
                self._fire(n, False, 0)


def cmd_note(p, args):
    n = int(args.nums[0])
    p.note_on(n, args.vel)
    time.sleep(args.dur)
    p.note_off(n)


def cmd_chord(p, args):
    notes = [int(x) for x in args.nums]
    for n in notes:
        p.note_on(n, args.vel)
    time.sleep(args.dur)
    for n in notes:
        p.note_off(n)


def cmd_scale(p, args):
    # C 大调一个八度 + 收尾和弦
    steps = [60, 62, 64, 65, 67, 69, 71, 72]
    for n in steps:
        p.note_on(n, args.vel)
        time.sleep(args.dur * 0.55)
        p.note_off(n)
        time.sleep(0.05)
    time.sleep(0.2)
    for n in (60, 64, 67):
        p.note_on(n, args.vel)
    time.sleep(1.2)
    for n in (60, 64, 67):
        p.note_off(n)


def cmd_layers(p, args):
    """分层试听：同音重复打 4 次，每次间隔够长以便分辨尾音叠加。

    四层实现后，每次 note-on 应当同时听到 N 个音色（按当前 selection）。
    现在（未实现分层）4 次是 4 个独立的同音重触发，用作对照基线。
    """
    n = int(args.nums[0]) if args.nums else 60
    for i in range(4):
        print(f"  [{i + 1}/4] note {n}")
        p.note_on(n, args.vel)
        time.sleep(args.dur)
        p.note_off(n)
        time.sleep(0.35)


def cmd_off(p, args):
    p.all_off(sweep=True)
    print("  已全关（含 0..107 全扫）")


def main():
    ap = argparse.ArgumentParser(description="UART 音符注入（四槽分层板级验证用）")
    ap.add_argument("cmd", choices=["note", "chord", "scale", "layers", "off"])
    ap.add_argument("nums", nargs="*", help="MIDI 音符号（60 = C4）")
    ap.add_argument("--port", default=None)
    ap.add_argument("--vel", type=int, default=9, help="力度 0..15")
    ap.add_argument("--dur", type=float, default=1.0, help="按住秒数")
    ap.add_argument("--gap", type=int, default=40, help="事件间隔毫秒")
    args = ap.parse_args()

    link = find_board(args.port)
    if link is None:
        print("找不到板子。检查：板子是否上电、码流是否烧进 SRAM、COM 口是否被占用。")
        return 1

    p = Player(link, args.gap)
    try:
        {"note": cmd_note, "chord": cmd_chord, "scale": cmd_scale,
         "layers": cmd_layers, "off": cmd_off}[args.cmd](p, args)
    finally:
        p.all_off()
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
