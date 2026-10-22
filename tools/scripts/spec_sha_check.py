#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_sha_check.py —— 校验规格文档里的「源码 blob 表」是否与工作树一致

【为什么要有这一条】
  项目纪律要求"每项结果绑定源码 SHA"。`34-当前版本规格-基线v1.md` 的做法是
  在文档里列出**每个 RTL 模块的 blob 短哈希**（还有 6 张数据表）。
  但**没有任何东西保证它们会被更新** —— 改了 RTL 却忘了改表，
  文档就会指向旧代码，而读者无从察觉（这比"没有绑定"更危险：它看起来是绑定的）。

  本判据把"绑定是否真的有效"变成一条**可复跑的机械检查**：
  逐行取出文档里的 `路径 → 哈希`，用 `git hash-object` 重算工作树里的实际哈希，
  不一致即报错并列出差异。

【判据】
  S1 能从文档里抽到 blob 行（**抽不到 = 提取器失效，必须报错**，
     否则会像"零行 ⇒ 零不一致 ⇒ PASS"那样**空集假通过**）
  S2 每一行的哈希都与工作树实际内容一致
  S3 数据表（`src/gowin/tdm_synth/*.hex`）同样校验

【为什么校验"工作树"而不是"HEAD"】
  文档的绑定对象是"这一版源码"。工作树是即将提交的内容；
  若校验 HEAD，未提交的 RTL 改动会被漏掉（那正是最容易出错的时候）。

用法：python tools/scripts/spec_sha_check.py [--simdir DIR] [--doc PATH]
退出码：0 = 全部一致；1 = 有不一致或提取器失效
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DOC = os.path.join(ROOT, "docs", "02-技术方案", "34-当前版本规格-基线v1.md")


def blob12(path):
    """工作树里该文件的 git blob 短哈希（前 12 位）。

    ★ 不要用 `git hash-object --short=12`：某些 git 版本不支持该组合，
      会**静默返回空串**（第一版就这样：17 行全部"实际="为空 ⇒ 全报不一致，
      看起来像文档全错，其实是取哈希的方式不对）。故取完整哈希再截。
    """
    r = subprocess.run(["git", "hash-object", path], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip()[:12]


def main():
    doc = DEFAULT_DOC
    for i, a in enumerate(sys.argv):
        if a == "--doc" and i + 1 < len(sys.argv):
            doc = sys.argv[i + 1]
        #   --simdir 是门禁 judge_script 的统一传参，本判据不需要，但必须接受
    if not os.path.isfile(doc):
        print("找不到规格文档: %s" % doc)
        return 1
    src = open(doc, encoding="utf-8", errors="replace").read()

    print("=" * 70)
    print(" 规格文档源码绑定校验")
    print(" 文档: %s" % os.path.relpath(doc, ROOT))
    print("=" * 70)

    #   RTL 模块表：| `src/rtl/xxx.v` | `hash` |
    rows = re.findall(r"\|\s*`(src/rtl/[\w_]+\.v)`\s*\|\s*`([0-9a-f]{12})`\s*\|", src)
    #   数据表：以 `名字.hex hash` 形式写在正文里
    hits = re.findall(r"`([\w_]+\.hex)\s+([0-9a-f]{12})`", src)

    print(" S1 抽取结果")
    print("    RTL 模块行 = %d" % len(rows))
    print("    数据表行   = %d" % len(hits))
    if not rows:
        print("  FAIL  S1 抽取器没抽到任何 RTL blob 行 ⇒ **判据本身失效**")
        print("        （这正是本判据第一版的问题：零行 ⇒ 零不一致 ⇒ 空集假通过）")
        return 1

    bad = []
    for path, want in rows:
        full = os.path.join(ROOT, path)
        if not os.path.isfile(full):
            bad.append((path, want, "文件不存在"))
            continue
        got = blob12(full)
        if got != want:
            bad.append((path, want, got))

    for nm, want in hits:
        full = os.path.join(ROOT, "src", "gowin", "tdm_synth", nm)
        if not os.path.isfile(full):
            bad.append(("src/gowin/tdm_synth/" + nm, want, "文件不存在"))
            continue
        got = blob12(full)
        if got != want:
            bad.append(("src/gowin/tdm_synth/" + nm, want, got))

    print(" S2/S3 逐行比对（工作树实际内容 vs 文档记载）")
    if bad:
        print("  FAIL  %d 行不一致：" % len(bad))
        for p, w, g in bad:
            print("        %-36s 文档=%s 实际=%s" % (p, w, g))
        print("        处置：重跑门禁确认全绿后，把文档里的哈希更新为实际值。")
        return 1
    print("  PASS  全部 %d 行一致（RTL %d + 数据表 %d）"
          % (len(rows) + len(hits), len(rows), len(hits)))
    print("=" * 70)
    print("RESULT spec_sha=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
