#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
public_spec.py —— 公开版"不许出现什么"的**唯一权威规格**（阶段 4）

【为什么要单独成文件（2026-10-07）】
  这套知识原来是散在 `make_public.py` 里的三个投影：
      EXCLUDE        要 git rm --cached 的路径
      IGNORE_BLOCK   追加进公开版 .gitignore 的规则
      LEAK_PATTERNS  提交前用来**中止**的判据
  三处规模还不一致（20 / 43 / 21）⇒ 新增排除项时只改一两处很容易，
  而**只改前两者、忘了改 LEAK_PATTERNS** 会让新项"不被判据拦住"。

  同时，阶段 4 把"整理工具链"（make_public / scan_traces / neutralize_* …）
  **移出了活动工作树**，放到同级的 `../fpga-export-tooling/`。
  但门禁套件 `24 leakcheck` 必须留在工作树里（它守的是**产物**），
  于是它不能再 import 那个已经搬走的 `make_public.py`。

  ⇒ 结论：**"不许出现什么"是产品侧知识，应当留在产品里**；
     "怎么执行导出"才是整理工具，才该搬走。
     本文件就是留在产品里的那份规格，beimport 双方共享：
        · 门禁 `24 leakcheck` 直接 import 本文件做自检；
        · 搬走的 `make_public.py` 反过来读取本文件，避免两边各写一份。

【关于 `tools/scripts/*` 那几条规则】
  整理工具已经搬出工作树，所以那些路径**在本仓里结构上不可能出现** ——
  规则保留着也无害（防御性），但不再是"当前必须靠它挡住"的东西。
  `tools/scripts/_*.py` 同理：一次性脚本已随之搬走。
"""
import re

#---------------------------------------------------------------------------
# 1) 要从公开版移除的路径（目录不带尾斜杠；与 IGNORE_BLOCK 的写法不同，
#    规范化由 representative()/覆盖检查负责 —— 别再踩"notes" vs "notes/" 的坑）
#---------------------------------------------------------------------------
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

#---------------------------------------------------------------------------
# 2) 追加进公开版 .gitignore 的规则块
#---------------------------------------------------------------------------
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
# 一次性排查脚本（命名带 _ 前缀的临时工具）—— 已搬出工作树，保留规则作防御
tools/scripts/_*.py
# 仓库整理/备份工具本身 —— 已搬出工作树到 ../fpga-export-tooling/
tools/scripts/scan_traces.py
tools/scripts/neutralize_comments.py
tools/scripts/neutralize_docs.py
tools/scripts/make_public.py
tools/scripts/git_precheck.py
tools/scripts/fix_gitignore.py
tools/scripts/strip_refs.py
# 图形界面自测报告：生成的调试产物（非源码）
sim_build/gui/selftest_report.txt
# 赛事情报与学习路线：准备阶段的资料（大量引用 refs/ 下的第三方原文），
# 不是本项目的工程产出，且这些引用在公开版里会全部失效
docs/01-竞赛情报/
docs/03-学习路线/
docs/02-技术方案/22-全面审计-2026-10-04.md
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

#---------------------------------------------------------------------------
# 3) 泄漏判据（提交前逐条核对索引；命中即中止）
#
#    ★ 三条实测教训（都写在这里，避免后来人重犯）：
#      ① ASCII 词必须加词边界。原来 `GLM` 不带 \b，于是内联 base64 里
#         `...ZwGlmTZl...` 被算成身份痕迹（5 个架构 HTML 各报 A=2）。
#      ② 目录条目要写成 `dir/`（带斜杠），否则 `notes` 匹配不上 `^notes/`。
#      ③ 正则命中 ≠ 事实：报出命中后**必须打印上下文再定性**。
#---------------------------------------------------------------------------
LEAK_PATTERNS = [
    r"^refs/",
    r"^PROJECT_MEMORY\.md$",
    r"^\.zcodeignore$",
    r"^notes/",
    r"^backups/",
    r"^tools/pylib/",
    r"^src/rtl/archive/",
    r"^src/gowin/bringup_9k/",
    r"^tools/scripts/_",
    r"^tools/scripts/(scan_traces|neutralize_comments|neutralize_docs|"
    r"make_public|git_precheck|fix_gitignore|strip_refs|check_video_timing|"
    r"make_image_rom)\.py$",
    r"^tools/scripts/flash_sram\.cmd$",
    r"^src/rtl/(bringup_top|image_rom|image_view|lcd_480x272|test_pattern|"
    r"led_heartbeat|i2c_master)\.v$",
    r"^src/rtl/README\.md$",
    r"^src/sim/(mpr121_model|tb_i2c_master)\.v$",
    r"^src/constr/bringup_top\.cst$",
    r"^docs/01-竞赛情报/",
    r"^docs/03-学习路线/",
    r"^docs/02-技术方案/22-全面审计-2026-10-04\.md$",
    r"^docs/02-技术方案/07-候选架构方案-v1\.md$",
    r"^docs/02-技术方案/09-第一次烧录bring-up指南\.md$",
    r"^sim_build/gui/selftest_report\.txt$",
]


def find_leaks(files):
    """返回索引里**不该出现**的路径列表（空 = 干净）"""
    pats = [re.compile(p) for p in LEAK_PATTERNS]
    out = []
    for f in files:
        for p in pats:
            if p.search(f):
                out.append(f)
                break
    return out


def ignore_rules():
    """IGNORE_BLOCK 里的规则（去掉注释与空行）"""
    return [ln.strip() for ln in IGNORE_BLOCK.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
