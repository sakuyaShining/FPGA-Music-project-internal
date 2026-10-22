"""Read a pinned product candidate; run existing tests in a separate audit directory.

These characterize existing mechanisms. PASS is not acceptance of the new product.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def words(path):
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        result.extend(int(x, 16) for x in line.split("//")[0].split())
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rtl, sim, tables = repo / "src/rtl", repo / "src/sim", repo / "src/gowin/tdm_synth"
    report = {
        "purpose": "Existing mechanism audit, not acceptance of custom instruments/layers",
        "repo": str(repo),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "manifest": "project/versions/integration-20261011-07.json",
        "manifest_sha256": sha(repo / "project/versions/integration-20261011-07.json"),
        "source_sha256": {},
        "tests": [],
    }
    for p in list(rtl.glob("*.v")) + list(tables.glob("*.hex")):
        report["source_sha256"][str(p.relative_to(repo))] = sha(p)
    fs = 27000000 / 512
    preset = words(tables / "preset_part.hex")
    increments = words(tables / "note_inc.hex")
    assert len(preset) == 64 and len(increments) == 128
    wrap = []
    for pi in range(4):
        for k in range(16):
            item = preset[pi * 16 + k]
            ratio, amp = item >> 32, (item >> 24) & 255
            if not amp:
                continue
            for note, inc in enumerate(increments):
                full = inc * ratio >> 8
                truncated = full & ((1 << 24) - 1)
                if full >= (1 << 23) and truncated < (1 << 23):
                    wrap.append({"preset": pi, "partial": k + 1, "note": note,
                                 "ratio": ratio / 256,
                                 "frequency_hz": full * fs / (1 << 24),
                                 "wrapped_hz": truncated * fs / (1 << 24)})
    report["numeric"] = {
        "fs_hz": fs,
        "phase_increment_resolution_hz": fs / (1 << 24),
        "fixed_attack_samples_ceil": math.ceil(32768 / 117),
        "fixed_attack_ramp_ms": math.ceil(32768 / 117) / fs * 1000,
        "sustain_levels_by_preset": [
            sorted(set((w & ((1 << 23) - 1)) >> 7 for w in preset[i*16:(i+1)*16]))
            for i in range(4)],
        "truncation_then_nyquist_audit": {
            "classification": "Static RTL-equivalent arithmetic risk, not measured audio",
            "all_midi_nonzero_amp_count": len(wrap),
            "midi36_to108_count": sum(36 <= row["note"] <= 108 for row in wrap),
            "first_examples": wrap[:6],
        },
        "pitch_octave_crossing_example": {
            "note": 90, "partial": 16,
            "base_hz": (increments[90] * 16) * fs / (1 << 24),
            "after_plus_octave_hz": (increments[90] * 32) * fs / (1 << 24),
            "nyquist_hz": fs / 2,
        },
    }
    suites = [
        ("envelope", "tb_osc_env", ["osc_env"], "[PASS]"),
        ("finger_pitch", "tb_finger_pitch", ["finger_pitch"], "PASS finger_pitch:"),
        ("release_continuity", "tb_release_continuity",
         ["tdm_engine", "osc_env", "pitch_mod"], "RESULT release_continuity=PASS"),
    ]
    bindir = Path("D:/iverilog/bin")
    for name, top, modules, marker in suites:
        work = out / name
        work.mkdir()
        for p in tables.glob("*.hex"):
            shutil.copyfile(p, work / p.name)
        testfile = sim / (top + ".v")
        report["source_sha256"][str(testfile.relative_to(repo))] = sha(testfile)
        compile_result = subprocess.run(
            [str(bindir / "iverilog.exe"), "-g2012", "-DSIM_INIT", "-s", top,
             "-o", str(work / "test.vvp")]
            + [str(rtl / (m + ".v")) for m in modules] + [str(testfile)],
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        (work / "compile.log").write_text(compile_result.stdout + compile_result.stderr, encoding="utf-8")
        result = None
        if compile_result.returncode == 0:
            result = subprocess.run([str(bindir / "vvp.exe"), str(work / "test.vvp")],
                                    cwd=work, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=180)
            (work / "run.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        passed = bool(result and result.returncode == 0 and marker in result.stdout)
        report["tests"].append({"name": name, "compile_exit": compile_result.returncode,
                                "run_exit": None if result is None else result.returncode,
                                "existing_mechanism_pass": passed})
        print(name + ": " + ("PASS existing mechanism" if passed else "FAIL"), flush=True)
    unchanged = all(sha(repo / name) == digest for name, digest in report["source_sha256"].items())
    report["source_unchanged_during_audit"] = unchanged
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["numeric"], ensure_ascii=False, indent=2), flush=True)
    return 0 if unchanged and all(t["existing_mechanism_pass"] for t in report["tests"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
