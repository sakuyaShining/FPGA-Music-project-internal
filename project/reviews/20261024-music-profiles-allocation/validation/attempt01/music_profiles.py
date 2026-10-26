"""Run explicit historical/current music profiles on isolated engineering exports.

Profile success is not product, board, timing or musical-default acceptance.
"""
from pathlib import Path
from datetime import datetime, timezone
from itertools import zip_longest
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

import engineering


CASES = [('compat', 'tb_music', 'tb_compat_music.v', ['dut.core', 'ref_top']),
         ('layers', 'tb_layers', 'tb_layers.v', ['dut.core']),
         ('sensor', 'tb_sensor_layers', 'tb_sensor_layers.v', ['dut.music.core'])]
BENCHES = {case[2] for case in CASES}
DATA = 'handoff_support/resource_safety_20261016'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def read_hex(path, count, maximum):
    values = [int(word, 16) for line in path.read_text(encoding='utf-8').splitlines()
              for word in line.split('//', 1)[0].split()]
    if len(values) != count or any(value < 0 or value > maximum for value in values):
        raise ValueError('Invalid table size or value: ' + str(path))
    return values


def amplitude_reference(base, velocity, slot, partial, weights, tilts):
    if not (0 <= base <= 255 and 0 <= velocity <= 255 and 0 <= slot < 4 and 0 <= partial < 16):
        raise ValueError('Invalid amplitude reference input')
    tilt_weight = max(64, tilts[7 * 16 + partial])
    tilted = min(255, base * tilt_weight // 256)
    velocity_weight = weights[slot * 256 + (velocity // 16) * 16 + partial]
    if partial < 3:
        velocity_weight = max(64, velocity_weight)
    shaped = min(255, tilted * velocity_weight // 256)
    return shaped * velocity // 256


def expected_amplitudes(root):
    weights = read_hex(root / 'engine/src/vel_wtab.hex', 1024, 511)
    tilts = read_hex(root / 'engine/src/tilt_wtab.hex', 256, 511)
    sustain = read_hex(root / DATA / 'sustain.hex', 16, (1 << 48) - 1)
    strike = read_hex(root / DATA / 'strike.hex', 16, (1 << 48) - 1)
    definitions = [(0, [(word >> 24) & 255 for word in sustain]),
                   (1, [(word >> 24) & 255 for word in strike]),
                   (0, [40] + [partial * 3 for partial in range(1, 16)]),
                   (2, [120] + [partial * 3 for partial in range(1, 16)]),
                   (3, [60] + [partial * 3 for partial in range(1, 16)])]
    return [amplitude_reference(base, 192, slot, partial, weights, tilts)
            for slot, amplitudes in definitions for partial, base in enumerate(amplitudes)]


def replace_required(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Historical bench contract changed: ' + old)
    return text.replace(old, new)


def layer_reference_bench(text):
    text = replace_required(text, 'dut.core.u_tdm.amp_mem[a*16]!=135',
                            'dut.core.u_tdm.amp_mem[a*16]!==profile_expected[0]', count=3)
    for old, new in [('dut.core.u_tdm.amp_mem[b*16]!=67', 'dut.core.u_tdm.amp_mem[b*16]!==profile_expected[16]'),
                     ('(i*3*192)/256', 'profile_expected[i]'),
                     ('dut.core.u_tdm.amp_mem[a*16]!=30', 'dut.core.u_tdm.amp_mem[a*16]!==profile_expected[32]'),
                     ('dut.core.u_tdm.amp_mem[a*16]!=90', 'dut.core.u_tdm.amp_mem[a*16]!==profile_expected[48]'),
                     ('dut.core.u_tdm.amp_mem[b*16]!=45', 'dut.core.u_tdm.amp_mem[b*16]!==profile_expected[64]'),
                     ('independent custom spectrum', 'PROFILE custom spectrum')]:
        text = replace_required(text, old, new)
    marker = '        if(dut.core.finger_active[a]!=1||dut.core.finger_active[b]!=1)'
    text = replace_required(text, marker, '        profile_check(a,0);profile_check(b,16);profile_check(c,0);profile_check(d,16);\n' + marker)
    marker = '        report(0);\n        // Fill 32 groups'
    text = replace_required(text, marker, '        profile_check(a,32);\n' + marker)
    marker = '        // Invalid masks must reject'
    text = replace_required(text, marker, '        profile_check(a,48);profile_check(b,64);\n' + marker)
    helper = '''
    reg [7:0] profile_expected[0:79];
    initial $readmemh("../../profile-expected.hex", profile_expected);
    task profile_check;
        input integer group_number, reference_offset;
        integer partial_number;
        begin
            for(partial_number=0;partial_number<16;partial_number=partial_number+1)
                if(dut.core.u_tdm.amp_mem[group_number*16+partial_number] !== profile_expected[reference_offset+partial_number])
                    $fatal(1,"PROFILE amplitude group=%0d partial=%0d",group_number,partial_number);
            $display("PROFILE amplitude checked group=%0d reference=%0d",group_number,reference_offset);
        end
    endtask
'''
    return replace_required(text, 'endmodule', helper + 'endmodule')


def build_bench(source, case, profile, fault=None):
    name, top, bench, paths = case
    text = source.replace('"../', '"../../')
    if profile == 'current' and name == 'layers':
        text = layer_reference_bench(text)
    probe = 'initial begin\nrepeat(4000) @(negedge clk);\n'
    for path in paths:
        probe += ('if(' + path + ".r_vel_sens !== 8'h80 || " + path + '.vel_vscale !== 9\'d256) '
                  '$fatal(1,"PROFILE native defaults");\n')
    probe += '$display("PROFILE ' + profile + ' native_defaults_checked");\n'
    if profile == 'historical':
        for path in paths:
            probe += 'force ' + path + ".vel_vscale = 9'd0;\n"
    elif fault == 'muted-velocity':
        probe += "force dut.core.vel_vscale = 9'd0;\n"
    elif fault == 'wrong-slot':
        probe += "force dut.core.u_nm.u_vshape.slot = 2'd0;\n"
    return replace_required(text, 'endmodule', probe + 'end\nendmodule')


def compare_trace(reference, actual):
    first = None
    differing = 0
    expected_lines = 0
    actual_lines = 0
    with reference.open('rb') as expected, actual.open('rb') as observed:
        for line_number, (left, right) in enumerate(zip_longest(expected, observed), 1):
            expected_lines += left is not None
            actual_lines += right is not None
            if left != right:
                differing += 1
                if first is None:
                    first = dict(line=line_number, expected=(left or b'').decode().rstrip(),
                                 actual=(right or b'').decode().rstrip())
    return dict(equal=differing == 0, differing_lines=differing, first_difference=first,
                expected_lines=expected_lines, actual_lines=actual_lines,
                reference_sha256=digest(reference), actual_sha256=digest(actual))


def execute(command, cwd, log, timeout=300):
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        raw, returncode = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, returncode = (error.stdout or b'') + b'\nTIMEOUT\n', 124
    log.write_bytes(raw)
    return dict(command=command, cwd=str(cwd), returncode=returncode,
                log_sha256=digest(log), text=raw.decode('utf-8', errors='replace'))


def successful_run(result, name, profile):
    label = dict(compat='music', layers='layers', sensor='sensor')[name]
    text = result['text']
    return (result['returncode'] == 0 and 'FATAL:' not in text and '[FAIL]' not in text
            and 'PASS ' + label in text and 'PROFILE ' + profile + ' native_defaults_checked' in text
            and (profile != 'current' or name != 'layers'
                 or text.count('PROFILE amplitude checked') == 7))


def expected_fault(result):
    return (result['returncode'] not in (0, 124) and 'PROFILE current native_defaults_checked' in result['text']
            and ('FATAL:' in result['text'])
            and any(marker in result['text'] for marker in ('PROFILE amplitude', 'PROFILE custom spectrum')))


def run_case(root, case, profile, compiler, simulator, fault=None):
    name, top, bench, paths = case
    output = root / 'profile-results'
    original = (root / DATA / bench).read_text(encoding='utf-8')
    generated = build_bench(original, case, profile, fault)
    (root / bench).write_text(generated, encoding='utf-8')
    sources = [path for folder in ('engine/src', 'engine/rtl', 'rtl')
               for path in sorted((root / folder).glob('*.v'))
               if path.name not in ('joint_timing_top.v', 'probe_scan_store.v')]
    sources += [root / bench, root / 'tb/vendor_ram16sdp4.v']
    files = sources + list((root / 'engine/src').glob('*.hex')) + list((root / 'engine/src').glob('*.vh'))
    files += list(root.glob('*.hex'))
    before = {path.relative_to(root).as_posix(): digest(path) for path in files}
    command = [compiler, '-g2012', '-DTIMING_RTL_SIM', '-I', str(root / 'engine/src'),
               '-s', top, '-o', str(output / (name + '.vvp')), *map(str, sources)]
    compilation = execute(command, root, output / (name + '-compile.log'))
    result = dict(name=name, profile=profile, fault=fault, inputs=before, compilation=compilation,
                  original_bench_sha256=digest(root / DATA / bench), generated_bench_sha256=digest(root / bench),
                  product_acceptance=False)
    if compilation['returncode'] == 0 and 'FATAL:' not in compilation['text']:
        trace = output / (name + '.tsv')
        simulation = execute([simulator, str(output / (name + '.vvp')), '+trace=' + trace.as_posix()],
                             root / 'engine/src', output / (name + '-run.log'))
        result['simulation'] = simulation
        reference = root / DATA / 'evidence' / (name + '-all.tsv')
        golden = json.loads((root / DATA / 'evidence/music-equivalence-all.json').read_text(encoding='utf-8'))
        if digest(reference) != golden['traces'][name + '-all']['sha256']:
            raise ValueError('Golden identity changed: ' + name)
        if trace.exists():
            result['historical_trace_comparison'] = compare_trace(reference, trace)
        if fault:
            result['passed'] = expected_fault(simulation)
            result['scope'] = 'Intentional testbench/reference fault must be detected, not a passing music implementation'
        else:
            result['passed'] = successful_run(simulation, name, profile)
            if profile == 'historical':
                result['passed'] &= result.get('historical_trace_comparison', {}).get('equal', False)
            result['scope'] = ('Legacy velocity-off full golden equality' if profile == 'historical'
                               else 'Current default probe behavior; layered amplitudes checked against Python integer oracle, not full product acceptance')
    else:
        result['passed'] = False
    result['input_changes_during_run'] = [name for name, value in before.items() if digest(root / name) != value]
    result['passed'] &= not result['input_changes_during_run']
    write_json(output / (name + '.json'), result)
    return result


def run_profile(profile, output, compiler, simulator, fault=None):
    origin = engineering.export('fpga', output)
    output = output.resolve()
    (output / 'profile-results').mkdir()
    for name in ('sustain.hex', 'strike.hex'):
        shutil.copyfile(output / DATA / name, output / name)
    if profile == 'current':
        amplitudes = expected_amplitudes(output)
        if fault == 'bad-reference':
            amplitudes[0] = (amplitudes[0] + 1) % 256
        (output / 'profile-expected.hex').write_text('\n'.join(format(value, '02x') for value in amplitudes) + '\n', encoding='utf-8')
    results = []
    for case in CASES:
        if fault and case[0] != 'layers':
            continue
        print('RUN ' + profile + ('/' + fault if fault else '') + '/' + case[0], flush=True)
        try:
            result = run_case(output, case, profile, compiler, simulator, fault)
        except (ValueError, OSError, KeyError) as error:
            result = dict(name=case[0], profile=profile, fault=fault, passed=False, error=str(error))
        results.append(result)
        print(case[0] + ': ' + ('PASS' if result['passed'] else 'FAIL'), flush=True)
    changed = [name for name, value in origin['inputs'].items() if digest(output / name) != value]
    unexpected = sorted(set(changed) - BENCHES)
    report = dict(profile=profile, fault=fault, results=results, status='PASS' if all(result['passed'] for result in results) and not unexpected else 'FAIL',
                  source_origin_sha256=digest(output / 'SOURCE-ORIGIN.json'), source_manifest_sha256=origin['manifest_sha256'],
                  changed_original_inputs=changed, unexpected_source_changes=unexpected,
                  hardware_accessed=False, product_acceptance=False)
    write_json(output / 'profile-results/results.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=['all', 'historical', 'current'], default='all')
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == engineering.ROOT or engineering.ROOT in output.parents:
        raise ValueError('Output must be new and outside the source repository')
    engineering.check()
    tools = {}
    for key, executable in [('FPGA_IVERILOG', 'iverilog'), ('FPGA_VVP', 'vvp')]:
        selected = os.environ.get(key) or shutil.which(executable) or 'D:/iverilog/bin/' + executable + '.exe'
        if not Path(selected).is_file():
            raise ValueError('Missing simulator: ' + key)
        tools[key] = str(Path(selected).resolve())
    output.mkdir(parents=True)
    profiles = ['historical', 'current'] if arguments.profile == 'all' else [arguments.profile]
    reports = [run_profile(profile, output / profile, tools['FPGA_IVERILOG'], tools['FPGA_VVP']) for profile in profiles]
    if arguments.fault_checks:
        for fault in ('bad-reference', 'muted-velocity', 'wrong-slot'):
            reports.append(run_profile('current', output / fault, tools['FPGA_IVERILOG'], tools['FPGA_VVP'], fault))
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), runner_sha256=digest(Path(__file__)),
                  tools=tools, profiles=reports, status='PASS' if all(report['status'] == 'PASS' for report in reports) else 'FAIL',
                  scope='Explicit snapshot profiles and intentional fault detection, not four-layer/score/live/physical product acceptance',
                  hardware_accessed=False, product_acceptance=False)
    write_json(output / 'results.json', result)
    print(json.dumps(dict(status=result['status'], output=str(output), product_acceptance=False)))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
