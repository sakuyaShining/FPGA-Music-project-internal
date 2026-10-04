# -*- coding: utf-8 -*-
"""用 Python 重写 .gitignore（避免编辑工具吞换行 ✗），并用 **git 自己** 验证规则生效 ✓。

验证方式：git check-ignore -v <路径> —— 它会把命中的规则与行号打印出来 ✓
无输出 = 没有任何规则命中 = 漏网 ✗（这正是上一轮问题的诊断手段 ✓）
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTENT = "\n".join([
    "# =============================================================================",
    "#  .gitignore - FPGA-Music-project",
    "#",
    "#  原则：只传源与证据，不传可再生成的产物。",
    "#    - 源码本体其实只有 ~6 MB（src 去掉 impl/ + tools 去掉产物）",
    "#    - 不排除的话仓库会到 400+ MB（exe 37 MB / VCD 23 MB / 码流 7 MB ...）",
    "#",
    "#  ★ 特别提醒：src/gowin/tdm_synth/*.hex 是【综合用的静态表】",
    "#    （音高表 note_inc / 预设泛音表 preset_part / 倒数表 recip_inc）",
    "#    **必须进仓库** —— 少了它们，clone 下来根本编不过。",
    "#    所以【绝不能】写全局 `*.hex`，只排除 sim_build 里的副本。",
    "#",
    "#  ★ 验证方法（可证伪）：",
    "#      git check-ignore -v src/gowin/impl/pnr/led_blink.log",
    "#    打印出规则与行号 = 命中 ✓；无输出 = 漏网 ✗",
    "# =============================================================================",
    "",
    "# ---- 1. Gowin 综合/布局布线产物（可再生成）----",
    "#   ★ 必须用 ** 匹配任意深度：`src/gowin/*/impl/` 只匹配一层子目录，",
    "#     会漏掉 `src/gowin/impl/`（led_blink 工程的产物）—— 实测漏进 401 个文件里。",
    "src/gowin/**/impl/",
    "src/gowin/impl/",
    "src/gowin/*/impl/",
    "*.fs",
    "*.vg",
    "*.db",
    "*.log",
    "*.prj",
    "*.rsc.xml",
    "*.bin",
    "*.binx",
    "*.timing_paths",
    "*.rpt.txt",
    "*.rpt.html",
    "*.pin.html",
    "*.power.html",
    "*.tr.html",
    "",
    "# ---- 2. 仿真产物（体积大，且可重跑）----",
    "#   先排除 sim_build 下的一切，再【放行目录】（gitignore 规则：",
    "#   父目录被排除时无法再放行子文件，所以必须放行目录本身）",
    "sim_build/*",
    "!sim_build/audio/",
    "!sim_build/show/",
    "!sim_build/gui/",
    "sim_build/audio/*.txt",
    "sim_build/show/*.txt",
    "sim_build/show/*.hex",
    "*.vcd",
    "*.vvp",
    "*.out",
    "*.lxt",
    "*.lxt2",
    "",
    "# ---- 3. PyInstaller / Python 产物 ----",
    "tools/host/build/",
    "tools/host/dist/",
    "*.spec",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "",
    "# ---- 4. 旧快照与临时文件 ----",
    "#   backups/ 是 2026-10-01 的整目录快照（88 MB，含重复源码）。",
    "#   想要整目录备份请用云盘/移动硬盘，不要塞进 git。",
    "backups/",
    "*.tmp",
    "*.bak",
    "*~",
    "Thumbs.db",
    "desktop.ini",
    ".vscode/",
    ".idea/",
    "",
    "# ---- 5. 第三方参考资料（36+ MB，非本项目产出）----",
    "#   竞赛官方/往年/官网存档属于别人的资料，不适合放进作品仓库。",
    "refs/_site-archive/",
    "refs/candidate-guides/",
    "refs/past-years/",
    "refs/official-notices/",
    "refs/report-template/",
    "refs/vendor-examples/",
    "",
])

p = os.path.join(ROOT, ".gitignore")
with open(p, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(CONTENT)
print("  已重写 .gitignore：%d 行 / %d 字节" % (CONTENT.count("\n"), len(CONTENT.encode("utf-8"))))

# ---- 用 git 自己验证规则是否命中 ✓ ----
CASES = [
    ("src/gowin/impl/pnr/led_blink.log", True),
    ("src/gowin/tdm_synth/impl/pnr/tdm_synth.fs", True),
    ("tools/host/dist/dsp_gui.exe", True),
    ("sim_build/regress/01_additive/osc_additive.vcd", True),
    ("backups/2026-10-01_1646/PROJECT_MEMORY.md", True),
    ("refs/past-years/xxx.pdf", True),
    # 下面这些**必须不被忽略** ✓（漏了就会让仓库跑不起来）
    ("src/rtl/tdm_top.v", False),
    ("src/gowin/tdm_synth/note_inc.hex", False),
    ("tools/scripts/dsp_host.py", False),
    ("sim_build/audio/效果器对比_干声延迟合唱混响_48000.wav", False),
    ("sim_build/gui/selftest_report.txt", False),
]

fails = 0
print("  ---- git check-ignore 验证 ----")
for path, should_ignore in CASES:
    #   ★ 必须加 --no-index ✗：对**已在索引里**的路径，check-ignore 默认会跳过不报
    #     ⇒ 会误判成"规则没生效"（上一轮就是这么被骗的 ✓）
    r = subprocess.run(["git", "check-ignore", "-v", "--no-index", path], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    hit = bool(r.stdout.strip())
    ok = (hit == should_ignore)
    fails += 0 if ok else 1
    rule = r.stdout.strip().split("\t")[0] if hit else "-"
    print("  %s %-52s 期望%s 实际%s   %s"
          % ("✓" if ok else "✗", path, "忽略" if should_ignore else "保留",
             "忽略" if hit else "保留", rule))

print("  ⇒ %s" % ("规则全部符合预期 ✓" if fails == 0 else "有 %d 条不符合 ✗" % fails))
raise SystemExit(0 if fails == 0 else 1)
