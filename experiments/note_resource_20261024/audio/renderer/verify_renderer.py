from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess

from reference import generate

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
CAPTURED = PROJECT / 'fpga/current/engine/src'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbers(path):
    return [int(word, 16) for word in path.read_text(encoding='utf-8').split()]


def mutate(source, fault, filename='note_partial_renderer.v'):
    if fault == 'legacy-width':
        if filename != 'vel_shape_scaled.v':
            return source
        changes = [("wire signed [9:0]  dw_sc   = dw_mul[17:8];", "wire signed [8:0]  dw_sc   = dw_mul[16:8];"),
                   ("wire signed [10:0] w_sum   = dw_sc + 11'sd256;", "wire signed [9:0]  w_sum   = dw_sc + 10'sd256;"),
                   ("w_sum[10] == 1'b1", "w_sum[9] == 1'b1"),
                   ("w_sum > $signed(11'sd511)", "w_sum > $signed(10'sd511)")]
        for before, after in changes:
            if source.count(before) != 1:
                raise ValueError('Legacy width anchor changed')
            source = source.replace(before, after)
        return source
    if filename != 'note_partial_renderer.v':
        return source
    changes = {
        'wrong-slot': ('.slot(layer_hold)', ".slot(2'd0)"),
        'velocity-off': ('.vscale(scale_hold)', ".vscale(9'd0)"),
        'live-tilt': ('tilt_rom[{tilt_hold[7:4],index_hold}]', 'tilt_rom[{tilt[7:4],index_hold}]')
    }
    if fault not in changes:
        return source
    before, after = changes[fault]
    if source.count(before) != 1:
        raise ValueError('Changed mutation anchor: ' + fault)
    return source.replace(before, after)


def compare(expected, path):
    observed = []
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            words = line.split()
            if len(words) != 11 or words[0] != 'R':
                return dict(field='malformed-trace', line=line)
            try:
                observed.append([int(words[1])] + [int(word, 16) for word in words[2:]])
            except ValueError:
                return dict(field='unknown-trace', line=line)
    for index, row in enumerate(expected):
        if index >= len(observed):
            return dict(field='query-count', expected=len(expected), observed=len(observed))
        for field, before, after in zip(('query','token','ticket','layer','partial','inc','amp','epar','env','glide'), row, observed[index]):
            if before != after:
                return dict(query=index, field=field, expected=before, observed=after)
    return None if len(observed) == len(expected) else dict(field='query-count', expected=len(expected), observed=len(observed))


def run(command, output, cwd, timeout=300):
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        raw, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, code = (error.stdout or b'') + b'\nTIMEOUT\n', 124
    output.write_bytes(raw)
    return dict(command=command, returncode=code, text=raw.decode('utf-8', errors='replace'), log_sha256=digest(output))


def main():
    parser = argparse.ArgumentParser(description='Independent integer oracle for real four-slot note partial renderer')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside repository')
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    if not compiler.is_file() or not simulator.is_file():
        raise ValueError('Icarus and vvp required')
    sources = [ROOT / 'rtl/note_partial_renderer.v', ROOT / 'rtl/vel_shape_scaled.v', ROOT / 'tb/tb_partial_renderer.v', ROOT / 'reference.py', ROOT / 'verify_renderer.py']
    sources += [CAPTURED / name for name in ('instrument_table.v','vel_shape.v','note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    inputs = {path.relative_to(PROJECT).as_posix():digest(path) for path in sources}
    output.mkdir(parents=True)
    (output / 'INPUTS.json').write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf-8')
    notes, presets, tilts, captured_weights = [numbers(CAPTURED / name) for name in ('note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    reports = []
    for case in ['captured', 'distinct-slots'] + (['wrong-slot','velocity-off','live-tilt','legacy-width'] if arguments.fault_checks else []):
        print('RUN ' + case, flush=True)
        directory = output / case
        directory.mkdir()
        weights = captured_weights[:]
        if case in ('distinct-slots','wrong-slot'):
            address = 256 + 5 * 16 + 7
            weights[address] = 64 if (weights[address] & 511) != 64 else 192
        for name in ('note_inc.hex','preset_part.hex','tilt_wtab.hex'):
            shutil.copyfile(CAPTURED / name, directory / name)
        (directory / 'vel_wtab.hex').write_bytes((''.join('%03x\n' % weight for weight in weights)).encode())
        commands, expected, coverage = generate(notes, presets, tilts, weights)
        (directory / 'commands.txt').write_bytes(('\n'.join(commands) + '\n').encode())
        (directory / 'expected.json').write_text(json.dumps(expected) + '\n', encoding='utf-8')
        rtl = directory / 'note_partial_renderer.v'
        rtl.write_bytes(mutate((ROOT / 'rtl/note_partial_renderer.v').read_text(encoding='utf-8'), case).encode())
        velocity_rtl = directory / 'vel_shape_scaled.v'
        velocity_rtl.write_bytes(mutate((ROOT / 'rtl/vel_shape_scaled.v').read_text(encoding='utf-8'), case, 'vel_shape_scaled.v').encode())
        binary = directory / 'renderer.vvp'
        compilation = run([str(compiler),'-g2012','-s','tb_partial_renderer','-o',str(binary),str(rtl),str(velocity_rtl),str(ROOT / 'tb/tb_partial_renderer.v'),
                           str(CAPTURED / 'instrument_table.v'),str(CAPTURED / 'vel_shape.v')], directory / 'compile.log', directory)
        report = dict(case=case, compilation=compilation, passed=False, coverage=coverage,
                      generated_source_sha256=digest(rtl), generated_velocity_sha256=digest(velocity_rtl), weights_sha256=digest(directory / 'vel_wtab.hex'),
                      commands_sha256=digest(directory / 'commands.txt'), expected_sha256=digest(directory / 'expected.json'))
        if compilation['returncode'] == 0:
            trace = directory / 'trace.tsv'
            simulation = run([str(simulator),str(binary),'+commands='+(directory / 'commands.txt').as_posix(),'+trace='+trace.as_posix()], directory / 'run.log', directory)
            difference = compare(expected, trace)
            report.update(simulation=simulation, first_difference=difference)
            if case in ('captured','distinct-slots'):
                report['passed'] = simulation['returncode'] == 0 and 'PASS partial_renderer' in simulation['text'] and difference is None
            else:
                report['passed'] = simulation['returncode'] == 0 and 'PASS partial_renderer' in simulation['text'] and difference is not None and difference['field'] == 'amp'
            if trace.is_file():
                report['trace_sha256'] = digest(trace)
                (directory / 'trace.tsv.gz').write_bytes(gzip.compress(trace.read_bytes(), mtime=0))
        reports.append(report)
        print(case + ': ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
        (output / 'progress.json').write_text(json.dumps(dict(results=reports), indent=2) + '\n', encoding='utf-8')
    changed = [name for name, value in inputs.items() if digest(PROJECT / name) != value]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs, source_changes=changed, results=reports,
        tools={str(path):digest(path) for path in (compiler, simulator)}, status='PASS' if all(report['passed'] for report in reports) and not changed else 'FAIL',
        scope='Real partial payload generation and configuration/context isolation; no full PCM, input routing or timing/hardware acceptance', product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], output=str(output))))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
