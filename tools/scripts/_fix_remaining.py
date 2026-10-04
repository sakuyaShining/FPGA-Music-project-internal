# -*- coding: utf-8 -*-
"""收尾清理：把公开版里剩余的痕迹引用与措辞逐条改掉。

这些位置大多是**指向内部材料（refs/素材库/...）的引用**——公开版里这些文件并不存在，
引用留着的后果是"点进去 404"，同时也是痕迹。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (文件, 旧子串, 新子串)
EDITS = [
    # 21-验收判据清单.md
    ("docs/02-技术方案/21-验收判据清单.md",
     ">**当前完成/未验证状态以 `refs/素材库/未验证与挂账清单.md` 为准**，不要把本文件的历史待办当作当前状态。",
     "> 本文件给出判据全集与配方；各项的当前完成状态以回归结果和硬件验收为准。"),
    ("docs/02-技术方案/21-验收判据清单.md",
     "> 配套：`未验证与挂账清单.md`（维护的账本）、`regress_all.py`（闸口）、`双代理任务板.md`。",
     "> 配套工具：`tools/scripts/regress_all.py`（回归入口）。"),
    # 19-UART协议v1.0草案.md
    ("docs/02-技术方案/19-UART协议v1.0草案.md",
     "以 `refs/素材库/未验证与挂账清单.md` 为准。",
     "以实测回归结果为准。"),
    # src/rtl/README.md
    ("src/rtl/README.md",
     "`refs/素材库/未验证与挂账清单.md`；",
     ""),
    # src/rtl/tdm_top.v —— 行尾注释里的轮次标记与符号
    ("src/rtl/tdm_top.v", "★ 第 9 轮：", ""),
    ("src/rtl/tdm_top.v", "（实测 91.9% ✗）", "（实测 91.9% 的样本被限幅）"),
    # 工具脚本里的措辞
    ("tools/scripts/audio_check.py", "为什么用它（挂账清单 C2）：", "为什么用它（判据 C2）："),
    ("tools/scripts/dsp_host.py", "电极遥测（第 7 轮）：", "电极遥测："),
    ("tools/scripts/regmap_dump.py", "冻结后的规矩（建议写进任务板）：", "冻结后的规矩："),
    ("tools/scripts/regress_all.py", "存在失败，禁止销账/上板", "存在失败，不满足上板条件"),
    # 最后一轮补齐：仍指向内部材料的引用
    ("docs/02-技术方案/21-验收判据清单.md",
     "，频率压力测试方法见素材库“时序裕量特征”）",
     "）"),
    ("tools/scripts/dsp_host.py",
     "为什么这是“上板第一件事”（refs/素材库/步骤16_上板风险审计.md §1）：",
     "为什么这是“上板第一件事”："),
]


def main():
    total = 0
    for f, old, new in EDITS:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            print("  [跳过，不存在] %s" % f)
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        n = s.count(old)
        if n == 0:
            print("  [未命中] %s  «%s»" % (f, old[:40]))
            continue
        s = s.replace(old, new)
        io.open(p, "w", encoding="utf-8", newline="").write(s)
        total += n
        print("  %-38s x%d" % (f, n))
    print("  合计 %d 处" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
