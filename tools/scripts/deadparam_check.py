#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deadparam_check.py —— RTL「死参数 / 未使用信号」审计（阶段 4 收敛维护）

【为什么要这一条】
  本项目反复出现同一类"文档与实现脱节"的问题，已发现两例：
    · `pitch_mod.v` 的 `GLIDE_CUT`：参数声明 + 文档都写了"低于阈值直接归零"，
      但衰减式 `(gq > stp) ? gq-stp : 0` 本身就精确收敛 ⇒ **从未读它**。
    · `note_map.v` 的 `found_open` 档：加了却不可达（`29 inv` 已证实）。
  这类残留有两个害处：
    ① 让读者以为存在某个行为，从而**写错判据**（我就在 GLIDE_CUT 上写了假失败用例）；
    ② 掩盖真正的缺陷（死代码会让人以为路径已被覆盖）。
  ⇒ 需要一次**机械的、可复跑的**审计，而不是靠人偶然发现。

【审计口径（保守，只报高置信项）】
  A) **模块参数**：声明后在整个文件里除声明处外**从未出现** ⇒ 死参数。
     只统计 `parameter`（不统计 `localparam`，后者可能仅供生成用）。
  B) **声明但从未使用的 wire/reg**：名字出现次数 == 1（仅声明处）⇒ 可疑。
     排除：以 `_dbg`/`dbg_` 开头的（诊断用，可能被层次引用）、
           以及 `integer`/`genvar` 循环变量。

【注意（避免自己制造假阳性 —— 本会话已踩三次"检查器自己有 bug"）】
  · 只用**词边界**匹配，避免子串误命中（如 `gq` 命中 `gq_cal`/`gq_eff`）。
  · 层次引用（`u_top.xxx`）会算作"使用"，所以对 tb 专用的调试信号可能误报；
    故把 `_dbg`/`dbg_` 一律排除。
  · 本脚本**只报、不判**：真正的结论要人看。退出码恒为 0，
    以免一个不精确的启发式把门禁变红。

用法：python tools/scripts/deadparam_check.py [--simdir DIR] [--top N]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RTL = os.path.join(ROOT, "src", "rtl")


def strip_comments(src):
    """去掉 // 行注释与 /* */ 块注释（注释里的提及不算"使用"）"""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    out = []
    for ln in src.split("\n"):
        #   简单处理：整行 // 之后的都去掉（本项目没有把 // 写在字符串里的情况）
        i = ln.find("//")
        out.append(ln[:i] if i >= 0 else ln)
    return "\n".join(out)


def audit_file(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    src = strip_comments(raw)
    name = os.path.basename(path)
    dead_params, unused_sigs = [], []

    #---- A) 模块参数：声明后从未再出现
    for m in re.finditer(r"\bparameter\b\s+(?:integer\s+)?(?:signed\s+)?"
                         r"(?:\[[^\]]*\]\s*)?(\w+)\s*=", src):
        p = m.group(1)
        #   统计"词边界"出现次数；声明本身算 1 次
        uses = len(re.findall(r"\b%s\b" % re.escape(p), src))
        if uses <= 1:
            dead_params.append(p)

    #---- B) 声明但未使用的 wire/reg
    decl = re.compile(r"\b(wire|reg)\b\s*(?:signed\s*)?(?:\[[^\]]*\]\s*)?"
                      r"([\w,\s]+?)\s*;")
    for m in decl.finditer(src):
        for nm in m.group(2).split(","):
            nm = nm.strip()
            if not nm or not re.match(r"^\w+$", nm):
                continue
            if nm.startswith("_dbg") or nm.startswith("dbg_"):
                continue
            uses = len(re.findall(r"\b%s\b" % re.escape(nm), src))
            if uses <= 1:
                unused_sigs.append(nm)

    return name, dead_params, unused_sigs


def main():
    top = 40
    for i, a in enumerate(sys.argv):
        if a == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
    #   --simdir 是门禁 judge_script 的统一传参，本判据不需要，但必须接受
    files = sorted(f for f in os.listdir(RTL) if f.endswith(".v"))

    print("=" * 74)
    print(" RTL 死参数 / 未使用信号 审计")
    print("=" * 74)

    tot_p = tot_s = 0
    rows = []
    for f in files:
        nm, dp, us = audit_file(os.path.join(RTL, f))
        if dp or us:
            rows.append((nm, dp, us))
            tot_p += len(dp)
            tot_s += len(us)

    for nm, dp, us in rows:
        print(" %s" % nm)
        for p in dp:
            print("     [死参数]      %s" % p)
        for u in us[:top]:
            print("     [未使用信号]  %s" % u)
        if len(us) > top:
            print("     …（其余 %d 个未使用信号省略）" % (len(us) - top))

    print("-" * 74)
    print(" 合计：死参数 %d 个，未使用信号 %d 个（跨 %d 个文件）"
          % (tot_p, tot_s, len(rows)))
    print()
    print(" ⚠ 判读提示：")
    print("   · 本审计是**启发式**，会误报两类：")
    print("       ① 仅被层次引用（tb 用 u_top.xxx）的信号；")
    print("       ② 为将来预留、当前有意不用的参数。")
    print("   · 因此本脚本**退出码恒为 0**、只报不判 —— ")
    print("     一个不精确的启发式不该把门禁变红（否则红灯疲劳）。")
    print("   · 真正要处置的只有『文档声称有某行为、而实现没读该参数』这一类；")
    print("     判定方法是**回到文档**看它有没有被当作契约描述。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
