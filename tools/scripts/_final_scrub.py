# -*- coding: utf-8 -*-
"""最终收尾：一次性完成四件事，只作用于公开版会包含的文件。

  1. 精确修正
     - 恢复被误替换的网络术语（"系统协作" -> "系统代理"）
     - 删除"分工：RTL 由 AI 实现"这类内部说明行
     - 重写"两个代理共用一个工作区"这类句子
  2. 剥掉指向公开版不存在路径的引用（refs/ notes/ 素材库 等）
  3. 清理因此产生的悬空标点（空的括号、孤立的连接词）
  4. 报告改动

顺序很关键：先剥引用，再清残渣（反过来的话残渣还会留下）。
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRANCH = "public"

# ---- 1. 精确修正 ----
EXACT = [
    ("tools/host/build_exe.py",
     "# 本机 pip 曾因【Windows 系统协作指向一个不存在的协作】而全部失败",
     "# 本机 pip 曾因【Windows 系统代理指向一个不存在的代理】而全部失败"),
    ("tools/host/serial_link.py",
     "本机 pip 因系统协作不可用而装不上",
     "本机 pip 因系统代理不可用而装不上"),
    ("tools/scripts/regress_all.py",
     "两个代理共用一个工作区，最大风险是\"一方改 RTL 时悄悄破坏另一方的已验证性质\"。",
     "单一工作区并行改动的最大风险，是一处修改悄悄破坏另一处已验证的性质。"),
    ("docs/02-技术方案/14-必须项实施计划.md",
     "> 分工：RTL 由 AI 实现；架构与产品定义由用户拍板；用户负责验收与答辩可辩护性\n",
     ""),
]

# ---- 2. 要剥掉的路径引用 ----
DROP = [
    re.compile(r"`refs/[^`]*`"),
    re.compile(r"`notes/[^`]*`"),
    re.compile(r"`PROJECT_MEMORY\.md`"),
    re.compile(r"`tools/pylib[^`]*`"),
    re.compile(r"`(?:src/rtl/)?(?:bringup_top|image_rom|image_view|lcd_480x272|test_pattern)\.v`"),
    re.compile(r"refs/[\w\u4e00-\u9fff/\-\.]+"),
    re.compile(r"notes/[\w\u4e00-\u9fff/\-\.]+"),
    re.compile(r"PROJECT_MEMORY\.md"),
    re.compile(r"tools/pylib[\w/\-\.]*"),
    re.compile(r"[\w\u4e00-\u9fff/\-]*素材库[\w\u4e00-\u9fff/\-\.]*"),
    re.compile(r"`(?:src/rtl/)?(?:bringup_top|image_rom|image_view|lcd_480x272|test_pattern)\.v`"),
]

# ---- 3. 残渣清理 ----
TIDY = [
    (re.compile(r"[（(]\s*(?:见|详见|参见|依据见|已下载到|来源见)?\s*[）)]"), ""),
    (re.compile(r"[，,;；]?\s*(?:详见|参见|依据见)\s*[）)]"), "）"),
    (re.compile(r"[，,;；]?\s*见\s*[）)]"), "）"),
    (re.compile(r"(?:详见|参见)\s*$"), ""),
    (re.compile(r"[（(]\s*[，,;；]\s*"), "（"),
    (re.compile(r"[（(]\s+"), "（"),
    (re.compile(r"\s+[）)]"), "）"),
    (re.compile(r"[ \t]{2,}"), " "),
    (re.compile(r"\*\*[ \t]+"), "**"),
    (re.compile(r"[ \t]+\*\*"), "**"),
    (re.compile(r"[ \t]+$"), ""),
    (re.compile(r"[，,]\s*[，,]"), "，"),
    (re.compile(r"：\s*[）)]"), "）"),
    (re.compile(r"\|\s*\|"), "| - |"),
    (re.compile(r"^\s*[-|]\s*$"), ""),
]


def public_files():
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", BRANCH], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [f for f in r.stdout.splitlines() if f.strip()]


def main():
    apply = "--apply" in sys.argv
    files = public_files()
    if not files:
        print("  找不到 %s 分支的文件清单" % BRANCH)
        return 1

    exact_hits = 0
    print("[1] 精确修正")
    for f, old, new in EXACT:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            print("    [跳过] %s" % f)
            continue
        s = open(p, encoding="utf-8", errors="replace").read()
        if old not in s:
            print("    [未命中] %s" % f)
            continue
        exact_hits += 1
        print("    修正 %s" % f)
        if apply:
            open(p, "w", encoding="utf-8", newline="").write(s.replace(old, new))

    print("[2] 剥路径引用 + 清残渣")
    nf = nl = 0
    for f in files:
        if os.path.splitext(f)[1].lower() not in (
                ".md", ".txt", ".v", ".py", ".ps1", ".cst", ".sdc", ".qss"):
            continue
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        out, n = [], 0
        for ln in src.split("\n"):
            work = ln
            for pat in DROP:
                work = pat.sub("", work)
            if work != ln:
                for pat, rep in TIDY:
                    work = pat.sub(rep, work)
                n += 1
            out.append(work)
        if n:
            nf += 1
            nl += n
            if apply:
                open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("    精确修正 %d 处；剥引用 %d 行 / %d 个文件" % (exact_hits, nl, nf))
    if not apply:
        print("    （预演，未写文件；加 --apply 执行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
