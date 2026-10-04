# -*- coding: utf-8 -*-
"""
scan_traces.py —— 公开前的"痕迹扫描"（只报事实，不替你决定 ✓）

目的：仓库最终要公开，需要先看清**哪些文件/哪些措辞会一眼暴露"这是 AI/代理做的"**。
本脚本只做一件事：**统计**，把结果按"密度"排序，供人工判断 ✓。

统计口径（分三类）：
  A. 【过程身份】直接提到代理/工具的名字或角色：ZCode / DeepSeek / GLM / 代理 / 双代理 / 交接
  B. 【工作流黑话】本项目的代理协作术语：任务板 / 挂账 / 审计 / 轮次 / 第 N 轮 / 判据清单……
  C. 【行文风格】符号密度与第一人称：✓ ✗ ★ 我 你（技术文档里正常，代理文里"超标"）

输出：每个文件的 A/B/C 命中数 + 综合密度 + 排序列出；末尾按目录汇总。

用法：python tools/scripts/scan_traces.py [--top 30] [--all]
"""
import argparse
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PAT_A = re.compile(r"ZCode|DeepSeek|GLM|双代理|代理|交接|会话恢复|prompt|提示词", re.I)
PAT_B = re.compile(r"任务板|挂账|审计|认领|销账|工单|第\s*\d+\s*轮|轮次|判据清单|闸口|交接简报")
PAT_C = re.compile(r"[✓✗★☆⚠]|(?<![A-Za-z])我(?![A-Za-z])|(?<![A-Za-z])你(?![A-Za-z])")

TEXT_EXT = (".md", ".txt", ".v", ".sv", ".py", ".ps1", ".cst", ".sdc", ".qss",
            ".csv", ".gprj", ".json", ".hex", ".js", ".html", ".bat")


def tracked():
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return [f for f in r.stdout.splitlines() if f.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    rows = []
    for f in tracked():
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p) or not f.lower().endswith(TEXT_EXT):
            continue
        try:
            s = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        na, nb, nc = len(PAT_A.findall(s)), len(PAT_B.findall(s)), len(PAT_C.findall(s))
        if na or nb or nc:
            rows.append((na * 3 + nb * 2 + nc, na, nb, nc, len(s), f))

    rows.sort(reverse=True)
    print("=" * 100)
    print(" 公开前痕迹扫描（分数 = 3*A + 2*B + C；A=过程身份 B=工作流黑话 C=行文风格）")
    print("=" * 100)
    print(" %6s %5s %5s %5s %8s  %s" % ("分数", "A", "B", "C", "字节", "文件"))
    show = rows if a.all else rows[:a.top]
    for sc, na, nb, nc, n, f in show:
        flag = "★高危" if na else ("△中" if nb > 3 else "  ")
        print(" %6d %5d %5d %5d %8d  %s %s" % (sc, na, nb, nc, n, flag, f))
    print("-" * 100)
    print(" 共 %d 个文本文件有命中（全部 tracked 文件 %d 个）" % (len(rows), len(tracked())))

    # 目录汇总
    agg = {}
    for sc, na, nb, nc, n, f in rows:
        d = os.path.dirname(f) or "."
        top = "/".join(d.split("/")[:2])
        x = agg.setdefault(top, [0, 0, 0, 0])
        x[0] += sc; x[1] += na; x[2] += nb; x[3] += nc
    print("\n 按目录汇总（分数 / A / B / C）：")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        print("   %-34s %6d  A=%-4d B=%-4d C=%-5d" % (k, v[0], v[1], v[2], v[3]))

    print("\n 提示：A 列（过程身份）非 0 的文件 = 一眼能看出代理参与 ✗，"
          "建议移出公开仓库或改写 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
