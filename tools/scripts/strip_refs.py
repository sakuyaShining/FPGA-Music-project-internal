# -*- coding: utf-8 -*-
"""
strip_refs.py —— 剥掉指向公开版不存在路径的引用

公开版只保留作品本体：`refs/`、`notes/`、`PROJECT_MEMORY.md`、`tools/pylib/` 等都不在其中，
但代码注释与文档里仍写着这些路径。留着有两个问题：读者点进去找不到东西；这些文件名
（如内部证据文档名）本身也带着开发过程的痕迹。

做法：把路径引用整段去掉，并清理因此产生的悬空标点（"详见 " "（ ）" "，）" 之类）。
只动文字，不碰代码与 Markdown 结构。

用法：
  python tools/scripts/strip_refs.py --dry
  python tools/scripts/strip_refs.py --apply
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 整段删除的引用形式（先长后短）
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

# 删除后要清理的悬空标点与连接词
TIDY = [
    (re.compile(r"[，,;；]?\s*详见\s*[）)]"), "）"),
    (re.compile(r"[，,;；]?\s*见\s*[）)]"), "）"),
    (re.compile(r"详见\s*$"), ""),
    (re.compile(r"[（(]\s*[，,;；]?\s*[）)]"), ""),
    (re.compile(r"[（(]\s*[，,;；]"), "（"),
    (re.compile(r"[（(]\s+"), "（"),
    (re.compile(r"\s+[）)]"), "）"),
    (re.compile(r"[ \t]{2,}"), " "),
    (re.compile(r"[ \t]+$"), ""),
    (re.compile(r"（\s*）"), ""),
    (re.compile(r"[，,]\s*[，,]"), "，"),
    (re.compile(r"：\s*[）)]"), "）"),
    (re.compile(r"^\s*[-|]\s*$"), ""),
    (re.compile(r"\|\s*\|"), "| - |"),
]


def tracked_files(branch):
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [f for f in r.stdout.splitlines() if f.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--branch", default="public")
    a = ap.parse_args()
    if not (a.dry or a.apply):
        print(__doc__)
        return 0

    # 在公开版的文件集合上作业（避免改到不该进公开版的材料）
    files = tracked_files(a.branch) or []
    changed_files = 0
    changed_lines = 0
    samples = 0
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
                if a.dry and samples < 10:
                    samples += 1
                    print("     %s" % f)
                    print("       - %s" % ln.strip()[:116])
                    print("       + %s" % work.strip()[:116])
            out.append(work)
        if n:
            changed_files += 1
            changed_lines += n
            if a.apply:
                open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("-" * 78)
    print(" %s：%d 行 / %d 个文件" % ("预演" if a.dry else "已应用",
                                   changed_lines, changed_files))
    if a.dry:
        print(" （预演，未写文件；确认后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
