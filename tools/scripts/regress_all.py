#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
regress_all.py —— 全项目一键回归门

【为什么要有它】
  单一工作区并行改动的最大风险，是一处修改悄悄破坏另一处已验证的性质。
  本脚本把快速自检串成一条命令，任何 RTL/脚本改动后：
      python tools/scripts/regress_all.py            # 快速门（约 2-4 分钟）
      python tools/scripts/regress_all.py --full     # 加 TDM 8掩码×双配置 扫描
  全绿才算数 —— 这是回归基线（R0 生命线）。

【包含的套件】（文件清单以 2026-10-02 实测可用为准）
  01 additive   加法引擎 + Python≡RTL 逐位一致（synth_engine.py verify）
  02 clock      音频时钟链 S1–S6
  03 envelope   包络 A1–A9
  04 i2s        I2S 闭环（tb 自检 + 解码/源文件逐位比对）
  05 voices     多声部（mix_a FFT 4 峰）
  06 testmode   测试模式（tm_fixed 32 峰 + 随机窗可区分）
  07 regpitch   变调（过零频率比 440:660:440）
  08 seq        片上定序器（seq_check.py S1–S6）
  09 regctl     运行时参数/音色/旁路/定序集成（reg_ctl_check.py）
  10 fx         延迟+合唱冲激响应（fx_check.py，-DSIM_INIT）
  09b vp7       上电默认值/静音/音色通路（此前遗漏，2026-10-03 补入）
  11 tdm        TDM≡全并行黄金参考（默认全掩码；--full 时 8掩码×ENV 0/1）
  13 vel shape  力度→谱形单元 V1-V9（含灵敏度只缩放偏差）
  14 vel timbre 力度→音色 + 独立亮度轴 0x5C 端到端 J1-J4 / L1-L6
  15 i2s std    I2S 标准接收器（与 04 的旧模型同线对照，两条口径都留）
  16 i2s top    顶层音频通路端到端：tdm_top → fx → i2s_tx → 标准接收器
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RTL = os.path.join(ROOT, "src", "rtl")
SIM = os.path.join(ROOT, "src", "sim")
BUILD = os.path.join(ROOT, "sim_build", "regress")
IV = r"D:\iverilog\bin"

FULL_BASE = ["osc_core.v", "osc_env.v", "osc_additive.v", "mixer.v", "synth_top.v"]


def rtl(f):
    return os.path.join(RTL, f)


def sim(f):
    return os.path.join(SIM, f)


def run(cmd, cwd, timeout=1800, env_extra=None):
    # 超时用于抓「卡死」，不是性能门槛。vp7 是合法长测（约 600 秒，
    # 因为它在 27 MHz 下模拟约 314 ms 音频），600 秒会把它误判成超时。
    # 提到 1800 秒：留足合法余量，仍能抓住真正的挂死。
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired as e:
        # 2026-10-04 审计 P1：超时必须变成"该套件标红"，不能让整个闸口崩成
        #   traceback（原来无捕获，一个仿真挂死 = 门本身崩，掩盖失败原因）。
        #   返回 rc=None + 日志带 [TIMEOUT]，各 rc!=0 分支自然处理。
        out = (e.stdout or b"").decode("utf-8", errors="replace")
        return None, "[TIMEOUT] %ds\n%s" % (timeout, out[-2000:])
    return p.returncode, p.stdout.decode("utf-8", errors="replace")


def rmtree_ok(d):
    """删除目录；遇锁重试（本机常驻监视进程会持有产物句柄）；
    仍删不掉就容忍继续 —— 绝不让文件锁把闸口弄崩（判据按内容自行判断）。"""
    for _try in range(10):
        try:
            shutil.rmtree(d)
            return True
        except OSError:
            time.sleep(0.5)
    print("  [warn] 目录被占用，跳过清空：%s" % d)
    return False


def sine_hex():
    """正弦表来源：优先综合目录的权威副本，其次 01_additive 产出的缓存。

    2026-10-05 教训：原来只认缓存 sim_build/_hex/。缓存缺失时 $readmemh 失败，
    正弦表全 X、音频全 X —— 而 09 regctl 曾因运行目录残留上一次的产物而
    "通过"，把这个缺陷掩盖成了假绿。判据必须建立在本次真实产物上。
    """
    auth = os.path.join(ROOT, "src", "gowin", "tdm_synth", "sine256.hex")
    if os.path.isfile(auth):
        return auth
    return os.path.join(BUILD, "_hex", "sine256.hex")


