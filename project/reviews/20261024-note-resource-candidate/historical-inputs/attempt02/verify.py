from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess

from reference import scenarios

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_trace(path):
    blocks = []
    for line in path.read_text(encoding='utf-8').splitlines():
        words = line.split()
        if words[0] == 'C':
            blocks.append(dict(index=int(words[1]), works=[], entries=[]))
        elif words[0] == 'W':
            blocks[-1]['works'].append([int(words[1]), int(words[2])] + [int(value, 16) for value in words[3:]])
        elif words[0] == 'R':
            blocks[-1]['response'] = [int(words[1])] + [int(value, 16) for value in words[2:]]
        elif words[0] == 'S':
            blocks[-1]['snapshot'] = [int(words[1], 16), int(words[2], 16), int(words[3]), int(words[4])]
        elif words[0] == 'E':
            blocks[-1]['entries'].append([int(value, 16) for value in words[1:5]] + [int(words[5])])
        else:
            raise ValueError('Unexpected trace record: ' + line)
    return blocks


def first_difference(expected, observed):
    for index in range(max(len(expected), len(observed))):
        if index >= len(expected) or index >= len(observed):
            return dict(command=index, field='command-count', expected=len(expected), observed=len(observed))
        for field in ('works', 'response', 'snapshot', 'entries'):
            if expected[index][field] != observed[index].get(field):
                return dict(command=index, field=field, expected=expected[index][field], observed=observed[index].get(field))
    return None


def run(command, output, timeout=300):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        raw, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, code = (error.stdout or b'') + b'\nTIMEOUT\n', 124
    output.write_bytes(raw)
    return dict(command=command, returncode=code, log_sha256=digest(output), text=raw.decode('utf-8', errors='replace'))


def mutate(source, fault):
    count = 1
    if fault == 'tail-priority':
        old, new = 'else if(entries_released[scanned_victim])begin', 'else if(!entries_released[scanned_victim])begin'
    elif fault == 'partial-retire':
        old = 'issue_work(RETIRE,read_token,read_mask,read_layers,read_map,AFTER_STEAL);'
        new = 'issue_work(RETIRE,read_token,read_mask&(~read_mask+1\'b1),read_layers,read_map,AFTER_STEAL);'
        count = 2
    else:
        return source
    if source.count(old) != count:
        raise ValueError('Mutant source anchor changed')
    return source.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description='Compare resource RTL to an independent ordered-note model; no PCM/board claim')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=20261024)
    parser.add_argument('--random-count', type=int, default=700)
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or ROOT == output or ROOT in output.parents:
        raise ValueError('Use a new output outside the experiment')
    compiler = os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe'
    simulator = os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe'
    compiler, simulator = str(Path(compiler).resolve()), str(Path(simulator).resolve())
    if not Path(compiler).is_file() or not Path(simulator).is_file():
        raise ValueError('Icarus and vvp are required')
    commands, expected = scenarios(arguments.seed, arguments.random_count)
    inputs = {name:digest(ROOT / name) for name in ('rtl/note_resource_mgr.v', 'tb/tb_note_resource.v', 'reference.py', 'verify.py')}
    output.mkdir(parents=True)
    command_file = output / 'commands.txt'
    command_file.write_text(''.join('{kind} {token:08x} {layers:01x} {groups:08x} {cancel} {ready_delay} {done_delay} {response_delay} {wrong_ack}\n'.format(**command)
                                  for command in commands), encoding='utf-8')
    (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
    (output / 'expected.json').write_text(json.dumps(expected) + '\n', encoding='utf-8')
    reports = []
    for fault in [None] + (['tail-priority', 'partial-retire'] if arguments.fault_checks else []):
        label = fault or 'candidate'
        print('RUN ' + label, flush=True)
        directory = output / label
        directory.mkdir()
        source = mutate((ROOT / 'rtl/note_resource_mgr.v').read_text(encoding='utf-8'), fault)
        rtl = directory / 'note_resource_mgr.v'
        rtl.write_text(source, encoding='utf-8')
        binary = directory / 'resource.vvp'
        compilation = run([compiler, '-g2012', '-s', 'tb_note_resource', '-o', str(binary), str(rtl),
                           str(ROOT / 'tb/tb_note_resource.v')], directory / 'compile.log')
        report = dict(fault=fault, compilation=compilation, mutant_sha256=digest(rtl), passed=False)
        if compilation['returncode'] == 0:
            trace = directory / 'trace.tsv'
            simulation = run([simulator, str(binary), '+commands=' + command_file.as_posix(), '+trace=' + trace.as_posix()], directory / 'run.log')
            report['simulation'] = simulation
            observed = decode_trace(trace) if trace.exists() else []
            difference = first_difference(expected, observed)
            report.update(first_difference=difference, trace_sha256=digest(trace), completed_commands=len(observed))
            if fault:
                report['passed'] = (simulation['returncode'] != 124 and difference is not None
                                    and difference['field'] == 'works')
            else:
                report['passed'] = simulation['returncode'] == 0 and 'FATAL:' not in simulation['text'] and 'PASS resource' in simulation['text'] and difference is None
            (directory / 'trace.tsv.gz').write_bytes(gzip.compress(trace.read_bytes(), mtime=0))
        reports.append(report)
        print(label + ': ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
    source_changes = [name for name, value in inputs.items() if digest(ROOT / name) != value]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), seed=arguments.seed,
                  commands=len(commands), inputs=inputs, commands_sha256=digest(command_file), expected_sha256=digest(output / 'expected.json'),
                  tools=dict(iverilog=dict(path=compiler, sha256=digest(Path(compiler))), vvp=dict(path=simulator, sha256=digest(Path(simulator)))),
                  results=reports, source_changes=source_changes,
                  status='PASS' if all(report['passed'] for report in reports) and not source_changes else 'FAIL',
                  scope='Resource coordinator plus mock backend, not actual audio/envelope completion, four-layer PCM or board acceptance',
                  product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], commands=result['commands'], output=str(output))))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
