# -*- coding: utf-8 -*-
"""在任务板 ⑦ 行之后插入 ⑧（第 11 轮发现的测试台位映射分歧）—— 行定位插入，避免误合并 ✗"""
import io

p = "refs/素材库/双代理任务板.md"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")

row = ("| 🔄 **⑧ 测试台位映射分歧（第 11 轮发现，待修）** | 🔄 | "
       "`tb_t60.v` 里我自己写的 FX_CTRL 切片把**混响使能放在 bit3** ✗，"
       "而 `tdm_top.v` 的真实定义是 **`fx_rev_en = r_fxctrl[6]`** ✓、`fx_wet_sh = r_fxctrl[5:3]` ✓ "
       "（顺带确认：`dsp_host.cmd_fx('reverb') = 0x41` 是**对的** ✓，是我记忆里的 bit3 错了 ✗）。"
       "⇒ T60 取证时写的 `FX_CTRL=0x08`，在**真实顶层**的语义是「wet_sh=1 + 混响关」✗，"
       "与判据里「混响」的标注不符 ✓✗。<br>"
       "**影响评估**：T60 量的是**衰减率**（与增益无关 ✓）⇒ **V2/V3/V4 的数值仍成立** ✓；"
       "但**配置标签错了** ✗，且当时湿声被 halve（wet_sh=1）⇒ 涉及「电平」的结论要重看 ✓。<br>"
       "**修法**：把 `tb_t60.v` 的切片改成与顶层一致（bit6 + wet_sh=[5:3] ✓）后重跑，"
       "确认 `t60_check.py` 的 V2/V3/V4/V5 仍全过 ✓。（未修完前，T60 证据在挂账清单 ⑥ 里按「配置标签待更正」处理 ✗） |")

out, done = [], False
for ln in lines:
    out.append(ln)
    if not done and ln.startswith("| ✅ **⑦ 混响两缺陷"):
        out.append(row)
        done = True
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("  插入 ⑧ 行：%s" % ("成功 ✓" if done else "失败 ✗（未找到 ⑦ 行）"))
