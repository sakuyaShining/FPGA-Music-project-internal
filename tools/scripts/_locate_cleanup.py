# -*- coding: utf-8 -*-
"""定位待清理的字符串与文件名引用（一次性排查脚本）。

只报告，不改动。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP_DIRS = {".git", "impl", "build", "dist", "__pycache__", "backups", "node_modules"}

# 1) 代码里的四处字符串残留
CODE_TARGETS = ["zcode", "ZCode", "双代理", "交接"]
CODE_FILES = ["src/sim/tb_tdm_top.v", "tools/scripts/regmap_dump.py",
              "tools/scripts/regress_all.py", "tools/scripts/t60_check.py"]

print("=" * 78)
print(" 一、代码里字符串形式的残留")
print("=" * 78)
for f in CODE_FILES:
    p = os.path.join(ROOT, f)
    if not os.path.isfile(p):
        print("  [缺失] %s" % f)
        continue
    for i, ln in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
        if any(t in ln for t in CODE_TARGETS):
            print("  %s:%d" % (f, i))
            print("      %s" % ln.rstrip()[:150])

# 2) 旧文件名的全部引用
OLD = "21-验收判据交接清单"
print()
print("=" * 78)
print(" 二、引用旧文件名 %s.md 的地方" % OLD)
print("=" * 78)
hits = 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fn in files:
        if os.path.splitext(fn)[1].lower() not in (
                ".md", ".py", ".ps1", ".v", ".txt", ".cst", ".json"):
            continue
        p = os.path.join(base, fn)
        try:
            s = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, ln in enumerate(s.split("\n"), 1):
            if OLD in ln:
                hits += 1
                rel = os.path.relpath(p, ROOT)
                print("  %s:%d  %s" % (rel, i, ln.strip()[:110]))
print("  合计 %d 处" % hits)

# 3) 七份待整理文档的"痕迹密度"（估算工作量）
print()
print("=" * 78)
print(" 三、待整理文档的符号与痕迹密度")
print("=" * 78)
DOCS = ["docs/01-竞赛情报/00-竞赛选题总览-2026.md",
        "docs/02-技术方案/17-混响Freeverb-lite设计与验收判据.md",
        "docs/02-技术方案/18-交互层决策清单.md",
        "docs/02-技术方案/19-UART协议v1.0草案.md",
        "docs/02-技术方案/20-pad扫描规格书.md",
        "docs/02-技术方案/21-验收判据交接清单.md",
        "sim_build/show/README_音频说明.md"]
SYM = re.compile(r"[✓✗★☆⚠▮]")
FP = re.compile(r"(?<![A-Za-z])[我你](?![A-Za-z])")
AG = re.compile(r"ZCode|DeepSeek|双代理|交接|挂账|任务板|第\s*\d+\s*[轮次]")
print("  %-52s %6s %5s %5s %6s" % ("文件", "行数", "符号", "人称", "术语"))
for f in DOCS:
    p = os.path.join(ROOT, f)
    if not os.path.isfile(p):
        print("  [缺失] %s" % f)
        continue
    s = io.open(p, encoding="utf-8", errors="replace").read()
    print("  %-52s %6d %5d %5d %6d"
          % (f.split("/")[-1], s.count("\n"), len(SYM.findall(s)),
             len(FP.findall(s)), len(AG.findall(s))))
