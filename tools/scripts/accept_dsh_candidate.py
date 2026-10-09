"""Read-only candidate checks in a git-archive snapshot, without touching DSH's checkout."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    output = root.parent
    spec = importlib.util.spec_from_file_location("candidate_gate", root / "tools/scripts/regress_all.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    integration = len(sys.argv) > 2
    label = "integration" if integration else "targeted"
    if integration:
        gate.RTL = str(Path(sys.argv[2]).resolve() / "src/rtl")
    gate.BUILD = str(root / ("sim_build/acceptance_" + label))
    Path(gate.BUILD).mkdir(parents=True, exist_ok=True)
    top = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
           "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
           "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
           "strip_ctrl.v", "led_ind.v", "event_hold.v"]
    results = []
    for name in ("evmerge", "alloc", "sat", "voice", "legato", "inv", "glide", "vib", "i2c_master"):
        if integration and name == "i2c_master":
            continue  # Current I2C revision has its own updated model and test contract.
        files = (["pitch_mod.v"] if name in ("glide", "vib") else
                 ["i2c_master.v", str(root / "src/sim/mpr121_model.v")] if name == "i2c_master" else top)
        log, err = gate.compile_and_run("audit_" + name, files + ["tb_" + name + ".v"],
                                       defines=("SIM_INIT",), need_hex=name not in ("glide", "vib", "i2c_master"))
        log = (err or "") + (log or "")
        (output / (label + "_" + name + ".log")).write_text(log, encoding="utf-8")
        marker = "RESULT " + name + "=PASS"
        ok = not err and (marker in log if name != "i2c_master" else "FAIL" not in log and "PASS" in log)
        results.append({"test": name, "pass": ok, "compile_error": err})
        print(name, "PASS" if ok else "FAIL", flush=True)
    if integration:
        (output / "integration_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if all(r["pass"] for r in results) else 1
    command = [sys.executable, str(root / "tools/scripts/spec_sha_check.py")]
    proc = subprocess.run(command, cwd=root, capture_output=True, encoding="utf-8", errors="replace")
    (output / "spec_sha.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    results.append({"test": "spec_sha", "pass": proc.returncode == 0, "exit": proc.returncode})
    # Removing the data-table manifest must not silently turn a full binding into partial validation.
    import re
    doc = next((root / "docs").rglob("34-*.md"))
    partial = re.sub(r"`([\w_]+\.hex)\s+([0-9a-f]{12})`", "(removed for negative test)", doc.read_text(encoding="utf-8"))
    bad_doc = output / "partial_manifest.md"
    bad_doc.write_text(partial, encoding="utf-8")
    proc = subprocess.run(command + ["--doc", str(bad_doc)], cwd=root, capture_output=True, encoding="utf-8", errors="replace")
    (output / "spec_sha_negative.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    results.append({"test": "spec_sha_missing_tables_rejected", "pass": proc.returncode != 0, "exit": proc.returncode})
    (output / "targeted_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
