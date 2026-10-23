from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Isolated resource-manager synthesis only; no PnR, constraints, bitstream or programmer')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        raise ValueError('Use a new output outside the experiment')
    executable = Path(os.environ.get('FPGA_GOWIN_GW_SH',
        'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'))
    if not executable.is_file():
        raise ValueError('Missing Gowin shell; set FPGA_GOWIN_GW_SH')
    output.mkdir(parents=True)
    source = ROOT / 'rtl/note_resource_mgr.v'
    before = digest(source)
    shutil.copyfile(source, output / source.name)
    project = output / 'resource.gprj'
    project.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
        '<Template>FPGA</Template><Version>5</Version>'
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>'
        '<FileList><File path="note_resource_mgr.v" type="file.verilog" enable="1"/></FileList></Project>', encoding='utf-8')
    script = output / 'synthesize.tcl'
    script.write_text('open_project "' + project.as_posix() + '"\nset_option -top_module note_resource_mgr\nrun syn\nexit\n', encoding='utf-8')
    start = time.monotonic()
    with (output / 'console.log').open('wb') as console:
        process = subprocess.Popen([str(executable), str(script)], cwd=output, stdout=console, stderr=subprocess.STDOUT)
        print('GOWIN PID ' + str(process.pid), flush=True)
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.wait()
            code = 124
    log = (output / 'console.log').read_text(encoding='utf-8', errors='replace')
    html = output / 'impl/gwsynthesis/resource_syn_resource.html'
    passed = code == 0 and html.exists() and not re.search(r'\bERROR\s*\(', log) and digest(source) == before
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), returncode=code,
        elapsed_seconds=round(time.monotonic()-start, 2), source_sha256=before,
        console_sha256=digest(output / 'console.log'), tool=dict(path=str(executable), sha256=digest(executable)),
        status='PASS_SYNTHESIS_ONLY' if passed else 'FAIL', report=str(html),
        report_sha256=digest(html) if html.exists() else None, warnings=re.findall(r'WARNING[^\r\n]*', log),
        scope='Standalone coordinator area; no clock/pin timing constraints or complete music top. No PnR/STA/bitstream/device acceptance.',
        product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
