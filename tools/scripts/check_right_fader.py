"""Compile and run the standalone candidate kernel; no touch/Part integration."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
iv = os.environ.get("FPGA_MUSIC_IVERILOG") or shutil.which("iverilog") or r"D:\iverilog\bin\iverilog.exe"
vvp = str(Path(iv).parent / "vvp.exe") if os.name == "nt" else (shutil.which("vvp") or "vvp")
out = root / "sim_build/right_fader"
out.mkdir(parents=True, exist_ok=True)
compile_run = subprocess.run([iv, "-g2012", "-s", "tb_right_fader_follow", "-o", str(out / "test.vvp"),
                             str(root / "src/rtl/right_fader_follow.v"), str(root / "src/sim/tb_right_fader_follow.v")], capture_output=True)
if compile_run.returncode:
    print(compile_run.stderr.decode(errors="replace"))
    sys.exit(1)
result = subprocess.run([vvp, str(out / "test.vvp")], capture_output=True)
log = result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
(out / "result.txt").write_text(log, encoding="utf-8")
print(log.strip())
sys.exit(0 if result.returncode == 0 and "RESULT right_fader_follow PASS fails=0" in log else 1)
