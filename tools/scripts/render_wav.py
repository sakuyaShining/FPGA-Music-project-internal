# -*- coding: utf-8 -*-
"""
render_wav.py —— 把仿真的每样本输出渲染成 WAV

【为什么要单独写一个渲染器】
   "听不到声音"可能是三种完全不同的原因：
     1. 文件太短          -> 做长的
     2. WAV 头写错了      -> 用标准写法并回读校验
     3. 采样率太冷门      -> 同时输出 44.1 kHz 版本
   这一版把三种都处理掉，并且【回读文件校验】，而不是"写完就报成功"。

【回读校验做什么】
   · 重新打开刚写的 WAV，检查头部字段
   · 统计非零样本比例、峰值、RMS
   · 如果非零比例过低，直接报"可能是静音文件"而不是默默成功
"""
import argparse
import os
import struct
import sys

RATE_ALIASES = {
    "39062.5": 39062,       # 本项目的仿真采样率（clk 5MHz / NSLOT 128）
    "46875": 46875,         # 目标硬件采样率（clk 27MHz / 576 拍）
    "44100": 44100,
    "48000": 48000,
}


def read_dump(path):
    v, nskip = [], 0
    for l in open(path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            v.append(float(l.split()[1]))
        except ValueError:
            nskip += 1
    if nskip:
        print("  （跳过 %d 个非数值样本 —— 流水线建立前正常）" % nskip)
    return v


def resample_linear(x, src, dst):
    """线性插值重采样。够用：本用途只是换一个播放器友好的采样率。"""
    if src == dst:
        return list(x)
    n = int(len(x) * dst / src)
    out = []
    for i in range(n):
        p = i * src / dst
        i0 = int(p)
        i1 = min(i0 + 1, len(x) - 1)
        fr = p - i0
        out.append(x[i0] * (1.0 - fr) + x[i1] * fr)
    return out


def write_wav(path, samples, rate):
    peak = max(1.0, max(abs(v) for v in samples))
    # -1 dBFS：0.891 ≈ 10^(-1/20)
    scale = (0.891 * 32767.0) / peak
    data = bytearray()
    for v in samples:
        q = int(round(v * scale))
        q = -32768 if q < -32768 else (32767 if q > 32767 else q)
        data += struct.pack("<h", q)
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
           + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate,
                                   rate * 2, 2, 16)
           + b"data" + struct.pack("<I", len(data)))
    with open(path, "wb") as fh:
        fh.write(hdr)
        fh.write(bytes(data))
    return path


def verify_wav(path, expect_rate):
    """★ 回读刚写的文件并校验 —— 不靠"写完就报成功"。

       WAV 的 fmt 块实际布局（这里曾经漏掉最前面的 audio format 字段，
       导致所有偏移差 2 字节，读出来的全是垃圾）：
         偏移 16: 块大小 (4)
         偏移 20: audio format (2)   <- 必须有
         偏移 22: 声道数 (2)
         偏移 24: 采样率 (4)
         偏移 28: 字节率 (4)
         偏移 32: 块对齐 (2)
         偏移 34: 位深 (2)
         偏移 36: "data"
    """
    raw = open(path, "rb").read()
    ok = True
    if len(raw) < 44:
        print("    ✗ 文件太短（%d 字节）" % len(raw))
        return False
    if raw[0:4] != b"RIFF" or raw[8:12] != b"WAVE":
        print("    ✗ 头部不是 RIFF/WAVE"); ok = False
    if raw[36:40] != b"data":
        print("    ✗ 偏移 36 不是 data 块"); ok = False
    fmt, ch, sr, br, ba, bits = struct.unpack("<HHIIHH", raw[20:36])
    n = (len(raw) - 44) // 2
    vals = struct.unpack("<%dh" % n, raw[44:44 + n * 2])
    nz = sum(1 for v in vals if v != 0)
    pk = max(abs(v) for v in vals) if n else 0
    rms = (sum(float(v) * v for v in vals) / max(1, n)) ** 0.5
    print("    回读：fmt=%d(1=PCM) %d 声道 %d Hz %d bit  样本 %d"
          % (fmt, ch, sr, bits, n))
    print("          非零 %.1f%%   峰值 %d   RMS %.0f"
          % (100.0 * nz / max(1, n), pk, rms))
    if fmt != 1:
        print("    ✗ 不是 PCM"); ok = False
    if sr != expect_rate:
        print("    ✗ 采样率不符（头里是 %d，期望 %d）" % (sr, expect_rate)); ok = False
    if nz < n * 0.5:
        print("    ✗★ 非零样本不到一半 —— 很可能是静音文件！"); ok = False
    if pk < 1000:
        print("    ✗★ 峰值过低 —— 可能几乎无声！"); ok = False
    print("    => %s" % ("格式与内容校验通过 ✓" if ok else "有问题 ✗"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--src-rate", default="39062.5")
    ap.add_argument("--rates", default="44100", help="额外输出的采样率，逗号分隔")
    a = ap.parse_args()

    src = float(a.src_rate)
    print("读入 %s" % a.dump)
    x = read_dump(a.dump)
    print("  %d 个样本  %.2f s @ %.1f Hz" % (len(x), len(x) / src, src))

    base = os.path.splitext(a.out)[0]
    targets = [int(round(src))] + [RATE_ALIASES.get(r.strip(), int(r.strip()))
                                   for r in a.rates.split(",") if r.strip()]
    seen = set()
    allok = True
    for r in targets:
        if r in seen:
            continue
        seen.add(r)
        y = resample_linear(x, src, r) if r != int(round(src)) else x
        p = "%s_%d.wav" % (base, r) if len(targets) > 1 else "%s.wav" % base
        write_wav(p, y, r)
        print("\n写出 %s  (%.2f s @ %d Hz, %.0f KB)"
              % (p, len(y) / float(r), r, os.path.getsize(p) / 1024.0))
        allok = verify_wav(p, r) and allok
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