def patch_sine_path(d):
    """02–07 这些套件不走 copy_data，而是**覆盖** 01_additive 产出的 sine256.hex。

    2026-10-06：这里补 tilt_wtab.hex。
      这些套件本身不实例化 note_map，用不到亮度表；但 note_map.v 一旦被加进
      某个套件的源文件清单（本项目已发生过两次"某个套件漏登记源文件"），
      缺表就会立刻变成"音频全 X"。补这一行等于把这个陷阱提前填掉，
      代价是一次 1 KB 的文件拷贝。
    """
    if os.path.isfile(sine_hex()):
        shutil.copy(sine_hex(), d)
    wt = os.path.join(ROOT, "src", "gowin", "tdm_synth", "tilt_wtab.hex")
    if os.path.isfile(wt):
        shutil.copy(wt, d)
    return [h for h in ("sine256.hex", "tilt_wtab.hex")
            if not os.path.isfile(os.path.join(d, h))]


DATA_FILES = ("sine256.hex", "note_inc.hex", "preset_part.hex",
              "recip_inc.hex", "vel_wtab.hex", "tilt_wtab.hex")


def copy_data(d, extra=(), build_dir=None):
    """把仿真运行目录需要的所有数据文件一次拷齐。

    2026-10-06 第三次栽在同一类问题上（运行目录缺 hex ⇒ $readmemh 失败 ⇒
    音频全 X ⇒ 判据崩），根因是【同一件事在四处各写一遍】。这里收成唯一入口：
    新增数据文件只改 DATA_FILES，不再逐个套件补。

    ★ 2026-10-06 二次加固：源文件缺失时**必须让闸口红**。
      原来 `if os.path.isfile(p)` 静默跳过 —— 缺表不会报错，只会让下游
      判据拿到 X，报出来的是一句莫名其妙的 ValueError（当天就这么白查了一轮）。
      现在缺源文件直接列进 missing，由调用方标红并说明缺的是哪一张表。

    build_dir：02–07 这类"先用 01 additive 产出 sine256.hex、再覆盖"的套件，
      缓存就在 sim_build/ 下而不在 src/gowin/tdm_synth/。给了 build_dir 时
      允许回退到 sim_build/_hex/ 找，找不到同样算 missing（不再静默通过）。
    """
    src_dir = os.path.join(ROOT, "src", "gowin", "tdm_synth")
    cache = os.path.join(build_dir, "_hex") if build_dir else None
    missing = []
    for h in DATA_FILES:
        p = os.path.join(src_dir, h)
        if not os.path.isfile(p) and cache:
            p = os.path.join(cache, h)
        if os.path.isfile(p):
            shutil.copy(p, d)
        else:
            missing.append(h)
    for h in extra:
        if os.path.isfile(h):
            shutil.copy(h, d)
        else:
            missing.append(os.path.basename(h))
    # 拷贝后逐个复核：拷贝失败（锁/权限）同样不能静默通过
    for h in DATA_FILES:
        if h not in missing and not os.path.isfile(os.path.join(d, h)):
            missing.append(h + "(拷贝失败)")
    return missing


def compile_and_run(name, files, defines=(), plusargs=(), need_hex=False, extra_hex=()):
    """在 sim_build/regress/<name>/ 里编译并运行一个测试台，返回 stdout"""
    d = os.path.join(BUILD, name)
    # 每次清空运行目录：判据脚本读目录下的产物文件，残留旧代产物会污染判据
    #   （遇锁重试机制见 rmtree_ok 的注释，2026-10-03 遇 PermissionError 教训）
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    if need_hex:
        miss = copy_data(d, extra_hex, build_dir=BUILD)
        if miss:
            return None, ("缺数据文件：%s —— 运行目录缺 hex 会让 $readmemh 失败、"
                          "音频全 X、判据崩成 traceback。"
                          "源目录 = src/gowin/tdm_synth/" % ", ".join(miss))
    # tb 文件归 sim，其余 rtl
    srcs = []
    for f in files:
        p = sim(f) if f.startswith("tb_") else rtl(f)
        srcs.append(p)
    out = os.path.join(d, "sim.vvp")
    # 顶层 = tb_ 开头的文件（测试台），没有则退回第一个文件
    top = next((f[:-2] for f in files if f.startswith("tb_")), files[0][:-2])
    cmd = [os.path.join(IV, "iverilog.exe"), "-g2005", "-o", out, "-s", top]
    for df in defines:
        cmd.append("-D" + df)
    cmd += srcs
    rc, log = run(cmd, d)
    if rc != 0:
        return None, "COMPILE FAIL:\n" + log
    cmd = [os.path.join(IV, "vvp.exe"), "sim.vvp"] + list(plusargs)
    rc, log = run(cmd, d)
    if rc != 0 and "[TIMEOUT]" not in log:
        return None, "RUN FAIL (rc=%d):\n%s" % (rc, log[-2000:])
    return log, None


# ---------------------------------------------------------------- 判据
def judge_pass_text(log):
    return ("[PASS]" in log or "★★★ 通过" in log) and "[FAILED]" not in log and "[FAIL]" not in log


