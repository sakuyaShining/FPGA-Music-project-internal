from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import shutil

from diagnose_timing import digest, output_path, registered_wrapper, ROOT, PROJECT
from verify import run


def main():
    parser = argparse.ArgumentParser(description='Verify diagnostic shell one-cycle alignment, not product behavior')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    sources = [Path(__file__).resolve(), ROOT/'diagnose_timing.py', ROOT/'build.py', ROOT/'verify.py',
               ROOT/'rtl/note_event_router.v', ROOT/'rtl/note_router_timing_probe.v', ROOT/'tb/tb_router_shell_pipeline.v']
    inputs = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    output.mkdir(parents=True)
    snapshot = output/'original-inputs'
    snapshot.mkdir()
    for source in sources:
        shutil.copyfile(source, snapshot/source.name)
    original = (ROOT/'rtl/note_router_timing_probe.v').read_text(encoding='utf-8')
    if original.count('module note_router_timing_probe(') != 1:
        raise ValueError('Original shell module identity changed')
    reference = original.replace('module note_router_timing_probe(', 'module note_router_timing_original(', 1)
    registered = registered_wrapper(original)
    reports = []
    for case in ('registered', 'misaligned-load'):
        directory = output/case
        directory.mkdir()
        candidate = registered
        if case == 'misaligned-load':
            if candidate.count('if(load_q)controls<=staging;') != 1:
                raise ValueError('Misalignment anchor changed')
            candidate = candidate.replace('if(load_q)controls<=staging;', 'if(load)controls<=staging;')
        (directory/'original.v').write_text(reference, encoding='utf-8')
        (directory/'registered.v').write_text(candidate, encoding='utf-8')
        shutil.copyfile(ROOT/'rtl/note_event_router.v', directory/'note_event_router.v')
        shutil.copyfile(ROOT/'tb/tb_router_shell_pipeline.v', directory/'tb.v')
        binary = directory/'shell.vvp'
        compilation = run([str(compiler), '-g2012', '-s', 'tb_router_shell_pipeline', '-o', str(binary),
                           str(directory/'original.v'), str(directory/'registered.v'),
                           str(directory/'note_event_router.v'), str(directory/'tb.v')], directory/'compile.log', directory)
        report = dict(case=case, compilation=compilation, passed=False)
        if compilation['returncode'] == 0:
            simulation = run([str(simulator), str(binary)], directory/'run.log', directory)
            report['simulation'] = simulation
            report['passed'] = (simulation['returncode'] == 0 and 'PASS shell_pipeline cycles=24000 ' in simulation['text']) if case == 'registered' else (
                simulation['returncode'] not in (0, 124) and 'shell pipeline state mismatch' in simulation['text'])
        report['source_hashes'] = {path.name: digest(path) for path in directory.glob('*.v')}
        reports.append(report)
        print(case+': '+('PASS' if report['passed'] else 'FAIL'), flush=True)
    changed = [name for name, expected in inputs.items() if digest(PROJECT/name) != expected]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        tools={str(path): digest(path) for path in (compiler, simulator)}, reports=reports, source_changes=changed,
        status='PASS' if all(report['passed'] for report in reports) and not changed else 'FAIL',
        scope='Diagnostic shell full state and router outputs equal original delayed one cycle; misalignment mutant required',
        hardware_accessed=False, product_acceptance=False)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
