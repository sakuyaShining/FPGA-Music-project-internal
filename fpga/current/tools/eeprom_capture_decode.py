#!/usr/bin/env python3
"""eeprom_capture_decode.py —— 把 I²C 边沿捕获还原成"总线上到底发生了什么"

为什么需要它
------------
eeprom_capture_top 从 UART 吐出来的只有"谁在什么时刻跳变"：

    #EEPROBE 1F40
    000000,1,0
    000a20,0,0
    ...

这串东西本身不是证据 —— 证据是"第 58 个读字节后面主机到底回了 ACK 还是 NACK"。
本脚本把边沿还原成 START / 重复 START / 帧 / ACK / STOP，并对读事务的结尾
直接下判定。

用法
----
    python tools/eeprom_capture_decode.py  capture.txt
    python tools/eeprom_capture_decode.py  capture.txt --wave 20
    python tools/eeprom_capture_decode.py  capture.txt --json out.json
    python tools/eeprom_capture_decode.py  --selftest

输入格式
--------
两种都吃，靠有没有 `#EEPROBE` 表头区分：

    · 探针（真板）：`#EEPROBE XXXX` 之后每行 `TTTTTT,S,D`
    · 仿真导出（tb_ack_last）：只有 `TTTTTT,S,D` 行

时间戳单位不是固定的：探针是 27 MHz 拍，仿真导出是 ns。本脚本按 SCL 周期
自动判别，不猜。

判定规则
--------
I²C 规范：主机读 N 个字节，前 N-1 个回 ACK（继续要），第 N 个必须回 NACK
（告诉从机"到此为止"）。若第 N 个仍回 ACK，从机会立刻把**下一格**的 bit7
推上 SDA；那一格只要是 0，STOP 的上升沿就不存在 —— 总线当场卡死。

所以本脚本对每个读事务输出一行结论：
    · `last=ACK` ⇒ 违规
    · `last=NACK` ⇒ 合规
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROW = re.compile(r'^([0-9A-Fa-f]{1,8}),([01]),([01])\s*$')
HDR = re.compile(r'^#EEPROBE\s+([0-9A-Fa-f]+)')


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def parse(path):
    """返回 (header_count_or_None, [ (t, scl, sda), ... ])"""
    hdr = None
    rows = []
    bad = 0
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        m = HDR.match(line)
        if m:
            hdr = int(m.group(1), 16)
            continue
        m = ROW.match(line)
        if m:
            rows.append((int(m.group(1), 16), int(m.group(2)), int(m.group(3))))
        else:
            bad += 1
    return hdr, rows, bad


def guess_unit(rows):
    """按 SCL 周期判别时间戳单位。返回 (单位名, 每个 tick 的秒数, 实测 SCL 频率)。"""
    rise = []
    prev_scl = 1
    for t, scl, _ in rows:
        if scl == 1 and prev_scl == 0:
            rise.append(t)
        prev_scl = scl
    if len(rise) < 4:
        return ('未知', 0.0, 0.0)
    d = sorted(rise[i + 1] - rise[i] for i in range(len(rise) - 1))
    med = d[len(d) // 2]
    if med <= 0:
        return ('未知', 0.0, 0.0)
    # 100 kHz I²C：ns 单位下周期约 10000；27 MHz 拍下约 270。
    if med > 2000:
        return ('ns', 1e-9, 1.0 / (med * 1e-9))
    return ('27MHz 拍', 1.0 / 27e6, 27e6 / med)


# ---------------------------------------------------------------------------
# 还原成事务
# ---------------------------------------------------------------------------
def decode(rows):
    """把边沿还原成 [{'t0':.., 'segments':[{'kind':..,'t':..,'frames':[(b,ack)]}], 't_stop':..}]"""
    txns = []
    cur = None
    seg = None
    prev_scl, prev_sda = 1, 1
    bitcnt, byte = 0, 0

    def new_seg(kind, t):
        return {'kind': kind, 't': t, 'frames': [], 'ft': []}

    for t, scl, sda in rows:
        # ---- START / STOP：SCL 高时 SDA 跳变 ----
        if scl == 1 and prev_sda == 1 and sda == 0:
            if cur is None or cur.get('t_stop') is not None:
                cur = {'t0': t, 'segments': [], 't_stop': None, 't_last': t}
                txns.append(cur)
                seg = new_seg('START', t)
            else:
                seg = new_seg('RSTART', t)     # 重复起始位
            cur['segments'].append(seg)
            bitcnt, byte = 0, 0

        elif scl == 1 and prev_sda == 0 and sda == 1:
            if cur is not None and cur.get('t_stop') is None:
                cur['t_stop'] = t
            bitcnt, byte = 0, 0

        # ---- SCL 上升沿：采样 ----
        elif scl == 1 and prev_scl == 0:
            if cur is not None and cur.get('t_stop') is None and seg is not None:
                if bitcnt < 8:
                    byte = ((byte << 1) | sda) & 0xFF
                    bitcnt += 1
                else:
                    seg['frames'].append((byte, sda == 0))   # ack=True 表示从机/主机拉低
                    seg['ft'].append(t)
                    bitcnt, byte = 0, 0

        if cur is not None and cur.get('t_stop') is None:
            cur['t_last'] = t
        prev_scl, prev_sda = scl, sda

    return txns


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def seg_name(frames):
    if not frames:
        return '（无帧）'
    b0 = frames[0][0]
    return f'{"读" if (b0 & 1) else "写"} 0x{b0:02X}'


def describe(txn, idx):
    out = []
    segs = txn['segments']
    stop_ok = txn['t_stop'] is not None
    span = (txn['t_stop'] - txn['t0']) if stop_ok else (txn['t_last'] - txn['t0'])
    note = '有 STOP' if stop_ok else '**没有 STOP —— 总线被从机按住**'
    out.append(f'  事务 {idx}: {len(segs)} 段, 跨度 {span} tick, {note}')

    verdicts = []
    for si, sg in enumerate(segs):
        kind = 'S ' if sg['kind'] == 'START' else 'Sr'
        fr = sg['frames']
        out.append(f'    {kind} @{sg["t"]}  {seg_name(fr)}  帧数 {len(fr)}')
        if not fr:
            continue
        addr = fr[0][0]
        if addr & 1:
            # 读段：第 0 帧是设备地址（从机 ACK），其余是数据
            data = fr[1:]
            n_ack = sum(1 for _, a in data if a)
            n_nack = len(data) - n_ack
            last = 'ACK' if (data and data[-1][1]) else ('NACK' if data else '-')
            out.append(f'         读 {len(data)} 字节：ACK×{n_ack}  NACK×{n_nack}  '
                       f'末字节={last}')
            out.append(f'         数据: {bytes(b for b, _ in data)[:24].hex(" ")}'
                       f'{" ..." if len(data) > 24 else ""}')
            tail = data[-3:]
            out.append('         末 3 字节: ' + '  '.join(
                f'0x{b:02X}->{"ACK" if a else "NACK"}' for b, a in tail))
            if data:
                verdicts.append(('read_last_' + last.lower(), si, len(data), n_ack, n_nack))
        else:
            # 写段：地址 + 2 字节指针 + 数据
            body = fr[1:]
            out.append(f'         写 {len(body)} 帧（含 2 字节地址指针）'
                       f'，从机 ACK {sum(1 for _, a in body if a)}/{len(body)}')
            if len(body) >= 3:
                ptr = (body[0][0] << 8) | body[1][0]
                payload = body[2:]
                out.append(f'         指针 0x{ptr:04X}  数据 {len(payload)} 字节')
                out.append(f'         前 8 字节: '
                           f'{bytes(b for b, _ in payload[:8]).hex(" ")}')
    return '\n'.join(out), verdicts


def render_wave(rows, t_from, t_to, width=96):
    """把 [t_from, t_to] 窗口画成两行 ASCII 波形（`-` 高，`_` 低）。"""
    win = [r for r in rows if t_from <= r[0] <= t_to]
    if not win:
        return '（窗口内无记录）'
    # 窗口起点电平 = 窗口前最后一条记录的电平
    scl = sda = 1
    for t, s, d in rows:
        if t < t_from:
            scl, sda = s, d
        else:
            break
    step = max(1, (t_to - t_from + 1) // width)
    scl_row, sda_row = [], []
    i = 0
    t = t_from
    while t <= t_to and len(scl_row) < width:
        while i < len(win) and win[i][0] <= t:
            scl, sda = win[i][1], win[i][2]
            i += 1
        scl_row.append('-' if scl else '_')
        sda_row.append('-' if sda else '_')
        t += step
    return ('SCL ' + ''.join(scl_row) + '\n' +
            'SDA ' + ''.join(sda_row))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('capture', nargs='?', help='捕获文本文件')
    ap.add_argument('--wave', type=int, default=0, metavar='BYTES',
                    help='画事务结尾最后 BYTES 个字节的波形（0 = 不画，建议 3）')
    ap.add_argument('--json', help='把结论写成 JSON')
    ap.add_argument('--selftest', action='store_true', help='用内置样本自检')
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.capture:
        ap.print_help()
        return 2

    hdr, rows, bad = parse(args.capture)
    print(f'文件      : {args.capture}')
    print(f'表头      : {"#EEPROBE " + format(hdr, "04X") if hdr is not None else "无（仿真/离线导出）"}')
    print(f'记录      : {len(rows)} 条' + (f'（{bad} 行无法解析）' if bad else ''))
    if not rows:
        print('没有可解析的记录。')
        return 1

    unit, sec_per_tick, scl_hz = guess_unit(rows)
    print(f'时间单位  : {unit}（按 SCL 周期推断，实测 SCL ≈ {scl_hz / 1000:.1f} kHz）')

    txns = decode(rows)
    print(f'事务      : {len(txns)} 个')

    summary = {'file': str(args.capture), 'records': len(rows),
               'unit': unit, 'scl_hz': round(scl_hz, 1),
               'transactions': []}

    problems = 0
    for i, txn in enumerate(txns, 1):
        print()
        text, verdicts = describe(txn, i)
        print(text)
        if args.wave:
            segs = txn['segments']
            sg = segs[-1]
            if sg['frames'] and sg['ft']:
                end = txn['t_stop'] if txn['t_stop'] is not None else sg['ft'][-1]
                # 窗口 = 最后 N 个字节（含各自的 ACK 槽），从第 N 个之前的
                # 那个 ACK 时刻起算，保证起始处是一条完整字节
                k = max(1, args.wave)
                i0 = max(0, len(sg['ft']) - k - 1)
                t_from = sg['ft'][i0] if i0 else sg['t']
                print(f'  波形（最后 {k} 个字节，横轴 {end - t_from} 个 tick）：')
                for ln in render_wave(rows, t_from, end, 88).splitlines():
                    print('    ' + ln)
        for kind, si, n, ack, nack in verdicts:
            rec = {'segment': si, 'bytes': n, 'ack': ack, 'nack': nack,
                   'verdict': kind}
            summary['transactions'].append({'index': i, **rec})
            if kind == 'read_last_ack':
                problems += 1
                print(f'    >> 违规：最后一个读字节回了 ACK（应为 NACK）')

    print()
    print('-' * 66)
    n_read = sum(1 for t in summary['transactions'])
    if problems:
        print(f' 结论: {n_read} 个读事务，其中 {problems} 个末字节回了 ACK —— 违反 I²C 规范')
        print('       从机会继续把下一格推上 SDA；那一格 bit7=0 时 STOP 就发不出来。')
        rc = 1
    else:
        print(f' 结论: {n_read} 个读事务，末字节全部 NACK —— 符合 I²C 规范')
        rc = 0
    print('-' * 66)

    if args.json:
        summary['read_transactions'] = n_read
        summary['violations'] = problems
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                   encoding='utf-8')
        print(f' 已写出 {args.json}')
    return rc


# ---------------------------------------------------------------------------
# 自检：手搓一段最短的合规序列，确认解码器本身没坏
# ---------------------------------------------------------------------------
def selftest():
    """造一个 START + 0xA1 + 2 字节（ACK, NACK）+ STOP，检查解码结果。

    这是"解码器自己的单元测试"。它不替代真捕获 —— 只是保证当捕获文件
    真送进来时，解析这一层不会先崩。
    """
    rows = []
    t = [0]

    def ev(scl, sda):
        t[0] += 10
        rows.append((t[0], scl, sda))

    def bit(b):
        ev(0, b)
        ev(1, b)

    ev(1, 1)
    ev(1, 0)                      # START
    for b in (1, 0, 1, 0, 0, 0, 0, 1):   # 0xA1
        bit(b)
    ev(0, 0)
    ev(1, 0)                      # 从机 ACK
    for b in (1, 1, 0, 0, 1, 1, 0, 0):   # 0xCC
        bit(b)
    ev(0, 0)
    ev(1, 0)                      # 主机 ACK
    for b in (1, 0, 1, 0, 1, 0, 1, 0):   # 0xAA
        bit(b)
    ev(0, 1)                      # 主机 NACK：SCL 低时先释放 SDA
    ev(1, 1)                      # 再把 SCL 抬高 —— ACK 槽
    ev(0, 0)
    ev(1, 0)
    ev(1, 1)                      # STOP

    txns = decode(rows)
    ok = True
    if len(txns) != 1:
        print(f'[FAIL] 事务数 {len(txns)}，期望 1'); ok = False
    else:
        fr = txns[0]['segments'][0]['frames']
        want = [(0xA1, True), (0xCC, True), (0xAA, False)]
        if fr != want:
            print(f'[FAIL] 帧 {fr}，期望 {want}'); ok = False
        if txns[0]['t_stop'] is None:
            print('[FAIL] 没解出 STOP'); ok = False
    print('解码器自检: ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
