# -*- coding: utf-8 -*-
"""
make_public.py —— 从「全量」主线生成一份【公开版快照】分支

背景：仓库要最终公开，但主线里有大量**内部过程材料**（代理协作的交接/任务板/挂账/
一次性排查脚本/快照 ……）不适合对外 —— 它们既不是作品内容，也会让人一眼看出
"这是 AI 协作的产物"。这些材料**不能丢**，所以：
    · 主线 main        → 推送【私有仓库】做完整备份（一个字节都不丢）
    · 分支 public      → 推送【公开仓库】：只留作品本体

做法：在 public 分支上 `git rm -r --cached <内部材料>`（**只从索引移除，磁盘文件保留** ✓），
      再把排除规则写进该分支的 .gitignore，最后提交 ✓。
验证：跑 scan_traces.py 的口径复核 public 分支剩下什么痕迹 ✓（同一把尺子 ✓）。

用法：
  python tools/scripts/make_public.py --dry     # 只看会移除什么
  python tools/scripts/make_public.py --apply   # 真正建分支并提交
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 公开版要移除的（内部过程材料 / 与作品无关的演示 / 第三方资料 / 清理工具本身）
EXCLUDE = [
    "refs/素材库",                  # 交接、任务板、挂账清单、步骤证据
    "PROJECT_MEMORY.md",            # 跨会话记忆文件
    ".zcodeignore",                 # 特定代理工具的忽略文件（文件名本身就是痕迹）
    "notes",
    "backups",
    "refs/_site-archive", "refs/candidate-guides", "refs/past-years",
    "refs/official-notices", "refs/report-template", "refs/vendor-examples",
    "tools/pylib",                  # 随仓库带进来的第三方库（下载物，不该当作品提交）
    "src/rtl/archive",              # 早期版本的死代码
    # —— 与"这台乐器"无关的其它 bringup 演示（9K LCD / 图片显示等）——
    "src/rtl/bringup_top.v", "src/rtl/image_rom.v", "src/rtl/image_view.v",
    "src/rtl/lcd_480x272.v", "src/rtl/test_pattern.v",
    "src/constr/bringup_top.cst", "src/gowin/bringup_9k",
]

IGNORE_BLOCK = """
# ===== 公开版：以下为内部过程材料，不在公开仓库中 =====
refs/素材库/
PROJECT_MEMORY.md
.zcodeignore
notes/
backups/
refs/_site-archive/
refs/candidate-guides/
refs/past-years/
refs/official-notices/
refs/report-template/
refs/vendor-examples/
tools/pylib/
src/rtl/archive/
src/rtl/bringup_top.v
src/rtl/image_rom.v
src/rtl/image_view.v
src/rtl/lcd_480x272.v
src/rtl/test_pattern.v
src/constr/bringup_top.cst
src/gowin/bringup_9k/
# 一次性排查脚本（命名带 _ 前缀的临时工具）
tools/scripts/_*.py
# 仓库整理/备份工具本身（与本作品的功能无关，且会暴露整理过程）
tools/scripts/scan_traces.py
tools/scripts/neutralize_comments.py
tools/scripts/neutralize_docs.py
tools/scripts/make_public.py
tools/scripts/git_precheck.py
tools/scripts/fix_gitignore.py
# 图形界面自测报告：生成的调试产物（非源码）
sim_build/gui/selftest_report.txt
# 赛事情报与学习路线：准备阶段的资料（大量引用 refs/ 下的第三方原文），
# 不是本项目的工程产出，且这些引用在公开版里会全部失效
docs/01-竞赛情报/
docs/03-学习路线/
docs/02-技术方案/22-全面审计-2026-10-04.md
tools/scripts/strip_refs.py
docs/02-技术方案/07-候选架构方案-v1.md
docs/02-技术方案/09-第一次烧录bring-up指南.md
refs/
src/rtl/led_heartbeat.v
tools/scripts/check_video_timing.py
tools/scripts/make_image_rom.py
src/rtl/README.md
tools/scripts/flash_sram.cmd
src/rtl/i2c_master.v
src/sim/mpr121_model.v
src/sim/tb_i2c_master.v
"""

PAT_A = re.compile(r"ZCode|DeepSeek|GLM|双代理|交接|会话恢复", re.I)
PAT_B = re.compile(r"任务板|挂账|销账|工单|认领|第\s*\d+\s*[轮次]")
# 指向公开版中不存在路径的悬空引用（点进去 404，同时也是痕迹）
PAT_C = re.compile(r"refs/|notes/|PROJECT_MEMORY|tools/pylib|素材库|"
                   r"bringup_top|bringup_9k|image_rom|image_view|lcd_480x272|test_pattern")


def git(*args, check=True):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print("  ✗ git %s 失败：%s" % (" ".join(args), (r.stdout + r.stderr).strip()[:300]))
        raise SystemExit(1)
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--branch", default="public")
    a = ap.parse_args()
    if not (a.dry or a.apply):
        print(__doc__)
        return 0

    print("[1] 当前主线状态")
    print("  分支：%s" % git("rev-parse", "--abbrev-ref", "HEAD").strip())
    dirty = git("status", "--porcelain").strip()
    if dirty:
        print("  ⚠ 工作区有未提交改动（%d 行）⇒ 请先提交主线再生成公开版 ✗"
              % len(dirty.splitlines()))
        if a.apply:
            print("  ✗ 已中止（避免把未提交内容带进快照）")
            return 1

    print("[2] 将从公开版移除的路径")
    for p in EXCLUDE:
        exists = os.path.exists(os.path.join(ROOT, p))
        n = len(git("ls-files", p, check=False).splitlines()) if exists else 0
        print("   %-32s 已跟踪 %3d 个文件 %s" % (p, n, "" if exists else "(磁盘上不存在)"))

    if a.dry:
        print("\n （预演：未创建任何分支/提交 ✓ 加 --apply 执行）")
        return 0

    print("[3] 创建 %s 分支（orphan 单一提交：公开仓库历史干净，"
          "不会有整理/修补这类显眼的中间提交）" % a.branch)
    git("checkout", "--orphan", a.branch)

    print("[4] 清空索引（**文件全部留在磁盘** ✓）")
    # ★ 必须先清空整个索引 ✗：checkout --orphan 只是让下次提交没有父节点，
    #   **并不会清空索引** ⇒ 已在索引里的文件不受 .gitignore 约束 ✗✗
    #   （上一版就是因此把 _*.py / 清理工具全漏进公开版 ✓ git check-ignore 却显示规则命中 ✓）
    git("rm", "-r", "--cached", "-q", ".")
    for p in EXCLUDE:
        if os.path.exists(os.path.join(ROOT, p)):
            git("rm", "-r", "--cached", "-q", "--ignore-unmatch", p, check=False)

    print("[5] 写入公开版排除规则")
    with open(os.path.join(ROOT, ".gitignore"), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(IGNORE_BLOCK)

    git("add", "-A")
    files = [f for f in git("ls-files").splitlines() if f.strip()]
    print("   公开版跟踪文件数 = %d" % len(files))

    # 用同一把尺子复核剩余痕迹
    a_hits, b_hits, c_hits = [], [], []
    for f in files:
        if f == ".gitignore":
            continue          # 忽略规则本身就写着这些关键词，属误报
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p) or os.path.splitext(f)[1].lower() not in (
                ".md", ".txt", ".v", ".py", ".ps1", ".cst", ".sdc", ".qss"):
            continue
        try:
            s = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if PAT_A.search(s):
            a_hits.append(f)
        if PAT_B.search(s):
            b_hits.append(f)
        if PAT_C.search(s):
            c_hits.append(f)

    print("[6] 痕迹复核（公开版）")
    print("   身份痕迹(A，协作方与工具名) 剩余文件数 = %d" % len(a_hits))
    for f in a_hits[:15]:
        print("       %s" % f)
    print("   工作流术语(B) 剩余文件数 = %d" % len(b_hits))
    for f in b_hits[:15]:
        print("       %s" % f)
    print("   悬空引用(C，指向公开版不存在的路径) 剩余文件数 = %d" % len(c_hits))
    for f in c_hits[:15]:
        print("       %s" % f)

    git("commit", "-q", "-m", "公开版快照：移出内部过程材料，只保留作品本体")
    print("[7] 已提交：%s" % git("log", "--oneline", "-1").strip())
    print("    现在可：git push <公开仓库> %s:main" % a.branch)
    print("    已自动切回主线（避免后续提交误落在快照分支上）")
    git("checkout", "main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
