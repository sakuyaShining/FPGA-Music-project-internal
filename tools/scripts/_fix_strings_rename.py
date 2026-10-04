# -*- coding: utf-8 -*-
"""清理第 1、2 项：
   1) 代码注释/文档字符串里残留的四处措辞（zcode / ZCode / 双代理 / 交接）
   2) 重命名 docs/02-技术方案/21-验收判据交接清单.md -> 21-验收判据清单.md，并更新全部引用

只用**子串替换**（不依赖整行匹配，避免空白差异导致漏替）。
改完做一次自检：代码文件里不该再有这些词，全仓库不该再有旧文件名。
"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OLD_DOC = "21-验收判据交接清单"
NEW_DOC = "21-验收判据清单"

# (旧子串, 新子串) —— 逐条对应上面定位到的行
REPL = [
    # src/sim/tb_tdm_top.v:11
    ("zcode 把门初值改成 0、要求", "早期版本把门初值改成 0，要求"),
    # tools/scripts/regmap_dump.py:7,8
    ("（ZCode 的 UART 协议规格）", "（UART 协议规格）"),
    ("和协议文档（ZCode 的 UART 协议规格）", "和协议文档（UART 协议规格）"),
    ("⚠️ 本项目已经出过一次：ZCode 的 17 号文档写", "本项目已经出过一次：17 号文档曾写"),
    ("本项目已经出过一次：ZCode 的 17 号文档写", "本项目已经出过一次：17 号文档曾写"),
    # tools/scripts/regress_all.py:4,11
    ("全项目一键回归门（双代理共同验收闸口）", "全项目一键回归门"),
    ("这是《双代理任务板》的销账依据（R0 生命线）", "这是回归基线（R0 生命线）"),
    # 文件名引用
    (OLD_DOC, NEW_DOC),
]

CODE_FILES = [
    "src/sim/tb_tdm_top.v",
    "tools/scripts/regmap_dump.py",
    "tools/scripts/regress_all.py",
    "tools/scripts/t60_check.py",
]
# 私有过程材料里也引用了旧文件名，一并更新，避免留下失效路径
REF_FILES = [
    "refs/素材库/交接-DeepSeek会话恢复.md",
    "refs/素材库/双代理任务板.md",
    "refs/素材库/未验证与挂账清单.md",
]


def patch(path, counter):
    if not os.path.isfile(path):
        print("  [跳过，不存在] %s" % path)
        return
    s = io.open(path, encoding="utf-8", errors="replace").read()
    orig = s
    for old, new in REPL:
        n = s.count(old)
        if n:
            s = s.replace(old, new)
            counter[0] += n
            counter[1].append((os.path.relpath(path, ROOT), old, n))
    if s != orig:
        io.open(path, "w", encoding="utf-8", newline="").write(s)


def main():
    counter = [0, []]
    print("[1] 子串替换")
    for f in CODE_FILES + REF_FILES:
        patch(os.path.join(ROOT, f), counter)
    for rel, old, n in counter[1]:
        print("   %-40s x%d  «%s»" % (rel, n, old[:38]))
    print("   合计替换 %d 处" % counter[0])

    print("[2] 重命名文件")
    src = os.path.join(ROOT, "docs", "02-技术方案", OLD_DOC + ".md")
    dst = os.path.join(ROOT, "docs", "02-技术方案", NEW_DOC + ".md")
    if os.path.isfile(src):
        r = subprocess.run(["git", "mv", src, dst], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        print("   git mv %s -> %s : %s" % (OLD_DOC, NEW_DOC,
              "成功" if r.returncode == 0 else "失败 " + r.stderr.strip()[:120]))
    else:
        print("   源文件不存在（可能已改过）")

    print("[3] 自检")
    bad = 0
    for f in CODE_FILES:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        for t in ("zcode", "ZCode", "DeepSeek", "双代理"):
            if t in s:
                print("   仍残留 %-10s 于 %s" % (t, f))
                bad += 1
    if bad == 0:
        print("   代码文件里已无 zcode/ZCode/DeepSeek/双代理")

    # 全仓库再也找不到旧文件名（跳过 .git 与产物目录）
    skip = {".git", "impl", "build", "dist", "__pycache__", "backups"}
    left = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in (".md", ".py", ".ps1", ".v", ".txt"):
                continue
            p = os.path.join(base, fn)
            try:
                s = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if OLD_DOC in s:
                print("   仍残留旧文件名于 %s" % os.path.relpath(p, ROOT))
                left += 1
    if left == 0:
        print("   全仓库已无旧文件名引用")
    return 0 if (bad == 0 and left == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
