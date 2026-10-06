#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leakcheck_test.py —— 公开版导出「泄漏判据」的自检（阶段 4）

【为什么要有这一条】
  make_public.py 的职责是生成**只含作品本体**的公开快照，而它原来在提交前
  只会**打印**三项痕迹计数，泄漏了也照常 commit 并返回 0 ——
  而"退出码 0"正是上游判断"这一步成功"的依据 ⇒ 泄漏会被**静默放过**。
  本次审计还发现排除依赖两个偶然条件：
    ① `git rm -r --cached .` 顺手把 make_public.py 自己清出索引；
    ② `tools/scripts/_*.py` 只写在 public 分支的 .gitignore 里，主线没有，
       那 28 个未跟踪排查脚本"只是因为还没被 add 才没进"。
  ⇒ 已给 make_public.py 加上 `find_leaks()` 硬判据：**提交前核对，泄漏即中止（退出码 1）**。

【本自检要防的是"判据本身失效"】
  一个永远返回空列表的 find_leaks() 会让导出流程**永远绿灯**，
  比没有判据更危险。所以这里**必须包含应当被抓到的输入** ——
  若检测器坏了，这些用例会红，本自检随之变红。

用法：python tools/scripts/leakcheck_test.py [--simdir DIR]
退出码：0 = 检测器行为正确；1 = 检测器失效
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_make_public():
    path = os.path.join(ROOT, "tools", "scripts", "make_public.py")
    spec = importlib.util.spec_from_file_location("make_public", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    #   --simdir 是门禁 judge_script 的统一传参，本判据不需要，但必须接受
    mp = load_make_public()

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

    print("=" * 70)
    if fails == 0:
        print("RESULT leakcheck=PASS（A %d 例 + B %d 例 + C 1 例）"
              % (len(clean_cases), len(leak_cases)))
        return 0
    print("RESULT leakcheck=FAIL fails=%d" % fails)
    return 1


if __name__ == "__main__":
    sys.exit(main())
