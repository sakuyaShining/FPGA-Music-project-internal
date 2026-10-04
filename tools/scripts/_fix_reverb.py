# -*- coding: utf-8 -*-
"""第 9 轮：① 修任务板被合并的行；② 修混响两个真缺陷。
   D1 湿声电平差 42 dB（16 位线缓冲 vs 24 位干声，原来只做符号扩展 ✗）
   D2 默认 RV_FB=0xC0 让线缓冲饱和（91.9% 削顶 ✗）
"""
import io

# ---------- ① 任务板：拆开被合并的行 ----------
p = "refs/素材库/双代理任务板.md"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")
out, fixed = [], 0
for ln in lines:
    if "⑦ 处置 V5 缺陷" in ln and "为什么必须做" in ln:
        a, b = ln.split(" | **为什么必须做**", 1)
        out.append(a.rstrip() + " |")
        out.append("| ✅ **⑤ 电极遥测寄存器完成（第 7 轮）** | ✅ 2026-10-03 | **为什么必须做**" + b)
        fixed += 1
    else:
        out.append(ln)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("  任务板拆行 = %d" % fixed)

# ---------- ② D1：湿声电平对齐（fx_delay.v）----------
p = "src/rtl/fx_delay.v"
s = io.open(p, encoding="utf-8-sig").read()
old = "    wire signed [23:0] wet_s   = wet_sum >>> wet_sh;"
new = """    // ★★ D1 电平对齐（2026-10-03 第 9 轮修的真实缺陷）
    //   线缓冲是 16 位、干声是 24 位；原来只把抽头【符号扩展】到 24 位（数值不变 ✗）
    //   ⇒ 满幅抽头在 24 位域里只有 1/128 = **42 dB 偏低** ✗✗ ⇒ 混响实际听不见 ✓
    //   （demo 里"听得见混响"其实是 RV_FB=0.75 时线缓冲饱和削顶把它顶上去的 ✗ = 自激失真）
    //   修法：湿声先左移 8 位进入 24 位域 ✓（满幅 32767<<8 = 8388352，恰好不越 24 位上限 ✓），
    //         再按 wet_sh 衰减 ✓
    wire signed [31:0] wet_al = wet_sum <<< 8;
    wire signed [31:0] wet_at = wet_al >>> wet_sh;
    wire signed [23:0] wet_s  = wet_at[23:0];"""
assert old in s, "D1 未匹配"
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  D1 修好：湿声左移 8 位对齐 ✓")

# ---------- ③ D2：默认 RV_FB 0xC0 → 0x80 ----------
for p, old, new in (
    ("src/rtl/tdm_top.v",
     "6'd21: begin b_addr <= 8'h48; b_data <= 8'hC0; end // REV_FB = 0xC0 (0.75)",
     "6'd21: begin b_addr <= 8'h48; b_data <= 8'h80; end // REV_FB = 0x80 (0.5) ★ 第 9 轮：0xC0 会让线缓冲饱和削顶（实测 91.9% ✗）"),
    ("src/rtl/reg_bank.v",
     "mem[8'h48] = 8'hC0;   // RV_FB = 0.75",
     "mem[8'h48] = 8'h80;   // RV_FB = 0.5 ★ 第 9 轮：0.75 会让线缓冲饱和（实测 91.9% 样本削顶 ✗）"),
):
    s = io.open(p, encoding="utf-8-sig").read()
    if old in s:
        s = s.replace(old, new)
        io.open(p, "w", encoding="utf-8", newline="").write(s)
        print("  D2 修好：%s ✓" % p.split("/")[-1])
    else:
        print("  !! D2 未匹配：%s" % p)
