from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'audio/renderer'))
from reference import render

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
RENDERER = ROOT.parent / 'audio/renderer'
CAPTURED = PROJECT / 'fpga/current/engine/src'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbers(name):
    return [int(word,16) for word in (CAPTURED / name).read_text(encoding='utf-8').split()]


def run(command, output, cwd, timeout=600):
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        raw, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, code = (error.stdout or b'') + b'\nTIMEOUT\n', 124
    output.write_bytes(raw)
    return dict(command=command, returncode=code, text=raw.decode('utf-8', errors='replace'), log_sha256=digest(output))


def inspect_trace(path):
    notes, presets, tilts, weights = [numbers(name) for name in ('note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    context = None
    loads, frames, on_events = 0, 0, 0
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if fields[0] == 'N':
            token = int(fields[1],16)
            context = dict(token=token, note=int(fields[2]), velocity=int(fields[3]), slow=bool(int(fields[4])),
                tilt=0x70, scale=256, pad=0, spectrum=[0]*16, replace=0, artic=0, artic_mask=0, glide=0)
            on_events += 1
        elif fields[0] == 'L':
            values = [int(value,16) for value in fields[1:]]
            if context is None or values[0] != context['token']:
                return dict(field='load-context', observed=values), dict(loads=loads,frames=frames,on_events=on_events)
            token, layer, partial = values[:3]
            envelope = (1 << 35) | (4096 << 15) | (3 << 5) | (13 if context['slow'] else 3)
            definition = (envelope << 48) | (presets[layer*16+partial] & ~((1<<24)-1)) | (20000<<7) | (3<<5) | 12
            expected = render(context, layer, partial, definition, True, notes, tilts, weights)
            if values[3:] != expected:
                return dict(field='rendered-load', load=loads, token=token, layer=layer, partial=partial, expected=expected, observed=values[3:]), dict(loads=loads,frames=frames,on_events=on_events)
            loads += 1
        elif fields[0] == 'P':
            frames += 1
        elif fields[0] != 'R':
            return dict(field='malformed-record',line=line), dict(loads=loads,frames=frames,on_events=on_events)
    return None, dict(loads=loads,frames=frames,on_events=on_events)


def main():
    parser = argparse.ArgumentParser(description='Real note/config renderer -> resource manager -> TDM/envelope chain; no external partial provider')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fault-check', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == PROJECT or PROJECT in output.parents:
        raise ValueError('Use a fresh output outside repository')
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    if not compiler.is_file() or not simulator.is_file():
        raise ValueError('Icarus/vvp required')
    sources = [ROOT / 'rtl/note_event_router.v', ROOT / 'rtl/note_duet_probe.v'] + sorted((RENDERER / 'rtl').glob('*.v')) + sorted((ROOT.parent / 'audio/rtl').glob('*.v'))
    sources += [ROOT.parent / 'rtl/note_resource_mgr.v', ROOT / 'tb/tb_duet_audio.v']
    sources += [CAPTURED / name for name in ('osc_env.v','pitch_mod.v','pitch_native_store.v','vel_shape.v','instrument_table.v')]
    sources += [PROJECT / 'fpga/current/tb/vendor_ram16sdp4.v']
    tables = [CAPTURED / name for name in ('sine256.hex','note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    tracked = sources + tables + [RENDERER / 'reference.py', ROOT / 'verify_audio.py']
    inputs = {path.relative_to(PROJECT).as_posix():digest(path) for path in tracked}
    output.mkdir(parents=True)
    (output / 'INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf-8')
    top = ROOT / 'rtl/note_duet_probe.v'
    generated = (output / 'note_duet_probe.v')
    text = top.read_text(encoding='utf-8')
    if arguments.fault_check:
        before = 'wire core_cancel_valid=cancel_valid||cancel_pending;'
        if text.count(before) != 1:
            raise ValueError('Queued cancellation mutation anchor changed')
        text = text.replace(before, 'wire core_cancel_valid=cancel_valid;')
    generated.write_bytes(text.encode())
    sources = [generated if source == top else source for source in sources]
    for table in tables:
        shutil.copyfile(table, output / table.name)
    binary = output / 'instrument.vvp'
    compilation = run([str(compiler),'-g2012','-s','tb_duet_audio','-o',str(binary)] + [str(path) for path in sources], output / 'compile.log', output)
    passed, simulation, difference, coverage = False, None, None, {}
    if compilation['returncode'] == 0:
        trace = output / 'trace.tsv'
        simulation = run([str(simulator),str(binary),'+trace='+trace.as_posix()], output / 'run.log', output)
        if trace.is_file():
            difference, coverage = inspect_trace(trace)
            (output / 'trace.tsv.gz').write_bytes(gzip.compress(trace.read_bytes(),mtime=0))
        passed = simulation['returncode'] == 0 and 'PASS rendered_audio' in simulation['text'] and difference is None and coverage.get('loads',0) > 4000
        if arguments.fault_check:
            passed = simulation['returncode'] != 0 and 'queued cancellation was dropped' in simulation['text'] and not any(marker in simulation['text'] for marker in ('TIMEOUT','response timeout','global timeout'))
    changed = [name for name, expected in inputs.items() if digest(PROJECT / name) != expected]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs, tools={str(path):digest(path) for path in (compiler,simulator)},
        compilation=compilation, simulation=simulation, first_difference=difference, coverage=coverage, source_changes=changed,
        trace_sha256=digest(output / 'trace.tsv') if (output / 'trace.tsv').is_file() else None,
        fault='queued-cancel' if arguments.fault_check else None, generated_top_sha256=digest(generated),
        status='PASS' if passed and not changed else 'FAIL',
        scope='Two tagged ready/valid logical sources and matched response routing into real hardware partial generation, runtime custom slot definitions and note-resource/TDM PCM chain. Synthetic note/config events; no physical scan, score file, auto-release scheduler, full independent PCM oracle or timing/board acceptance.',
        product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],coverage=coverage,output=str(output))))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
