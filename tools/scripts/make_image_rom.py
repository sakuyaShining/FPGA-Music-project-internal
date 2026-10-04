#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_image_rom.py -- 把一张图片转换成 FPGA 用的 8 色索引 ROM 数据

用途
    Tang Nano 9K 的 4.3 寸屏（480x272）显示一张静态图片。
    产出 src/gowin/bringup_9k/image_rom.bin，由 src/rtl/image_rom.v 通过
    $readmemb 读入并映射成 BSRAM（实测占 24/26 块，93%，已是上限）。

为什么只有 8 色
    GW1NR-9 的 BSRAM 只有 26 块共 468 Kbit。
    480x272 全彩 16 位需要 2,088,960 bit —— 是它的 4.5 倍，放不下。
    实测 131072 x 3 bit = 24 块。想再提高画质只能换存储介质
    （板载 64 Mbit PSRAM / 32 Mbit SPI Flash），需要另写控制器。

用法
    python make_image_rom.py <输入图片> [选项]
    # 换图后必须同步更新 src/rtl/image_view.v 里的 PAL0..PAL7
    # （本脚本会直接把调色板打印成 Verilog localparam，粘过去即可）

参数
    --crop {top,center,bottom}   裁剪锚点（竖构图图片配横屏时用），默认 top
    --contrast F                 对比度增强倍数，默认 1.25
    --saturation F               饱和度增强倍数，默认 1.5
    --colors N                   调色板颜色数，默认 8（**改成非 8 必须同步改 RTL 位宽**）
    --out PATH                   输出 .bin 路径
    --preview PATH               同时输出一张 PNG 预览（强烈建议看一眼再烧板）
"""

import argparse
import io
import os
import sys
from collections import Counter

try:
    from PIL import Image, ImageEnhance
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow")

SCREEN_W, SCREEN_H = 480, 272
# ROM 深度取 2 的幂（对 BSRAM 映射最友好）；比 130560 多出的 512 个条目填 0
ROM_DEPTH = 131072


def rgb_to_565(r, g, b):
    """RGB888 -> RGB565，与屏幕驱动的像素格式一致"""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def crop_fill(img, w, h, anchor):
    """等比缩放到"填满"目标框，再按 anchor 裁剪掉多余部分（不拉伸变形）"""
    ratio = max(w / img.width, h / img.height)
    big = img.resize((max(1, round(img.width * ratio)),
                      max(1, round(img.height * ratio))), Image.LANCZOS)
    left = (big.width - w) // 2
    if anchor == "top":
        top = 0
    elif anchor == "bottom":
        top = big.height - h
    else:
        top = (big.height - h) // 2
    return big.crop((left, top, left + w, top + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--crop", choices=["top", "center", "bottom"], default="top")
    ap.add_argument("--contrast", type=float, default=1.25)
    ap.add_argument("--saturation", type=float, default=1.5)
    ap.add_argument("--colors", type=int, default=8)
    ap.add_argument("--out", default=None)
    ap.add_argument("--preview", default=None)
    args = ap.parse_args()

    if args.colors != 8:
        print("!! 警告：RTL 里 image_rom.v 按 3 bit/像素写死，"
              "改成别的颜色数必须同步改存储器位宽和 image_view.v 的 case。")

    here = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.normpath(os.path.join(here, "..", "..",
                                         "src", "gowin", "bringup_9k"))
    out_bin = args.out or os.path.join(proj, "image_rom.bin")
    out_prev = args.preview or os.path.join(proj, "image_rom_preview.png")

    img = Image.open(args.image).convert("RGB")
    print("输入: %s  %dx%d  宽高比 %.3f" %
          (args.image, img.width, img.height, img.width / img.height))

    frame = crop_fill(img, SCREEN_W, SCREEN_H, args.crop)
    if args.contrast != 1.0:
        frame = ImageEnhance.Contrast(frame).enhance(args.contrast)
    if args.saturation != 1.0:
        frame = ImageEnhance.Color(frame).enhance(args.saturation)

    pal_img = frame.convert("P", palette=Image.ADAPTIVE,
                            colors=args.colors, dither=Image.FLOYDSTEINBERG)
    pal_rgb = pal_img.getpalette()[: args.colors * 3]
    indices = list(pal_img.getdata())

    # 写出 $readmemb 用的二进制文件：
    #   每行 3 个字符（000~111），行数 = ROM_DEPTH
    #   数据宽度必须和 Verilog 里存储器位宽完全一致，
    #      否则 Gowin 会报 EX2526 并**静默丢弃内容**（存储器被整个优化掉）。
    with io.open(out_bin, "w") as f:
        for i in range(ROM_DEPTH):
            v = indices[i] if i < len(indices) else 0
            f.write(format(v, "0%db" % (args.colors - 1).bit_length()) + "\n")

    size = os.path.getsize(out_bin)
    print("已写出: %s  (%d 行, %.1f KB)" % (out_bin, ROM_DEPTH, size / 1024.0))
    print("注意: 行尾是 CRLF（Windows 文本模式），Gowin 能正常解析。")

    # 预览：让眼睛先确认，再烧板
    pal_img.convert("RGB").save(out_prev)
    print("预览图: %s   <- 烧板前先看一眼" % out_prev)

    print("\n把下面这段粘进 src/rtl/image_view.v（替换原有的 PAL0..PAL7）:")
    for i in range(args.colors):
        r, g, b = pal_rgb[i * 3], pal_rgb[i * 3 + 1], pal_rgb[i * 3 + 2]
        print("    localparam [15:0] PAL%d = 16'h%04X;   // RGB %3d,%3d,%3d"
              % (i, rgb_to_565(r, g, b), r, g, b))

    cnt = Counter(indices)
    total = len(indices)
    print("\n各色像素占比: " + "  ".join(
        "P%d=%.1f%%" % (i, 100.0 * cnt.get(i, 0) / total) for i in range(args.colors)))


if __name__ == "__main__":
    main()
