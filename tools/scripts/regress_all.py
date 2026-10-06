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


def compile_and_run(name, files, defines=(), plusargs=(), need_hex=False, extra_hex=()):
    """在 sim_build/regress/<name>/ 里编译并运行一个测试台，返回 stdout"""
    d = os.path.join(BUILD, name)
    # 每次清空运行目录：判据脚本读目录下的产物文件，残留旧代产物会污染判据
    #   （遇锁重试机制见 rmtree_ok 的注释，2026-10-03 遇 PermissionError 教训）
    if os.path.isdir(d):
        rmtree_ok(d)
    os.makedirs(d, exist_ok=True)
    if need_hex:
        shutil.copy(sine_hex(), d)
        # vel_shape 的权重表：与 sine256 同类的运行期依赖，一起拷
        _wt = os.path.join(ROOT, "src", "gowin", "tdm_synth", "vel_wtab.hex")
        if os.path.isfile(_wt):
            shutil.copy(_wt, d)
    for h in extra_hex:
        shutil.copy(h, d)
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
    shutil.copy(sine_hex(), d)
    _wt = os.path.join(ROOT, "src", "gowin", "tdm_synth", "vel_wtab.hex")
    if os.path.isfile(_wt):
        shutil.copy(_wt, d)
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
             "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v", "tb_reg_ctl.v"]
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
                 "fx_delay.v", "song_seq.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v", "tdm_top.v", "tb_vp7.v"]
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
        synth_hex = os.path.join(ROOT, "src", "gowin", "tdm_synth")
        for h in ("sine256.hex", "note_inc.hex", "preset_part.hex", "recip_inc.hex"):
            shutil.copy(os.path.join(synth_hex, h), d)
        f1_files = ["audio_clk_en.v", "osc_env.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                    "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v",
                    "fx_delay.v", "i2s_tx.v", "tdm_engine.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v",
                    "tdm_top.v", "tb_tdm_f1.v"]
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

    # 13 vel_shape：力度->谱形 单元判据（V1-V8；表 = src/gowin/tdm_synth/vel_wtab.hex）
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
        tail = [l.strip() for l in log2.splitlines() if "  FAIL" in l]
        msg = "V1-V8 全绿（基音/条数/单调/恒等）" if ok else (" / ".join(tail[:2]) or log2[-120:])
    results.append(("13 vel shape", ok, msg.replace(chr(10), " ")[:120]))

    # 14 vel_timbre：力度->音色 端到端（穿 tdm_top：端口 + 寄存器 0x6B-0x6D + 装载通路）
    vt_files = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
                "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v", "i2s_tx.v",
                "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v", "strip_ctrl.v", "led_ind.v",
                "tb_vel_timbre.v"]
    log, err = compile_and_run("14_veltimbre", vt_files, defines=("SIM_INIT",), need_hex=True)
    if err:
        results.append(("14 vel timbre", False, err[:120]))
    else:
        d = os.path.join(BUILD, "14_veltimbre")
        run([os.path.join(IV, "vvp.exe"), "sim.vvp"], d)
        ok, msg = judge_script("14_veltimbre", "vel_timbre_check.py")
        results.append(("14 vel timbre", ok, msg.replace(chr(10), " ")[:120]))

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
