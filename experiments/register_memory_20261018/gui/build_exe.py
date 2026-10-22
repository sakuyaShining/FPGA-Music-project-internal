#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_exe.py —— 一条命令把上位机打成**单文件 exe**，并**自测产物** ✓

用法：
    python tools/host/build_exe.py

为什么用 Python 而不是 .ps1：
    本机 PowerShell 5.1 会把子进程写 stderr 当成 NativeCommandError ✗（gw_sh 那次踩过），
    而且 --add-data 的 "src;dest" 分号在 PS 里也容易出问题 ⇒ 用 Python 编排干净 ✓。

打包内容（三份 data，缺一个 exe 就跑不起来 ✗）：
    theme.qss                —— 主题样式表
    dsp_host.py              —— 协议地址表/帧构造（**必须进包**，否则 exe 里 import 不到 ✗）
    regmap_baseline.csv      —— RTL 抽取的上电默认值（模拟设备用它，读不到就全 0 ✗）

自测（关键 ✓）：打完直接运行 exe 的 --selftest，检查
    ① 退出码 0  ② 截图与报告文件是**本次**新写的 ③ 报告里含 PASS
—— 这样"exe 能不能跑"不靠猜 ✓，有可证伪的证据 ✓。
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUTPUT_ROOT = os.path.abspath(os.environ.get('FPGA_HOST_BUILD_ROOT', HERE))
DIST = os.path.join(OUTPUT_ROOT, "dist")
BUILD = os.path.join(OUTPUT_ROOT, "build")
EXE = os.path.join(DIST, "fpga_workbench.exe")
OUTDIR = os.path.join(ROOT, "sim_build", "gui")


def run(args, **kw):
    print("  $ " + " ".join(args))
    return subprocess.call(args, cwd=ROOT, **kw)


def have(mod):
    return subprocess.call([sys.executable, "-c", "import " + mod],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def need(mod, pkg=None):
    if have(mod):
        print("  %-12s 已装 ✓" % mod)
        return True
    pkg = pkg or mod
    print("  安装 %s …" % pkg)
    if run([sys.executable, "-m", "pip", "install", pkg]) != 0:
        print("  ✗ pip 安装 %s 失败（网络/代理？可以手动装完再跑本脚本）" % pkg)
        return False
    return True


def main():
    # 本机 pip 曾因【Windows 系统代理指向一个不存在的代理】而全部失败
    #   （报 ProxyError / getaddrinfo failed），而 NO_PROXY=* 可以绕过
    #   —— 实测有效：pyserial 用这一条装上了 。放在最前面，免得每次都要手工设
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")

    print("=" * 70)
    print(" 打包上位机 → 单文件 exe")
    print("=" * 70)

    # ---- 1. 依赖 ----
    print("[1/4] 依赖检查")
    if not need("PyInstaller", "pyinstaller"):
        return 1
    # pyserial 必须**打包时**已安装，否则 exe 里没有串口能力 （冻结后不能再用系统的）
    if not need("serial", "pyserial"):
        return 1
    if not need('PyQt5') or not need('numpy'):
        return 1

    # ---- 2. 清理 ----
    print("[2/4] 清理构建缓存（保留已交付的程序）")
    for d in (BUILD,):
        if os.path.commonpath((os.path.realpath(d), os.path.realpath(OUTPUT_ROOT))) != os.path.realpath(OUTPUT_ROOT):
            raise RuntimeError('构建目录不在指定输出根目录内')
        if os.path.isdir(d):
            try:
                import shutil
                shutil.rmtree(d)
                print("  已删 %s" % d)
            except OSError as e:
                print("  ⚠ 删不掉 %s：%s（继续）" % (d, e))

    # ---- 3. 打包 ----
    #   路径必须用**绝对路径** ：PyInstaller 3.6 会把 --add-data 的源路径
    #     按 **--specpath 目录** 解析 ⇒ 相对路径会拼成 tools\host\tools\host\... 找不到
    def A(p):
        return os.path.join(ROOT, p)

    # onefile启动时先解压DLL，此时Python代码尚未运行。必须把运行时
    # 临时目录写入bootloader，不能仅设置构建进程的TEMP/TMP。
    runtime_temp = os.path.join(OUTPUT_ROOT, 'temp')
    os.makedirs(runtime_temp, exist_ok=True)
    print("[3/4] PyInstaller 打包（onefile + windowed）")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
            "--name", "fpga_workbench",
            "--hidden-import", "pkg_resources.py2_warn",
            "--runtime-tmpdir", runtime_temp,
            "--paths", A(os.path.join("tools", "scripts")),
            "--add-data", A(os.path.join("tools", "host", "theme.qss")) + os.pathsep + ".",
            "--add-data", A(os.path.join("tools", "host", "host_version.json")) + os.pathsep + ".",
            "--add-data", A(os.path.join("tools", "host", "fonts")) + os.pathsep + "fonts",
            "--add-data", A(os.path.join("tools", "scripts", "dsp_host.py")) + os.pathsep + ".",
            "--add-data", A(os.path.join("docs", "02-技术方案", "regmap_baseline.csv")) + os.pathsep + ".",
            "--distpath", DIST,
            "--workpath", BUILD,
            "--specpath", OUTPUT_ROOT,
            A(os.path.join("tools", "host", "dsp_gui.py"))]
    if run(args) != 0:
        print("  ✗ 打包失败")
        return 1
    if not os.path.isfile(EXE):
        print("  ✗ 没找到产物 %s" % EXE)
        return 1
    print("  ✓ 产物：%s（%.1f MB）" % (EXE, os.path.getsize(EXE) / 1048576.0))

    # ---- 4. 自测产物（关键）----
    print("[4/4] 自测产物：运行 exe 的 --selftest 并检查新写的文件")
    png = os.path.join(OUTDIR, "gui_preview.png")
    rpt = os.path.join(OUTDIR, "selftest_report.txt")
    t0 = time.time()
    rc = subprocess.call([EXE, "--selftest"], cwd=ROOT)
    print("  exe 退出码 = %d" % rc)
    ok = (rc == 0)
    ok = subprocess.call([EXE, '--workbench-selftest'],cwd=ROOT)==0 and ok
    ok = subprocess.call([EXE, '--startup-check'],cwd=ROOT)==0 and ok
    for p in (png, rpt):
        if os.path.isfile(p) and os.path.getmtime(p) >= t0 - 2:
            print("  ✓ 已刷新：%s" % os.path.relpath(p, ROOT))
        else:
            print("  ✗ 未生成/未刷新：%s" % p)
            ok = False
    if os.path.isfile(rpt):
        txt = open(rpt, encoding="utf-8").read()
        if "PASS" in txt:
            print("  ✓ 报告含 PASS")
            for line in txt.splitlines():
                if line.strip():
                    print("      | " + line.strip())
        else:
            print("  ✗ 报告里没有 PASS")
            ok = False
    print("=" * 70)
    print(" RESULT build_exe=%s exe=%s" % ("PASS" if ok else "FAIL", EXE))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
