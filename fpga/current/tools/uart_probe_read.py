#!/usr/bin/env python3
"""读 UART 原始字节并做直方图 —— 用于解读 beacon 探针字节。

用法:
    python tools/uart_probe_read.py --port COM6 --seconds 3
    python tools/uart_probe_read.py --port COM6 --seconds 3 --baud 460800
"""
import argparse
import collections
import sys
import time

import serial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM6')
    ap.add_argument('--baud', type=int, default=115200)
    ap.add_argument('--seconds', type=float, default=3.0)
    ap.add_argument('--raw', action='store_true', help='同时打印前 64 字节十六进制')
    args = ap.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
    except Exception as e:
        print(f'打开 {args.port} 失败: {e}')
        return 2

    time.sleep(0.2)
    ser.reset_input_buffer()

    hist = collections.Counter()
    order = []
    t_end = time.time() + args.seconds
    while time.time() < t_end:
        chunk = ser.read(4096)
        if not chunk:
            continue
        for b in chunk:
            hist[b] += 1
            if len(order) < 64:
                order.append(b)
    ser.close()

    total = sum(hist.values())
    print(f'port={args.port} baud={args.baud} total={total} distinct={len(hist)}')
    if total == 0:
        print('  (无数据)')
        return 1

    print('  top bytes:')
    for b, n in hist.most_common(8):
        print(f'    0x{b:02X}  {n:6d}  {100.0*n/total:5.1f}%')

    if args.raw:
        print('  first 64:', ' '.join(f'{b:02X}' for b in order))

    # ---- beacon v4 解码 ----
    # byte = {4'b1010, bc_div[19], por_done, btn_state, rst_n}
    #        bit7..4     bit3        bit2       bit1        bit0
    #
    #   slow=0, por=1, btn=0, rst=1  -> 0b1010_0101 = 0xA5  正常
    #   slow=1, por=1, btn=0, rst=1  -> 0b1010_1101 = 0xAD  正常
    #   slow=0, por=0, btn=0, rst=0  -> 0b1010_0000 = 0xA0  POR 未完成
    #   slow=1, por=0, btn=0, rst=0  -> 0b1010_1000 = 0xA8  POR 未完成
    #   slow=0, por=1, btn=1, rst=0  -> 0b1010_0110 = 0xA6  按键按住
    #   slow=1, por=1, btn=1, rst=0  -> 0b1010_1110 = 0xAE  按键按住
    #
    # 注：慢速位每 39 ms 才翻一次，而帧周期约 0.8 ms，所以约 1/50 的帧会
    #     撞上"帧中途位翻转"，产生少量杂散字节（0xA0/0xA8/0xAA/0xF8/0x5A 等）。
    #     判读只看**占比最大的两个值**，杂散字节不影响结论。
    known = {
        0xA5: 'slow=0  正常 (por_done=1, rst_n=1)',
        0xAD: 'slow=1  正常 (por_done=1, rst_n=1)',
        0xA0: 'slow=0  POR 未完成 (rst_n=0)',
        0xA8: 'slow=1  POR 未完成 (rst_n=0)',
        0xA6: 'slow=0  按键按住中 (rst_n=0)',
        0xAE: 'slow=1  按键按住中 (rst_n=0)',
    }

    hit = [b for b in hist if b in known]
    if hit:
        print('  === beacon v4 解读 ===')
        normal = sum(hist[b] for b in (0xA5, 0xAD))
        porbad = sum(hist[b] for b in (0xA0, 0xA8))
        btnbad = sum(hist[b] for b in (0xA6, 0xAE))
        n = normal + porbad + btnbad
        if n:
            print(f'  占比: 正常 {100.0*normal/n:.1f}%  POR未完成 {100.0*porbad/n:.1f}%  '
                  f'按键按住 {100.0*btnbad/n:.1f}%')
        if normal > porbad + btnbad:
            print('  结论: 复位修复生效 —— POR 完成、rst_n=1、27MHz 时钟在跑')
        elif porbad > normal:
            print('  结论: POR 未完成 ==> 时钟没跑 / 计数器被卡')
        elif btnbad > normal:
            print('  结论: 按键被判为按住 ==> 引脚 87 仍为高（复位保持）')
        for b in sorted(hit):
            print(f'    0x{b:02X} x{hist[b]:<6d} {known[b]}')
    else:
        print('  === 不是 beacon v4 的字节 ===')
        print('  若出现 0xA9/0xAB 说明烧的是 v3 beacon')
        print('  若出现 0x5A 说明烧的是 v1/v2 beacon')
    return 0


if __name__ == '__main__':
    sys.exit(main())
