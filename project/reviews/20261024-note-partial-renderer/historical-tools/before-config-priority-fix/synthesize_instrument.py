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
PROJECT = ROOT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Four-slot note renderer plus resource/TDM synthesis only; not a complete device board top')
    parser.add_argument('--output', required=True, type=Path)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside repository')
    executable = Path(os.environ.get('FPGA_GOWIN_GW_SH',
        'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'))
    if not executable.is_file():
        raise ValueError('Missing Gowin shell')
    sources = sorted((ROOT / 'rtl').glob('*.v')) + sorted((ROOT.parent / 'rtl').glob('*.v'))
    sources += [ROOT.parent.parent / 'rtl/note_resource_mgr.v']
    sources += [PROJECT / 'fpga/current/engine/src' / name for name in ('osc_env.v','pitch_mod.v','pitch_native_store.v','instrument_table.v','vel_shape.v','sine256.hex','note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    inputs = {source.relative_to(PROJECT).as_posix():digest(source) for source in sources}
    inputs[Path(__file__).resolve().relative_to(PROJECT).as_posix()] = digest(Path(__file__))
    output.mkdir(parents=True)
    entries = []
    for source in sources:
        shutil.copyfile(source, output / source.name)
        if source.suffix == '.v':
            entries.append('<File path="' + source.name + '" type="file.verilog" enable="1"/>')
    project = output / 'instrument.gprj'
    project.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
        '<Template>FPGA</Template><Version>5</Version>'
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>'
        '<FileList>' + ''.join(entries) + '</FileList></Project>', encoding='utf-8')
    script = output / 'synthesize.tcl'
    script.write_text('open_project "' + project.as_posix() + '"\nset_option -top_module note_resource_instrument_probe\nrun syn\nexit\n', encoding='utf-8')
    started = time.monotonic()
    with (output / 'console.log').open('wb') as console:
        process = subprocess.Popen([str(executable), str(script)], cwd=output, stdout=console, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print('GOWIN PID ' + str(process.pid), flush=True)
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.wait()
            code = 124
    report = output / 'impl/gwsynthesis/instrument_syn_resource.html'
    log = (output / 'console.log').read_text(encoding='utf-8', errors='replace')
    changed = [name for name, expected in inputs.items() if digest(PROJECT / name) != expected]
    passed = code == 0 and report.is_file() and not re.search(r'\bERROR\s*\(', log) and not changed
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=round(time.monotonic()-started, 2),
        inputs=inputs, tool=dict(path=str(executable), sha256=digest(executable)), returncode=code,
        report=str(report), report_sha256=digest(report) if report.is_file() else None,
        console_sha256=digest(output / 'console.log'), warnings=re.findall(r'WARNING[^\r\n]*', log), source_changes=changed,
        status='PASS_SYNTHESIS_ONLY' if passed else 'FAIL',
        scope='Four-slot runtime partial renderer and32-group transactional512-partial TDM/envelope core. Logical note/config inputs; no scan, score file, auto-release scheduler, complete peripherals, PnR/STA, bitstream or hardware.',
        product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], elapsed_seconds=result['elapsed_seconds'], output=str(output))))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
