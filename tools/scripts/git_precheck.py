# -*- coding: utf-8 -*-
"""git 备份前的**精确校验**（避免 PowerShell 对中文路径/编码的坑 ✗）：

  ① 重新暂存（先清空索引）
  ② 统计：文件数、总体积、>1 MB 的大件清单
  ③ 断言：关键源文件在库、危险产物不在库
  ④ 全部通过才提交

用法：python tools/scripts/git_precheck.py [--commit "提交信息"]
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 必须在库里（少了 clone 下来就编不过 / 跑不起来）
MUST_HAVE = [
    "src/rtl/tdm_top.v", "src/rtl/note_map.v", "src/rtl/pad_scan.v",
    "src/rtl/fx_delay.v", "src/rtl/reg_bank.v", "src/rtl/song_seq.v",
    "src/gowin/tdm_synth/tdm_synth.gprj",
    "src/gowin/tdm_synth/note_inc.hex", "src/gowin/tdm_synth/preset_part.hex",
    "src/gowin/tdm_synth/recip_inc.hex",
    "src/constr/tdm_top.cst", "src/constr/tdm_top.sdc",
    "tools/scripts/dsp_host.py", "tools/scripts/regress_all.py",
    "tools/host/dsp_gui.py", "tools/host/theme.qss", "tools/host/build_exe.py",
    ".gitignore",
]
# 绝不能进库（要么巨大、要么可再生成）
MUST_NOT = ("/impl/", ".fs", ".vcd", ".vvp", ".exe", "/build/", "/dist/",
            "backups/", "__pycache__", ".spec")


def git(*args, **kw):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **kw)


def main():
    # core.quotepath=false：中文文件名原样输出，别转义
    git("config", "core.quotepath", "false")
    git("config", "i18n.commitEncoding", "utf-8")

    print("[1] 清空索引并重新暂存")
    git("rm", "-r", "--cached", ".", "-q")
    r = git("add", "-A")
    if r.returncode != 0:
        print("  ✗ git add 失败：%s" % r.stderr)
        return 1

    r = git("ls-files")
    files = [f for f in r.stdout.splitlines() if f.strip()]
    print("  暂存文件数 = %d" % len(files))

    total = 0
    big = []
    for f in files:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            n = os.path.getsize(p)
            total += n
            if n > 1024 * 1024:
                big.append((n, f))
    print("  合计体积 = %.2f MB" % (total / 1048576.0))

    print("[2] 大件（>1 MB）清单：")
    if not big:
        print("     （无 ✓）")
    for n, f in sorted(big, reverse=True):
        print("     %7.2f MB  %s" % (n / 1048576.0, f))

    print("[3] 校验")
    fails = 0
    miss = [f for f in MUST_HAVE if f not in files]
    if miss:
        fails += 1
        print("  ✗ 关键文件缺失：")
        for f in miss:
            print("       %s" % f)
    else:
        print("  ✓ 关键源文件全部在库（%d 项）" % len(MUST_HAVE))

    bad = [f for f in files if any(k in f.replace("\\", "/") for k in MUST_NOT)]
    if bad:
        fails += 1
        print("  ✗ 有不该进库的产物：")
        for f in bad[:12]:
            print("       %s" % f)
    else:
        print("  ✓ 没有 impl//.fs/.vcd/.exe/build/dist/backups 等产物 ✓")

    print("  提示：素材库中文名文件数 = %d" % sum(1 for f in files if "素材库" in f))

    print("[4] 结论")
    if fails:
        print("  ✗ 校验不通过 ⇒ 未提交（先修 .gitignore 或补文件）")
        return 1
    print("  ✓ 校验通过 ⇒ 可以提交 ✓")
    if "--commit" in sys.argv:
        msg = sys.argv[sys.argv.index("--commit") + 1]
        r = git("commit", "-q", "-m", msg)
        if r.returncode != 0:
            print("  ✗ 提交失败：%s%s" % (r.stdout, r.stderr))
            return 1
        r = git("log", "--oneline", "-1")
        print("  ✓ 已提交：%s" % r.stdout.strip())
        r = git("count-objects", "-vH")
        for ln in r.stdout.splitlines():
            if ln.startswith(("count", "size-pack", "size:")):
                print("     %s" % ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