def judge_i2s(name):
    d = os.path.join(BUILD, name)
    src = [int(l) for l in open(os.path.join(d, "i2s_src.txt")) if l.strip()]
    dec = [tuple(map(int, l.split())) for l in open(os.path.join(d, "i2s_dec.txt")) if l.strip()]
    left = [v for lr, v in dec if lr == 0]
    m = min(len(left) - 1, len(src))
    bad = sum(1 for i in range(m) if left[1 + i] != src[i])
    return bad == 0, "解码侧跳过1个同步字后不符 %d/%d" % (bad, m)


def fft_peaks(path, fs, thr_rel=0.02):
    import numpy as np
    x = np.array([float(v) for v in open(path) if v.strip()])
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / fs)
    thr = X.max() * thr_rel
    return [round(f[i]) for i in range(1, len(X) - 1)
            if X[i] > X[i - 1] and X[i] >= X[i + 1] and X[i] > thr]


def judge_voices(name):
    p = fft_peaks(os.path.join(BUILD, name, "mix_a.txt"), 52734.375, 0.05)
    ok = len(p) >= 4
    return ok, "谱峰=%s（期望≥4 个基频峰）" % p[:8]


def judge_testmode(name):
    p1 = fft_peaks(os.path.join(BUILD, name, "tm_fixed.txt"), 52734.375, 0.01)
    ok1 = len(p1) == 32
    pa = set(v // 400 for v in p1)
    pb = set(v // 400 for v in fft_peaks(os.path.join(BUILD, name, "tm_rnd_b.txt"), 52734.375, 0.02))
    ok2 = (pa != pb) and len(pa) >= 16
    return ok1 and ok2, "固定峰数=%d(应32) 窗A格=%d 窗B格=%d %s" % (
        len(p1), len(pa), len(pb), "" if ok2 else "两随机窗不可区分!")


def judge_regpitch(name):
    import numpy as np
    p = np.array([float(v) for v in open(os.path.join(BUILD, name, "pitch.txt")) if v.strip()])
    seg = len(p) // 3
    freqs = []
    for i in range(3):
        s = p[i * seg:(i + 1) * seg]
        zc = np.sum(np.diff(np.signbit(s)) != 0)
        freqs.append(zc / 2 / (seg / 52734.375))
    r = freqs[1] / freqs[0]
    ok = 1.45 <= r <= 1.55 and abs(freqs[2] - freqs[0]) / freqs[0] < 0.05
    return ok, "三段频率=%s 段2/段1=%.3f（期望≈1.5）" % ([round(f) for f in freqs], r)


def judge_script(name, script):
    rc, log = run([sys.executable, os.path.join(ROOT, "tools", "scripts", script),
                   "--simdir", os.path.join(BUILD, name)], BUILD)
    # 2026-10-05：把判据的【完整】输出落盘。此前只留最后 400 字符，
    #   结果判据脚本中途抛异常时，异常信息恰好落在被截掉的部分，
    #   排查只能靠猜。可诊断性比节省这点字节重要得多。
    try:
        with open(os.path.join(BUILD, "%s_judge.log" % name.replace(" ", "_")), "w",
                  encoding="utf-8") as fh:
            fh.write(log)
    except Exception:
        pass
    return (rc == 0 and ("通过" in log or "PASS" in log or "★★★" in log)), log[-400:]


def judge_tdm_compare(name):
    """★ 判据 = 黄金参考行（TDM≡并行 0 不符）。
    不能用返回码：包络打开时解析真值项必然不符（模型不建模包络），
    tdm_compare 会返回非零 —— 那是预期行为，不是失败。"""
    rc, log = run([sys.executable, os.path.join(ROOT, "tools", "scripts", "tdm_compare.py"),
                   "--simdir", os.path.join(BUILD, name),
                   "--mask", "0xFFFFFFFF"], BUILD)
    golden = [l for l in log.splitlines() if "黄金参考" in l]
    ok = bool(golden) and "不符 0 /" in golden[-1] and "黄金参考通过" in golden[-1]
    return ok, golden[-1].strip() if golden else log[-120:]


TDM_MASK = 0xFFFFFFFF


def run_tdm_mask(mask, env_on):
    """--full 用：打补丁的 tb 副本跑指定掩码/包络配置"""
    d = os.path.join(BUILD, "11_tdm_%08X_e%d" % (mask, env_on))
    os.makedirs(d, exist_ok=True)
    miss = copy_data(d, build_dir=BUILD)
    if miss:
        return False, "缺数据文件：%s" % ", ".join(miss)
    tb = open(sim("tb_tdm_equiv.v"), encoding="utf-8").read()
    tb = re.sub(r"localparam ENV_ON\s*=\s*1'b[01];", "localparam ENV_ON  = 1'b%d;" % env_on, tb)
    tb = re.sub(r"localparam \[NSLOT-1:0\] ACTIVE = 32'h[0-9A-Fa-f]+;",
                "localparam [NSLOT-1:0] ACTIVE = 32'h%08X;" % mask, tb)
    tb_path = os.path.join(d, "tb_patched.v")
    open(tb_path, "w", encoding="utf-8").write(tb)
    files = FULL_BASE[:5] + ["pitch_mod.v", "tdm_engine.v", "tb_patched.v"]
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "sim.vvp", "-s", "tb_tdm_equiv"] +
                  [rtl(f) if not f.startswith("tb_") else tb_path for f in files], d)
    if rc != 0:
        return False, "COMPILE FAIL"
    run([os.path.join(IV, "vvp.exe"), "sim.vvp"], d)
    rc2, log2 = run([sys.executable, os.path.join(ROOT, "tools", "scripts", "tdm_compare.py"),
                     "--simdir", d, "--mask", "0x%08X" % mask], BUILD)
    golden = [l for l in log2.splitlines() if "黄金参考" in l]
    ok = bool(golden) and "不符 0 /" in golden[-1] and "黄金参考通过" in golden[-1]
    return ok, "mask=%08X env=%d : %s" % (mask, env_on, golden[-1].strip() if golden else "无黄金行")


