# -*- coding: utf-8 -*-
"""
neutralize_docs.py —— Markdown 文档措辞整理（只改表述，不改事实）

目标：让文档读起来像项目自己的技术记录，而不是协作代理的工作日志。

保护（绝不破坏结构）：
  · ``` 围栏代码块 —— 整块跳过
  · 行内 `code` 片段与 `[文本](路径)` 链接 —— 先挖出占位，替换完再放回
  · 表格竖线与列表符号 —— 只改单元格内的文字

处理内容：
  1. 符号：✓ ✗ ★ ☆ ⚠ ▮ ✅ ❌ 等（删除；表格单元格若因此变空则填 "-"）
  2. 协作术语：任务板 / 挂账 / 销账 / 工单 / 交接 / 审计 / 认领 / 双代理 / 代理 /
     代理与工具名 ZCode / DeepSeek / GLM / 第 N 轮
  3. 固定第一人称短语：我原来 / 我这边 / 我们 / 我得 / 我按 / 我这次
  4. 清理残留：空括号、（本次）这类替换残渣、行尾空格

用法：
  python tools/scripts/neutralize_docs.py --dry    [--files ...]
  python tools/scripts/neutralize_docs.py --apply  [--files ...]
"""
import argparse
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_FILES = [
    "docs/01-竞赛情报/00-竞赛选题总览-2026.md",
    "docs/02-技术方案/17-混响Freeverb-lite设计与验收判据.md",
    "docs/02-技术方案/18-交互层决策清单.md",
    "docs/02-技术方案/19-UART协议v1.0草案.md",
    "docs/02-技术方案/20-pad扫描规格书.md",
    "docs/02-技术方案/21-验收判据清单.md",
    "docs/02-技术方案/19-UART协议v1.0草案.md",
    "sim_build/show/README_音频说明.md",
    "tools/host/README.md",
    "src/rtl/README.md",
]

TERMS = [
    (re.compile(r"第\s*\d+\s*[轮次]"), ""),
    (re.compile(r"双代理任务板|任务板"), "任务清单"),
    (re.compile(r"未验证与挂账清单|挂账清单"), "待办清单"),
    (re.compile(r"挂账"), "待办"),
    (re.compile(r"销账"), "关闭"),
    (re.compile(r"工单"), "任务"),
    (re.compile(r"交接简报|交接文件|交接-"), "移交说明"),
    (re.compile(r"交接"), "移交"),
    (re.compile(r"审计发现|审计第|审计"), "复核"),
    (re.compile(r"认领"), "登记"),
    # 协作方与工具名：直接删掉署名，不要替换成称谓
    # （换成"评审 起草"读起来不通，删掉后是"起草"，自然得多）
    (re.compile(r"ZCode"), ""),
    (re.compile(r"DeepSeek"), ""),
    (re.compile(r"\bGLM\b"), ""),
    (re.compile(r"双代理"), ""),
    (re.compile(r"代理"), ""),
    # 固定第一人称短语（孤立"我/你"不自动改，留人工）
    (re.compile(r"我原来"), "原先"),
    (re.compile(r"我这边"), "本项目"),
    (re.compile(r"我这次"), "本次"),
    (re.compile(r"我按"), "按"),
    (re.compile(r"我得"), "需要"),
    (re.compile(r"我们"), "本项目"),
]

# ★★ 这类**连排星号是评分数据**（如 ★★★★★），必须保留；
#    只有单独一个 ★/☆ 当装饰时才删。上一版把评分整列删成了 "-"，把内容弄丢了。
STAR_RUN = re.compile(r"[★☆]{2,}")
SYMBOLS = re.compile(r"[✓✗★☆⚠▮●○◆✅❌]\ufe0f?[ \t]?")
INLINE = re.compile(r"`[^`]*`")
LINK = re.compile(r"\]\([^)]*\)")
RESIDUE = [
    (re.compile(r"（\s*）|\(\s*\)"), ""),
    (re.compile(r"（本次）"), ""),
    (re.compile(r"([（(])[ \t]+"), r"\1"),          # 删词后括号内的多余空格
    (re.compile(r"[ \t]+([）)])"), r"\1"),
    (re.compile(r"[ \t]{2,}"), " "),
    (re.compile(r"\*\*[ \t]+"), "**"),               # 删词后粗体标记内多余空格
    (re.compile(r"[ \t]+\*\*"), "**"),
    (re.compile(r"[ \t]+$"), ""),
    (re.compile(r"\|\s*\|"), "| - |"),
]


def tidy(text):
    for pat, rep in RESIDUE:
        text = pat.sub(rep, text)
    return text


def process(path, dry, stats):
    src = io.open(path, encoding="utf-8", errors="replace").read()
    lines = src.split("\n")
    out, changed, in_fence = [], 0, False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(ln)
            continue
        if in_fence:
            out.append(ln)
            continue
        orig = ln
        keeper = []

        def stash(mm):
            keeper.append(mm.group(0))
            return "\x01%d\x02" % (len(keeper) - 1)

        work = INLINE.sub(stash, ln)
        work = LINK.sub(stash, work)
        work = STAR_RUN.sub(stash, work)          # 先保住评分用的连排星号
        for pat, rep in TERMS:
            work = pat.sub(rep, work)
        work = SYMBOLS.sub("", work)
        work = tidy(work)
        work = re.sub(r"\x01(\d+)\x02", lambda mm: keeper[int(mm.group(1))], work)
        if work != orig:
            changed += 1
            if dry and changed <= 4:
                print("     %s" % os.path.relpath(path, ROOT))
                print("       - %s" % orig.strip()[:118])
                print("       + %s" % work.strip()[:118])
        out.append(work)
    if changed and not dry:
        io.open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    if changed:
        stats.append((changed, path))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--files", nargs="*", default=None)
    a = ap.parse_args()
    if not (a.dry or a.apply):
        print(__doc__)
        return 0

    files = a.files or DEFAULT_FILES
    stats = []
    print("[整理%s]" % (" 预演" if a.dry else " 应用"))
    for f in files:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            print("     [跳过，不存在] %s" % f)
            continue
        process(p, a.dry, stats)
    stats.sort(reverse=True)
    print("-" * 78)
    print(" 共改写 %d 行，涉及 %d 个文件" % (sum(s for s, _ in stats), len(stats)))
    for n, p in stats:
        print("   %5d 行  %s" % (n, os.path.relpath(p, ROOT)))
    if a.dry:
        print(" （预演，未写文件；确认后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
