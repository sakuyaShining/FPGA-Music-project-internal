#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leakcheck_test.py —— 公开版「泄漏判据」的自检（阶段 4）

【本判据守的是**产物**，所以它必须留在工作树里】
  阶段 4 把"整理工具链"（make_public / scan_traces / neutralize_* …）搬到了
  同级的 `../fpga-export-tooling/`。但"不许出现什么"是**产品侧知识**，
  于是它单独成文件 `public_spec.py` 留在本仓，本判据直接 import 它。
  （原来本文件用 importlib 加载 `tools/scripts/make_public.py` ——
    搬走之后那条路径就不存在，门禁会红。这正是"搬动前必须先理依赖"的原因。）

【本自检要防的是"判据本身失效"】
  一个永远返回空列表的 find_leaks() 会让导出流程**永远绿灯**，
  比没有判据更危险。所以这里**必须包含应当被抓到的输入** ——
  若检测器坏了，这些用例会红，本自检随之变红。

用法：python tools/scripts/leakcheck_test.py [--simdir DIR]
退出码：0 = 检测器行为正确；1 = 检测器失效
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_spec():
    """加载留在工作树里的权威规格 public_spec.py"""
    path = os.path.join(ROOT, "tools", "scripts", "public_spec.py")
    spec = importlib.util.spec_from_file_location("public_spec", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    #   --simdir 是门禁 judge_script 的统一传参，本判据不需要，但必须接受
    mp = load_spec()

    #   ---- 应当【干净】的输入（作品本体）----
    clean_cases = [
        (["src/rtl/tdm_top.v"], "作品 RTL"),
        (["docs/02-技术方案/34-当前版本规格-基线v1.md"], "作品文档"),
        (["tools/scripts/regress_all.py"], "门禁脚本（属于工程产出）"),
        (["src/sim/tb_evmerge.v"], "测试台"),
        (["src/gowin/tdm_synth/tdm_synth.gprj"], "综合工程"),
    ]
    #   ---- 应当【被抓到】的输入（内部材料 / 整理工具本身）----
    leak_cases = [
        (["tools/scripts/make_public.py"], "整理工具本身"),
        (["tools/scripts/scan_traces.py"], "痕迹扫描工具"),
        (["tools/scripts/neutralize_docs.py"], "注释/文档中和工具"),
        (["tools/scripts/_diag_pitch.py"], "一次性排查脚本（_ 前缀）"),
        (["tools/scripts/flash_sram.cmd"], "临时烧写脚本"),
        (["refs/素材库/x.md"], "交接/任务板材料"),
        (["PROJECT_MEMORY.md"], "跨会话记忆"),
        (["tools/pylib/foo.py"], "随仓库带进的第三方库"),
        (["src/rtl/archive/old.v"], "早期死代码"),
        (["src/rtl/bringup_top.v"], "与乐器无关的 bringup 演示"),
        (["src/gowin/bringup_9k/x.gprj"], "9K bringup 工程"),
        (["src/rtl/i2c_master.v"], "未启用的 I2C 主控"),
        (["docs/01-竞赛情报/x.md"], "准备阶段资料"),
    ]

    fails = 0
    print("=" * 70)
    print(" 公开版导出泄漏判据 自检")
    print("=" * 70)

    print(" A 干净输入必须判为无泄漏（%d 例）" % len(clean_cases))
    for files, why in clean_cases:
        got = mp.find_leaks(files)
        if got:
            print("  FAIL  %-28s %s -> 误报 %s" % (why, files, got))
            fails += 1
        else:
            print("  PASS  %-28s %s" % (why, files[0]))

    print(" B 泄漏输入必须被抓到（%d 例）—— 这一组是防'检测器失效'的关键" % len(leak_cases))
    for files, why in leak_cases:
        got = mp.find_leaks(files)
        if not got:
            print("  FAIL  %-28s %s -> **漏检**（检测器失效）" % (why, files))
            fails += 1
        else:
            print("  PASS  %-28s %s" % (why, files[0]))

    #   C 混合输入：既要抓到泄漏项，也不能把干净项算成泄漏
    print(" C 混合输入：只报泄漏项，不牵连干净项")
    mixed = ["src/rtl/tdm_top.v", "tools/scripts/make_public.py",
             "docs/02-技术方案/34-当前版本规格-基线v1.md",
             "tools/scripts/_probe_qt.py"]
    got = sorted(mp.find_leaks(mixed))
    exp = sorted(["tools/scripts/make_public.py", "tools/scripts/_probe_qt.py"])
    if got == exp:
        print("  PASS  混合输入 -> %s" % got)
    else:
        print("  FAIL  混合输入 期望 %s 实测 %s" % (exp, got))
        fails += 1

    #   D 三份清单必须同步（本轮新增，防"改一处漏两处"）
    #
    #   make_public.py 把"内部材料"这份知识写成了**三个投影**：
    #       EXCLUDE        要 git rm --cached 的路径
    #       IGNORE_BLOCK   追加进公开版 .gitignore 的规则
    #       LEAK_PATTERNS  提交前 find_leaks() 用来中止的判据
    #   ⇒ 将来新增一条排除项时，只改其中一两处是很容易发生的，
    #     而**只改 EXCLUDE/IGNORE 而不改 LEAK_PATTERNS** 会让新项*不被判据拦住*
    #     ——"排除规则"与"泄漏判据"脱节，正是最该防的那种漏洞。
    #   所以这里断言：**另外两份清单的每一条，都必须被 LEAK_PATTERNS 覆盖**。
    print(" D 三份清单同步：EXCLUDE / IGNORE_BLOCK 的每一条都必须被 LEAK_PATTERNS 覆盖")

    def representative(rule):
        """为一条 ignore/排除规则构造一个真实的、应当被判为泄漏的路径

        ★ 注意 EXCLUDE 里的**目录**是**不带尾斜杠**的（`notes`、`tools/pylib`），
          而 IGNORE_BLOCK / LEAK_PATTERNS 用的是 `notes/` 这种带斜杠形式。
          第一版直接把 `notes` 当代表路径，匹配 `^notes/` 自然失败 ⇒
          报了 5 条"未覆盖"，其实全是**本测试的规范不一致**，不是真缺口。
          （这已是本会话第三次"自己的检查器有 bug" —— 与前两次同类：
            必须先把检查器本身验一遍，再相信它给出的缺口。）
        """
        r = rule.strip().rstrip("/")
        #   在磁盘上确实是目录的 ⇒ 按目录语义构造路径
        if os.path.isdir(os.path.join(ROOT, r)):
            return r + "/example-file.md"
        if "*" in r:
            return r.replace("*", "diag_pitch")
        return r

    import re as _re
    leak_re = [_re.compile(p) for p in mp.LEAK_PATTERNS]

    def is_covered(path):
        return any(rx.search(path) for rx in leak_re)

    d_bad = []
    for p in mp.EXCLUDE:
        if not is_covered(representative(p)):
            d_bad.append(("EXCLUDE", p))
    for ln in mp.IGNORE_BLOCK.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if not is_covered(representative(ln)):
            d_bad.append(("IGNORE_BLOCK", ln))

    if d_bad:
        print("  FAIL  %d 条排除规则未被 LEAK_PATTERNS 覆盖（新项不会被判据拦住）：" % len(d_bad))
        for where, p in d_bad[:15]:
            print("        [%s] %s" % (where, p))
        fails += 1
    else:
        n_ex = len(mp.EXCLUDE)
        n_ig = len([l for l in mp.IGNORE_BLOCK.splitlines()
                    if l.strip() and not l.strip().startswith("#")])
        print("  PASS  EXCLUDE %d 条 + IGNORE_BLOCK %d 条，全部被 LEAK_PATTERNS(%d 条) 覆盖"
              % (n_ex, n_ig, len(mp.LEAK_PATTERNS)))

    print("=" * 70)
    if fails == 0:
        print("RESULT leakcheck=PASS（A %d 例 + B %d 例 + C 1 例 + D 同步）"
              % (len(clean_cases), len(leak_cases)))
        return 0
    print("RESULT leakcheck=FAIL fails=%d" % fails)
    return 1


if __name__ == "__main__":
    sys.exit(main())
