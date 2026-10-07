#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gatecov_check.py —— 门禁覆盖审计：哪些测试台 / 判据脚本**存在但没被挂上**

【为什么要有这一条（2026-10-07 发现）】
  我在补滑音判据时偶然发现：`tb_pitch_mod.v` + `pitch_mod_check.py` +
  `tb_pitch_mod512.v` + `pitch_mod512_check.py` 四个文件**都存在**，但门禁
  `regress_all.py` 里**只登记了 `07 regpitch`** —— 那条验的是"寄存器写入 → 音高"，
  **不是滑音/颤音本身**。也就是说最有信息量的一条判据长期没跑。
  ⇒ 这类"写了判据但没挂上"的漏，和"文档说做了但实际没有"是同一类问题：
    它**看起来有覆盖**（文件在那儿、脚本也在），实际没有。
  ⇒ 需要机械审计，而不是靠人偶然发现。

【口径】
  · 候选测试台 = `src/sim/tb_*.v`
  · 候选判据   = `tools/scripts/*_check.py`
  · "已挂上" = 名字出现在 `tools/scripts/regress_all.py` 的文本里
  · 未被引用的列出，并给出**分类提示**（便于人工判断是真漏还是有意不挂）：
       - 名字以 `tb_` 开头但疑似"子测试台/被 include"的（本项目无 include，故不适用）
       - 一次性/调试用的（`_` 前缀）
       - 需要特殊环境（如 `i2c_master` 属 v2 资产）

【重要】本审计**只报不判、退出码恒为 0**：
  "没挂在门禁里"不等于"该挂" —— 有些测试台是一次性排查用的，本就不该进闸口。
  真正的判定要人看（本脚本在输出里给出分类提示，降低判读成本）。

用法：python tools/scripts/gatecov_check.py [--simdir DIR]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM = os.path.join(ROOT, "src", "sim")
SCR = os.path.join(ROOT, "tools", "scripts")
GATE = os.path.join(SCR, "regress_all.py")


def main():
    #   --simdir 是门禁 judge_script 的统一传参，本判据不需要，但必须接受
    gate = open(GATE, encoding="utf-8", errors="replace").read()

    tbs = sorted(f for f in os.listdir(SIM)
                 if f.startswith("tb_") and f.endswith(".v"))
    cks = sorted(f for f in os.listdir(SCR)
                 if f.endswith("_check.py"))

    miss_tb = [t for t in tbs if t not in gate]
    miss_ck = [c for c in cks if c not in gate]

    print("=" * 74)
    print(" 门禁覆盖审计")
    print("=" * 74)
    print(" 测试台：存在 %d 个，门禁引用 %d 个，**未引用 %d 个**"
          % (len(tbs), len(tbs) - len(miss_tb), len(miss_tb)))
    for t in miss_tb:
        #   分类提示，降低人工判读成本
        why = []
        if t.startswith("tb__") or t.startswith("tb_1") or t.startswith("tb_x"):
            why.append("疑似一次性")
        if "i2c" in t or "mpr121" in t:
            why.append("v2 资产（不参与出货）")
        if "pad" in t and "padtop" not in t:
            why.append("触控子模块（可能已被顶层套件覆盖）")
        tag = ("  ← " + " / ".join(why)) if why else ""
        print("   - %-32s%s" % (t, tag))

    print()
    print(" 判据脚本：存在 %d 个，门禁引用 %d 个，**未引用 %d 个**"
          % (len(cks), len(cks) - len(miss_ck), len(miss_ck)))
    for c in miss_ck:
        why = []
        if c.startswith("_"):
            why.append("一次性")
        tag = ("  ← " + " / ".join(why)) if why else ""
        print("   - %-32s%s" % (c, tag))

    print("-" * 74)
    print(" ⚠ 判读提示：")
    print("   · '没挂在门禁里' ≠ '该挂' —— 一次性排查用的本就不该进闸口。")
    print("   · 真正要处置的是：**判据本身有价值、且已经写好、但没人跑**那一类。")
    print("     判法是看它有没有对应的 `*_check.py` 与稳定的输出文件约定。")
    print("   · 本审计退出码恒为 0（只报不判），避免不精确的启发式把门禁变红。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
