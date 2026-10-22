# -*- coding: utf-8 -*-
"""
neutralize_comments.py —— 把**注释**里的代理协作痕迹改成中性工程语言（保守版）

只动注释，不动任何代码：
  · 纯注释行 / 行尾注释 → 只改写注释文字，代码段一字不动
  · **保留注释原有的缩进与排版**（上一版的坑：合并空格把 `//   x` 变成 `// x`，
    产生几百行无意义 diff —— 已修掉）

只自动处理【安全类别】：
  1. 装饰符号 ★☆⚠✓✗▮ 等（删符号、留文字）
  2. 协作术语：任务板/挂账/销账/工单/交接/审计/双代理/代理/认领
  3. 代理与工具名：ZCode / DeepSeek / GLM
  4. 轮次标记：第 N 轮
  5. **固定**第一人称短语：我原来 / 我这边 / 我们 / 我得
     —— 孤立的"我/你"**不自动改**（会改出病句），脚本会**统计剩余量**留给人工 ✓

用法：
  python tools/scripts/neutralize_comments.py --dry     [--paths ...]
  python tools/scripts/neutralize_comments.py --apply   [--paths ...]
安全网：改动前已提交（20cf115）⇒ 出错可 `git checkout -- <路径>` 回滚 ✓
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMMENT_OF = {".v": "//", ".sv": "//", ".vh": "//", ".cst": "//",
              ".py": "#", ".ps1": "#", ".tcl": "#", ".sdc": "#", ".qss": "/*"}

DEFAULT_PATHS = ["src/rtl", "src/sim", "tools"]

SUBS = [
    (re.compile(r"第\s*\d+\s*[轮次]"), "(本次)"),
    (re.compile(r"双代理任务板|任务板"), "任务清单"),
    (re.compile(r"未验证与挂账清单|挂账清单"), "待办清单"),
    (re.compile(r"挂账"), "待办"),
    (re.compile(r"销账"), "关闭"),
    (re.compile(r"工单"), "任务"),
    (re.compile(r"交接简报|交接文件|交接-"), "移交说明"),
    (re.compile(r"交接"), "移交"),
    (re.compile(r"审计发现|审计第|审计"), "复核"),
    (re.compile(r"认领"), "登记"),
    (re.compile(r"ZCode"), "复核"),
    (re.compile(r"DeepSeek"), "本项目"),
    (re.compile(r"\bGLM\b"), "评审"),
    (re.compile(r"双代理|代理"), "协作"),
    (re.compile(r"[★☆⚠✓✗▮●○◆]\ufe0f?[ \t]?"), ""),
    (re.compile(r"我原来"), "原先"),
    (re.compile(r"我这边"), "本项目"),
    (re.compile(r"我得"), "需要"),
    (re.compile(r"我们"), "本项目"),
]

# 不在自动范围内、但要**统计**的残留（留给人工判断）
RESIDUAL = re.compile(r"(?<![A-Za-z])[我你](?![A-Za-z])|代理|审计|任务板|挂账|销账|工单|轮")

# 路径/文件名保护 ：上一版把注释里引用的
#   `docs/02-技术方案/11-综合结果与课题覆盖审计.md` 改成了 `…复核.md` —— 把引用改坏了
#   做法：先把路径整体"挖掉"存起来，替换完再放回
PATH_RE = re.compile(
    r"[\w\u4e00-\u9fff][\w\u4e00-\u9fff/\\.\-]*"
    r"\.(?:md|markdown|v|sv|vh|py|ps1|ps|tcl|cst|sdc|hex|csv|txt|json|qss|gprj|ipc|do|cfg|log|wav|png|jpg|html|docx|xlsx|fs|bin)",
    re.I)


def split_comment(line, marker):
    """返回 (代码段, 注释段 or None)。字符串里的注释符不算 ✓"""
    in_s = in_d = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == '"' and not in_s:
            in_s = True
        elif c == '"' and in_s:
            in_s = False
        elif c == "'" and not in_d:
            in_d = True
        elif c == "'" and in_d:
            in_d = False
        elif not in_s and not in_d and line.startswith(marker, i):
            return line[:i], line[i:]
        i += 1
    return line, None


def neutralize(cmt, marker):
    """只改注释文字，**保留 marker 后面原有的空白** ✓"""
    body = cmt[len(marker):]
    m = re.match(r"^([ \t]*)", body)
    pad, text = m.group(1), body[m.end():]

    # ① 挖出路径（占位符用不可能出现的字符组合）
    keeper = []

    def stash(mm):
        keeper.append(mm.group(0))
        return "\x01%d\x02" % (len(keeper) - 1)

    text = PATH_RE.sub(stash, text)

    # ② 文本替换
    for pat, rep in SUBS:
        text = pat.sub(rep, text)

    # ③ 安全清理：括号内多余空格 + 变体选择符（的）
    text = text.replace("\ufe0f", "")
    text = re.sub(r"([（(【\[])[ \t]+", r"\1", text)
    text = re.sub(r"[ \t]+([）)】\]])", r"\1", text)
    text = re.sub(r"[ \t]{2,}(?=[，。、；：])", "", text)

    # ④ 放回路径
    text = re.sub(r"\x01(\d+)\x02", lambda mm: keeper[int(mm.group(1))], text)
    return marker + pad + text.rstrip()          # 只去注释尾部空白，不碰内部对齐


def process(path, dry, stats, resid):
    ext = os.path.splitext(path)[1].lower()
    marker = COMMENT_OF.get(ext)
    if not marker:
        return 0
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return 0
    out, changed, r = [], 0, 0
    for ln in src.split("\n"):
        code, cmt = split_comment(ln, marker)
        if cmt is None:
            out.append(ln)
            continue
        new = neutralize(cmt, marker)
        if new != cmt:
            changed += 1
            if dry and changed <= 3:
                print("    %s" % os.path.relpath(path, ROOT))
                print("      - %s" % cmt.strip()[:120])
                print("      + %s" % new.strip()[:120])
        out.append(code + new)
        r += len(RESIDUAL.findall(cmt))
    if changed and not dry:
        open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    if changed:
        stats.append((changed, path))
    if r:
        resid.append((r, path, changed))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    a = ap.parse_args()
    if not (a.dry or a.apply):
        print(__doc__)
        return 0

    files = []
    for base in a.paths:
        p = os.path.join(ROOT, base)
        if os.path.isfile(p):
            files.append(p)
            continue
        for root, _d, fns in os.walk(p):
            if "__pycache__" in root or os.sep + "build" in root or os.sep + "dist" in root:
                continue
            for fn in fns:
                files.append(os.path.join(root, fn))

    stats, resid = [], []
    for f in sorted(files):
        process(f, a.dry, stats, resid)
    stats.sort(reverse=True)
    resid.sort(reverse=True)
    total = sum(s for s, _ in stats)
    print("-" * 80)
    print(" %s：改写 %d 行注释，涉及 %d 个文件"
          % ("[预演]" if a.dry else "[已应用]", total, len(stats)))
    for n, f in stats[:15]:
        print("   %5d 行  %s" % (n, os.path.relpath(f, ROOT)))
    print("\n 剩余需人工判断的痕迹（孤立第一人称/术语残留）：")
    for n, f, ch in resid[:15]:
        print("   %5d 处  %s" % (n, os.path.relpath(f, ROOT)))
    print(" 合计剩余 %d 处" % sum(n for n, _f, _c in resid))
    if a.dry:
        print(" （预演，未写文件 ✓ 确认后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
