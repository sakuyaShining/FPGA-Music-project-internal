#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_video_timing.py -- 480x272 RGB 屏行场时序不变量自检

为什么要有这个脚本：
    本机没有装 Verilog 仿真器，而上线前最想确认的恰恰是几个"差一"问题：
      · DE 拉高的像素数是不是**正好** 480（不是 479 也不是 481）？
      · DE 拉高的行数是不是**正好** 272？
      · 同步脉冲有没有和有效区重叠？
      · 一行的总拍数是不是设计的 560、一帧是不是 297？
    这些用肉眼数容易错，写成脚本让机器数，一秒出结果。

    它不替代仿真：脚本验证的是**时序算术**（参数取值、区间边界），
    不能验证 Verilog 的语法/语义。Verilog 侧的保证来自 Gowin 综合器
    成功 elaborate + 布局布线通过 + 引脚报告核对。

参数必须与 src/rtl/video_timing.v 的 default 保持一致。
改 RTL 参数时，这里也要同步改，然后重跑本脚本。
"""

# --- 与 video_timing.v 的 parameter 默认值一一对应 -------------------------
H_ACTIVE = 480
H_BP     = 30
H_FP     = 10
H_SYNC_W = 40

V_ACTIVE = 272
V_BP     = 5
V_FP     = 5
V_SYNC_W = 15

# --- 与 gowin_rpll.v 相关的时钟（标称值，见该文件顶部说明）-----------------
PIX_CLK_HZ = 9_000_000

# --- 与 test_pattern.v 一致 ------------------------------------------------
STRIP_H = 32
BAR_W   = 60
CELL_W  = 32      # 对应 x[8:5]，每格 32 像素

H_TOTAL = H_ACTIVE + H_BP + H_FP + H_SYNC_W
V_TOTAL = V_ACTIVE + V_BP + V_FP + V_SYNC_W

ok = True


def check(name, got, want):
    global ok
    mark = "OK  " if got == want else "FAIL"
    if got != want:
        ok = False
    print("  [%s] %-46s got=%-6s want=%s" % (mark, name, got, want))


print("=" * 72)
print("1) 计数器总量")
print("=" * 72)
check("H_TOTAL (一行总拍数)", H_TOTAL, 560)
check("V_TOTAL (一帧总行数)", V_TOTAL, 297)

print()
print("=" * 72)
print("2) DE 有效区宽度 —— 最关键的'差一'检查")
print("=" * 72)
# RTL: de <= (hcnt >= H_BP) && (hcnt < H_BP+H_ACTIVE) && ...
h_de = [h for h in range(H_TOTAL) if H_BP <= h < H_BP + H_ACTIVE]
v_de = [v for v in range(V_TOTAL) if V_BP <= v < V_BP + V_ACTIVE]
check("每行 DE 拉高的拍数", len(h_de), 480)
check("每帧 DE 拉高的行数", len(v_de), 272)
check("每帧有效像素总数", len(h_de) * len(v_de), 480 * 272)
check("DE 行区间起点", h_de[0], H_BP)
check("DE 行区间终点(闭)", h_de[-1], H_BP + H_ACTIVE - 1)
check("DE 场区间起点", v_de[0], V_BP)
check("DE 场区间终点(闭)", v_de[-1], V_BP + V_ACTIVE - 1)

print()
print("=" * 72)
print("3) 同步脉冲位置与宽度（低有效）")
print("=" * 72)
H_SYNC_BEG = H_BP + H_ACTIVE + H_FP
H_SYNC_END = H_SYNC_BEG + H_SYNC_W
V_SYNC_BEG = V_BP + V_ACTIVE + V_FP
V_SYNC_END = V_SYNC_BEG + V_SYNC_W

h_sync_low = [h for h in range(H_TOTAL) if H_SYNC_BEG <= h < H_SYNC_END]
v_sync_low = [v for v in range(V_TOTAL) if V_SYNC_BEG <= v < V_SYNC_END]
check("HSYNC 低电平拍数", len(h_sync_low), H_SYNC_W)
check("VSYNC 低电平行数", len(v_sync_low), V_SYNC_W)
check("HSYNC 区间落在有效区之后", len(h_sync_low) > 0 and h_sync_low[0] > h_de[-1], True)
check("VSYNC 区间落在有效区之后", len(v_sync_low) > 0 and v_sync_low[0] > v_de[-1], True)
check("HSYNC 不越界 (末拍 < H_TOTAL)", h_sync_low[-1] < H_TOTAL, True)
check("VSYNC 不越界 (末行 < V_TOTAL)", v_sync_low[-1] < V_TOTAL, True)
# 同步脉冲必须正好接在下一行/帧的后沿之前，中间不能有缝
check("HSYNC 紧接行末(到 H_TOTAL 为止)", h_sync_low[-1], H_TOTAL - 1)
check("VSYNC 紧接帧末(到 V_TOTAL 为止)", v_sync_low[-1], V_TOTAL - 1)

print()
print("=" * 72)
print("4) frame_tick 与场频")
print("=" * 72)
tick = [(h, v) for h in range(H_TOTAL) for v in range(V_TOTAL)
        if h == H_TOTAL - 1 and v == V_TOTAL - 1]
check("每帧 frame_tick 脉冲个数", len(tick), 1)
fps = PIX_CLK_HZ / (H_TOTAL * V_TOTAL)
print("  [INFO] 场频 = %.1f Hz  (%.1f MHz / (%d x %d))"
      % (fps, PIX_CLK_HZ / 1e6, H_TOTAL, V_TOTAL))
check("场频落在 50~65 Hz 的可用区间", 50.0 <= fps <= 65.0, True)

print()
print("=" * 72)
print("5) 测试图案布局")
print("=" * 72)
check("彩条段数 * 每段宽度 == 行宽", BAR_W * 8, H_ACTIVE)
# RTL: cell_idx = x[8:5] -> 0..14，覆盖 x = 0..479
cells = sorted(set(x >> 5 for x in range(H_ACTIVE)))
check("计数条格子数", len(cells), 15)
check("格子索引范围", (cells[0], cells[-1]), (0, 14))
check("格子覆盖最后一个像素 (479>>5)", cells[-1], H_ACTIVE - 1 >> 5)
check("每格宽度 * 格数 >= 行宽", CELL_W * len(cells), 480)
check("计数条高度 < 画面高度", STRIP_H < V_ACTIVE, True)
check("计数条顶部 y", V_ACTIVE - STRIP_H, 240)

print()
print("=" * 72)
if ok:
    print("全部通过：时序算术没有发现问题。")
else:
    print("有检查项未通过，见上面的 FAIL 行。")
print("=" * 72)
raise SystemExit(0 if ok else 1)