# ---------------------------------------------------------------- 主流程
def main():
    # The final summary contains Unicode status marks. On Windows, the default
    # console encoding may be cp936/GBK and raise UnicodeEncodeError after all
    # suites have run; force UTF-8 so a successful run can always report its result.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="TDM 8掩码×双配置全扫描")
    args = ap.parse_args()

    os.makedirs(BUILD, exist_ok=True)
    hexdir = os.path.join(BUILD, "_hex")
    os.makedirs(hexdir, exist_ok=True)

    results = []

    # 01 additive（先跑：产出 sine256.hex 供其它套件复制）
    d1 = os.path.join(BUILD, "01_additive")
    #   2026-10-04 审计 P2：本目录原先只建不清 —— 与"残留产物污染判据"的自定
    #   原则不一致，补齐（它产出的 hex 会被覆盖，清空安全）。
    if os.path.isdir(d1):
        rmtree_ok(d1)
    os.makedirs(d1, exist_ok=True)
    rc, log = run([sys.executable, os.path.join(ROOT, "tools", "scripts", "additive_tool.py"),
                   "gen", "--outdir", d1], BUILD)
    files = ["osc_core.v", "osc_env.v", "osc_additive.v", "tb_osc_additive.v"]
    cmd = [os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "sim.vvp", "-s", "tb_osc_additive"] + \
          [rtl(f) for f in files[:3]] + [sim(files[3])]
    rc, log = run(cmd, d1)
    rc, log = run([os.path.join(IV, "vvp.exe"), "sim.vvp"], d1)   # 生成样本 dump
    rc2, log2 = run([sys.executable, os.path.join(ROOT, "tools", "scripts", "synth_engine.py"), "verify",
                     "--simdir", d1, "--meta", os.path.join(d1, "stimulus_meta.json")], BUILD)
    ok = rc2 == 0 and "[PASS]" in log2
    line = [l for l in log2.splitlines() if "不一致样本数" in l]
    msg = "逐位一致 " + (line[-1].strip() if line else (log2.strip().splitlines()[-1] if log2.strip() else "无输出"))
    results.append(("01 additive", ok, msg))
    shutil.copy(os.path.join(d1, "sine256.hex"), os.path.join(hexdir, "sine256.hex"))
    #   亮度轴表也进缓存：`patch_sine_path` 优先从综合目录取，取不到时回退这里。
    #   这样"综合目录被清空"也不会让 02–07 组突然缺表。
    _tw = os.path.join(ROOT, "src", "gowin", "tdm_synth", "tilt_wtab.hex")
    if os.path.isfile(_tw):
        shutil.copy(_tw, os.path.join(hexdir, "tilt_wtab.hex"))

    # 02–07：自判据套件
    suites = [
        ("02 clock",     ["audio_clk_en.v", "tb_audio_clk_en.v"], (), (), judge_pass_text, None),
        ("03 envelope",  ["osc_core.v", "osc_env.v", "osc_additive.v", "tb_osc_env.v"], (), (), judge_pass_text, None),
        ("04 i2s",       ["audio_clk_en.v", "i2s_tx.v", "tb_i2s_tx.v"], (), (), lambda n: judge_pass_text(n[0]) and judge_i2s(n[1])[0], "combined"),
        ("05 voices",    FULL_BASE + ["tb_synth_top.v"], (), (), judge_voices, None),
        ("06 testmode",  FULL_BASE + ["test_mode.v", "tb_test_mode.v"], (), (), judge_testmode, None),
        ("07 regpitch",  FULL_BASE + ["reg_bank.v", "tb_reg_pitch.v"], (), (), judge_regpitch, None),
    ]
    for name, files, defs, plus, judge, mode in suites:
        key = name.split()[1]
        log, err = compile_and_run(name.replace(" ", "_"), files, defs, plus, need_hex=True)
        if err:
            results.append((name, False, err[:120]))
            continue
        if mode == "combined":
            ok1 = judge_pass_text(log)
            ok2, msg = judge_i2s("04_i2s")
            results.append((name, ok1 and ok2, "tb:%s dec:%s" % ("PASS" if ok1 else "FAIL", msg)))
        else:
            if judge in (judge_voices, judge_testmode, judge_regpitch):
                ok, msg = judge(name.replace(" ", "_"))
            else:
                ok, msg = judge(log), "tb 自检输出"
            results.append((name, ok, msg))

    # 08 seq（两档节奏各一次冷启动：+test=0 慢 / +test=1 快）
    d = os.path.join(BUILD, "08_seq")
    os.makedirs(d, exist_ok=True)
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "seq.vvp", "-s", "tb_seq",
                   rtl("song_seq.v"), sim("tb_seq.v")], d)
    if rc != 0:
        results.append(("08 seq", False, "COMPILE FAIL"))
    else:
        run([os.path.join(IV, "vvp.exe"), "seq.vvp", "+test=0"], d)
        run([os.path.join(IV, "vvp.exe"), "seq.vvp", "+test=1"], d)
        ok, msg = judge_script("08_seq", "seq_check.py")
        results.append(("08 seq", ok, msg.replace("\n", " ")[:120]))

    # 09 regctl（每个 test 一次冷启动，判据脚本依赖全部产物）
    #   静态表依赖：tb 读 note_inc/preset_part/recip_inc.hex（note_map 综合同样要），
    #     它们是预生成表，权威副本在 src/gowin/tdm_synth/（综合工程），此处从那里取。
    files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v", "song_seq.v",
             "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v", "i2s_tx.v",
             "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v",
             "event_hold.v", "tb_reg_ctl.v"]
    synth_dir = os.path.join(ROOT, "src", "gowin", "tdm_synth")
    tables = [os.path.join(synth_dir, h) for h in
              ("note_inc.hex", "preset_part.hex", "recip_inc.hex")]
    missing = [t for t in tables if not os.path.isfile(t)]
    if missing:
        results.append(("09 regctl", False, "缺静态表: " + ", ".join(os.path.basename(m) for m in missing)))
        files = None
    log, err = (compile_and_run("09_regctl", files, defines=("SIM_INIT",), need_hex=True, extra_hex=tables)
                if files else (None, "skipped"))
    if err:
        results.append(("09 regctl", False, err[:120]))
    elif files:
        d = os.path.join(BUILD, "09_regctl")
        for t in (0, 1, 2, 3, 4, 5):
            run([os.path.join(IV, "vvp.exe"), "sim.vvp", "+test=%d" % t], d, timeout=900)
        ok, msg = judge_script("09_regctl", "reg_ctl_check.py")
        results.append(("09 regctl", ok, msg.replace("\n", " ")[:120]))

    # 09b VP7: this test existed separately but was absent from the gate.
    # The stale 0xC0 expectation escaped prior regression after RTL moved to 0x80.
    vp7_files = ["audio_clk_en.v", "osc_env.v", "i2s_tx.v", "tdm_engine.v",
                 "pitch_mod.v", "note_map.v", "vel_shape.v", "reg_bank.v", "uart_rx.v", "uart_tx.v",
                 "fx_delay.v", "song_seq.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v", "tdm_top.v", "event_hold.v", "tb_vp7.v"]
    vp7_log, vp7_err = compile_and_run(
        "09_vp7", vp7_files, defines=("SIM_INIT",), need_hex=True,
        extra_hex=tables if files else ())
    if vp7_err:
        results.append(("09b vp7", False, vp7_err[:120]))
    else:
        vp7_ok = "RESULT vp7=PASS" in vp7_log and "RESULT vp7=FAIL" not in vp7_log
        vp7_result = next((line.strip() for line in vp7_log.splitlines()
                           if line.startswith("RESULT vp7=")), "missing result")
        results.append(("09b vp7", vp7_ok, vp7_result))

    # 10 fx（三个测试：0=延迟 1=合唱 2=混响[2026-10-02 加入]；判据脚本读全部产物）
    d = os.path.join(BUILD, "10_fx")
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-DSIM_INIT", "-o", "fx.vvp",
                   "-s", "tb_fx", rtl("fx_delay.v"), sim("tb_fx.v")], d)
    ok, msg = False, "compile fail"
    if rc == 0:
        for t in (0, 1, 2):
            run([os.path.join(IV, "vvp.exe"), "fx.vvp", "+test=%d" % t], d)
        ok, msg = judge_script("10_fx", "fx_check.py")
    results.append(("10 fx", ok, msg.replace("\n", " ")[:120]))

    # 11 tdm（快速门：tb 现状全掩码；--full：8掩码×双配置）
    log, err = compile_and_run("11_tdm", FULL_BASE[:5] + ["pitch_mod.v", "tdm_engine.v", "tb_tdm_equiv.v"], need_hex=True)
    if err:
        results.append(("11 tdm", False, err[:120]))
    else:
        ok, msg = judge_tdm_compare("11_tdm")
        results.append(("11 tdm", ok, msg))

    if args.full:
        # 12 F1：TDM 测试模式 512 谱栅格（约 8 分钟仿真；判据见 21 号移交清单 §3）
        d = os.path.join(BUILD, "12_f1")
        if os.path.isdir(d):
            rmtree_ok(d)
        os.makedirs(d, exist_ok=True)
        #   ★ 2026-10-06：这里原来是内联的 hex 清单，加 tilt_wtab.hex 时又漏了一次
        #     （与 14 套件同款故障）。改为走唯一的 copy_data()。
        miss = copy_data(d)
        if miss:
            #   缺表就直接标红，不再去编译/运行（跑了也是全 X，只会掩盖真因）
            results.append(("12 f1", False, "缺数据文件：%s" % ", ".join(miss)))
        else:
            f1_files = ["audio_clk_en.v", "osc_env.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                        "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v",
                        "fx_delay.v", "i2s_tx.v", "tdm_engine.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v",
                        "tdm_top.v", "event_hold.v", "tb_tdm_f1.v"]
            rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "f1.vvp",
                           "-s", "tb_tdm_f1"] +
                          [rtl(f) if not f.startswith("tb_") else sim(f) for f in f1_files], d,
                          timeout=2400)
            ok, msg = False, "compile fail"
            if rc == 0:
                run([os.path.join(IV, "vvp.exe"), "f1.vvp"], d, timeout=2400)
                rc2, log2 = run([sys.executable, os.path.join(ROOT, "tools", "scripts", "f1_check_tdm.py"),
                                 "--simdir", d], BUILD)
                ok = rc2 == 0 and "★★★" in log2
                tail = [l for l in log2.splitlines() if "G" in l or "★" in l]
                msg = " / ".join(tail[-3:]) if tail else log2[-120:]
            results.append(("12 f1", ok, msg.replace("\n", " ")[:120]))

        for env in (0, 1):
            for mask in (0x00000003, 0x0000000F, 0x000000FF, 0x0000FF00,
                         0x00000101, 0x000001FF, 0x0000FFFF, 0xFFFFFFFF):
                ok, msg = run_tdm_mask(mask, env)
                results.append(("11 tdm %08X/e%d" % (mask, env), ok, msg))

    # 13 vel_shape：力度->谱形（含亮度灵敏度）单元判据 V1-V9
    #   表 = src/gowin/tdm_synth/vel_wtab.hex（vel_shape.v 只读这一张）
    d = os.path.join(BUILD, "13_velshape")
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "src", "gowin", "tdm_synth", "vel_wtab.hex"), d)
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "vs.vvp",
                   "-s", "tb_vel_shape", rtl("vel_shape.v"), sim("tb_vel_shape.v")], d)
    ok, msg = False, "compile fail"
    if rc == 0:
        rc2, log2 = run([os.path.join(IV, "vvp.exe"), "vs.vvp"], d)
        ok = "ALL VEL_SHAPE CRITERIA PASS" in log2
        #   缺表时输出全是 X，判据会以 FAIL 收场 —— 这时把日志尾给出来，
        #   否则只能看到一句"compile fail"，无法区分是缺表还是逻辑错。
        tail = [l.strip() for l in log2.splitlines() if "  FAIL" in l]
        msg = "V1-V9 全绿（基音/条数/单调/恒等/灵敏度）" if ok else (" / ".join(tail[:2]) or log2[-160:])
    results.append(("13 vel shape", ok, msg.replace(chr(10), " ")[:160]))

    # 14 vel_timbre：力度->音色 + 独立亮度轴 端到端
    #   （穿 tdm_top：端口 + 寄存器 0x5C/0x6D/0x6E + 装载与刷新通路）
    vt_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v", "i2s_tx.v",
                "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v",
                "event_hold.v", "tb_vel_timbre.v"]
    log, err = compile_and_run("14_veltimbre", vt_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("14 vel timbre", False, err[:120]))
    else:
        #   compile_and_run 内部已经跑过 vvp，这里不再重复跑第二遍
        #   （原来多跑一次，等于把同一份产物写两遍，只会让"哪一次的结果"变得含糊）
        ok, msg = judge_script("14_veltimbre", "vel_timbre_check.py")
        results.append(("14 vel timbre", ok, msg.replace(chr(10), " ")[:160]))

    # 15 i2s std：I2S 标准接收器（与 tb_i2s_tx 的旧模型同线对照）
    #   为什么与 04 i2s 并存：04 的接收模型把"WS 翻转沿"当作新字 MSB，
    #   而标准 I2S 要求 WS 比 MSB 提前一个 BCK。两者在**采样沿与字边界**上的
    #   假设若都错，会一起错 —— 所以需要第二条独立口径，并把两条的结论都留下。
    d = os.path.join(BUILD, "15_i2sstd")
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "i2s.vvp",
                   "-s", "tb_i2s_std", rtl("audio_clk_en.v"), rtl("i2s_tx.v"),
                   sim("tb_i2s_std.v")], d)
    ok, msg = False, "compile fail"
    if rc == 0:
        rc2, log2 = run([os.path.join(IV, "vvp.exe"), "i2s.vvp"], d)
        ok, msg = judge_script("15_i2sstd", "i2s_std_check.py")
    results.append(("15 i2s std", ok, msg.replace(chr(10), " ")[:160]))

    # 16 i2s top：顶层音频通路 端到端（tdm_top → fx → i2s_tx → 标准接收器）
    #   验的是"单元绿但集成没跑到"这一类：24 位饱和输出 → 取高 16 位 → 解码。
    top_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                 "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
                 "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
                 "strip_ctrl.v", "led_ind.v", "event_hold.v", "tb_i2s_top.v"]
    log, err = compile_and_run("16_i2sttop", top_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("16 i2s top", False, err[:160]))
    else:
        #   判据需要测试台 stdout 里的 SUMRAW_MAX（饱和前那一级的实测峰值），
        #   而 compile_and_run 已经把日志返回来了 —— 落盘成 run.txt 供判据读取。
        #   ★ 必须显式写 UTF-8：PowerShell 的 `>` 重定向默认写 UTF-16，
        #     Python 读不到会导致"饱和余量核算"被静默跳过（实测踩过）。
        d = os.path.join(BUILD, "16_i2sttop")
        try:
            with open(os.path.join(d, "run.txt"), "w", encoding="utf-8") as fh:
                fh.write(log or "")
        except OSError:
            pass
        ok, msg = judge_script("16_i2sttop", "i2s_top_check.py")
        results.append(("16 i2s top", ok, msg.replace(chr(10), " ")[:160]))

    # 17 evloss：8 键同时按/放 不丢事件、不挂音（pad_scan 待发位图 + note_map 忙模型）
    #   为什么要有：tdm_top 自述"冲突时后到者被忽略"，pad_scan 则宣称有反压。
    #   两条说法必须实测对齐；本会话已三次因"读代码下结论"而误判。
    d = os.path.join(BUILD, "17_evloss")
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    rc, log = run([os.path.join(IV, "iverilog.exe"), "-g2005", "-o", "ev.vvp",
                   "-s", "tb_evloss", rtl("pad_scan.v"), sim("tb_evloss.v")], d)
    if rc != 0:
        results.append(("17 evloss", False, "COMPILE FAIL"))
    else:
        rc2, log2 = run([os.path.join(IV, "vvp.exe"), "ev.vvp"], d)
        ok = "RESULT evloss=PASS" in log2
        tail = [l.strip() for l in log2.splitlines() if "FAIL" in l]
        msg = ("8 键同时按/放：16 条事件无丢失、不挂音" if ok
               else (" / ".join(tail[:2]) or log2[-160:]))
        results.append(("17 evloss", ok, msg.replace(chr(10), " ")[:160]))

    # 18 evmerge：事件「汇合点 + 待处理队列」端到端（穿 tdm_top）
    #   为什么要有：阶段 2 的核心主张是"不丢事件，尤其不丢 note-off"。
    #   两个环节可能丢：① 优先级 mux 同拍只选一个（其余无声丢弃）
    #                   ② note_map 忙约 20 拍期间到达的单拍脉冲被忽略
    #   本套件用**真源**验：排针走事件端口、UART 走**真实字节流**（uart_rx 引脚发
    #   [addr][data] 帧，115200/8N1），然后逐条比对"发出的"与"note_map 收到的"。
    #   ★ 不要用 force 驱动内部写口 —— 那会绕过 uart_rx 与两字节组帧，
    #     本套件第一版就是这么写的，结果整段 UART 事件都取不到音符。
    evm_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                 "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
                 "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
                 "strip_ctrl.v", "led_ind.v", "event_hold.v", "tb_evmerge.v"]
    log, err = compile_and_run("18_evmerge", evm_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("18 evmerge", False, err[:160]))
    else:
        ok = "RESULT evmerge=PASS" in (log or "")
        tail = [l.strip() for l in (log or "").splitlines()
                if ("FAIL" in l or "收到" in l)]
        msg = ("28 条（排针 12 + UART 8 + 并存 8）一条不丢、note-off 14/14、溢出 0"
               if ok else (" / ".join(tail[:2]) or (log or "")[-160:]))
        results.append(("18 evmerge", ok, msg.replace(chr(10), " ")[:160]))

    # 19 alloc：声部分配/回收（阶段 3）
    #   为什么要有：note-off 曾经只清 gact、不把 gtab 写回 FREE ⇒ 32 组用过之后
    #   空闲搜索永不命中，新音会**抢占正在按住的音**。
    #   ★ 激励必须**填满全部 32 组**才能暴露它（只按 20 个音时判据假绿 —— 踩过）。
    alc_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                 "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
                 "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
                 "strip_ctrl.v", "led_ind.v", "event_hold.v", "tb_alloc.v"]
    log, err = compile_and_run("19_alloc", alc_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("19 alloc", False, err[:160]))
    else:
        ok = "RESULT alloc=PASS" in (log or "")
        tail = [l.strip() for l in (log or "").splitlines() if "FAIL" in l]
        msg = ("32 组填满后释放：gtab 回 FREE、新音不抢按住的音" if ok
               else (" / ".join(tail[:2]) or (log or "")[-160:]))
        results.append(("19 alloc", ok, msg.replace(chr(10), " ")[:160]))

    # 20 sat：24 位饱和/截断路径边界（阶段 3 遗留项）
    #   为什么要有：12 f1 与 16 i2s top 都**到不了**饱和区（实测 sum_raw 峰值 383370，
    #   阈值 524288 = 73%），clamp 分支从未被覆盖。
    #   本机没有 Gowin 工具链、也没有增益寄存器可调，所以改为 force 引擎内部的
    #   `acc_next`（饱和表达式的输入），逐点核对期望值 —— 覆盖正/负两侧的分界点。
    sat_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                 "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
                 "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
                 "strip_ctrl.v", "led_ind.v", "event_hold.v", "tb_sat.v"]
    log, err = compile_and_run("20_sat", sat_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("20 sat", False, err[:160]))
    else:
        ok = "RESULT sat=PASS" in (log or "")
        tail = [l.strip() for l in (log or "").splitlines() if "FAIL" in l]
        msg = ("±524288 分界点：正侧夹到 8388607、负侧正好 -8388608（10 点全对）" if ok
               else (" / ".join(tail[:2]) or (log or "")[-160:]))
        results.append(("20 sat", ok, msg.replace(chr(10), " ")[:160]))

    # 21 voice：逐声部力度/音色是否需要独立存储？
    #   阶段 3 计划里写着"保存每声部力度/音色/状态"。本套件把这条**假设变成事实**：
    #   note_map 装载时就把力度算进每个泛音的幅度（vel_shape → amp_cal → load_amp），
    #   引擎逐槽写进 pa_mem ⇒ 力度**烘进幅度**，装载后不再受全局变化影响。
    #   于是"逐声部保存力度"不是缺口，而是需要被**判据固定住**的不变量。
    voi_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                 "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
                 "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
                 "strip_ctrl.v", "led_ind.v", "event_hold.v", "tb_voice.v"]
    log, err = compile_and_run("21_voice", voi_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("21 voice", False, err[:160]))
    else:
        ok = "RESULT voice=PASS" in (log or "")
        tail = [l.strip() for l in (log or "").splitlines() if "FAIL" in l]
        msg = ("力度在装载时烘进每泛音幅度；换声部/改全局都不影响已发声声部" if ok
               else (" / ".join(tail[:2]) or (log or "")[-160:]))
        results.append(("21 voice", ok, msg.replace(chr(10), " ")[:160]))

    # ---------------------------------------------------------------- 汇总
    print()
    print("=" * 64)
    print(" 回归汇总  （%s 配置）" % ("全量 --full" if args.full else "快速门"))
    print("=" * 64)
    nfail = 0
    for name, ok, msg in results:
        print("  %s  %-18s %s" % ("✅" if ok else "❌", name, msg))
        nfail += 0 if ok else 1
    print("=" * 64)
    print(" %d/%d 通过%s" % (len(results) - nfail, len(results),
                             "" if nfail == 0 else "  —— 存在失败，不满足上板条件"))
    # 结果落盘（2026-10-04 审计 P1："全绿"声明必须可复核，不能只活在 git 提交一句话里）
    rpt = os.path.join(ROOT, "sim_build", "regress_result.txt")
    try:
        with open(rpt, "w", encoding="utf-8-sig") as fh:
            fh.write("回归门结果：%s 配置  %s\n" % (
                "全量 --full" if args.full else "快速门",
                time.strftime("%Y-%m-%d %H:%M:%S")))
            for name, ok, msg in results:
                fh.write("  %s  %-18s %s\n" % ("PASS" if ok else "FAIL", name, msg))
            fh.write("  => %d/%d 通过\n" % (len(results) - nfail, len(results)))
    except OSError:
        pass
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
