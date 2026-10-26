from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
CAPTURED = PROJECT / 'fpga/current'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, output, cwd, timeout=600):
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        raw, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, code = (error.stdout or b'') + b'\nTIMEOUT\n', 124
    output.write_bytes(raw)
    return dict(command=command, returncode=code, log_sha256=digest(output), text=raw.decode('utf-8', errors='replace'))


def mutant(source, fault):
    anchors = {
        'early-consume': ('pv1 & (TRANSACTIONAL ? published1 : (pp1 != ppr1))', 'pv1 & (pp1 != ppr1)'),
        'ignore-kill': ('wire kill_effect=TRANSACTIONAL&&consume&&kill1;', "wire kill_effect=1'b0;"),
        'early-finish': ('wire quiet_partial=env_n==0&&stg_n==0&&!eff_gate&&!(pv1&&!consume);', 'wire quiet_partial=!eff_gate;'),
        'partial-token': ('part_rsp_ticket==ticket_hold&&part_rsp_token==token_hold&&', 'part_rsp_ticket==ticket_hold&&')
    }
    if fault not in anchors:
        return source
    before, after = anchors[fault]
    if source.count(before) != 1:
        raise ValueError('Mutation anchor changed: ' + fault)
    return source.replace(before, after)


def main():
    parser = argparse.ArgumentParser(description='Real captured TDM/envelope path with transactional loading; no board or complete-product claim')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside the repository')
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    if not compiler.is_file() or not simulator.is_file():
        raise ValueError('Icarus and vvp are required')
    source_files = list((ROOT / 'rtl').glob('*.v')) + list((ROOT / 'tb').glob('*.v')) + [ROOT / 'verify_audio.py', ROOT / 'ENGINE-SOURCE.json', ROOT.parent / 'rtl/note_resource_mgr.v']
    source_files += [CAPTURED / 'engine/src' / name for name in ('tdm_engine_rh.v', 'osc_env.v', 'pitch_mod.v', 'pitch_native_store.v', 'vel_shape.v', 'sine256.hex', 'note_inc.hex', 'preset_part.hex', 'vel_wtab.hex')]
    source_files += [CAPTURED / 'tb/vendor_ram16sdp4.v']
    inputs = {path.relative_to(PROJECT).as_posix():digest(path) for path in source_files}
    output.mkdir(parents=True)
    reports = []
    cases = ['legacy', 'candidate'] + (['early-consume', 'ignore-kill', 'early-finish', 'partial-token'] if arguments.fault_checks else [])
    for case in cases:
        print('RUN ' + case, flush=True)
        directory = output / case
        directory.mkdir()
        for name in ('sine256.hex', 'note_inc.hex', 'preset_part.hex', 'vel_wtab.hex'):
            shutil.copyfile(CAPTURED / 'engine/src' / name, directory / name)
        rtl = []
        for source in sorted((ROOT / 'rtl').glob('*.v')):
            destination = directory / source.name
            destination.write_bytes(mutant(source.read_text(encoding='utf-8'), case).encode('utf-8'))
            rtl.append(str(destination))
        bench = 'tb_audio_compat' if case == 'legacy' else 'tb_note_audio'
        sources = rtl + [str(ROOT.parent / 'rtl/note_resource_mgr.v'), str(ROOT / 'tb' / (bench + '.v'))]
        sources += [str(CAPTURED / 'engine/src' / name) for name in ('tdm_engine_rh.v', 'osc_env.v', 'pitch_mod.v', 'pitch_native_store.v', 'vel_shape.v')]
        sources.append(str(CAPTURED / 'tb/vendor_ram16sdp4.v'))
        binary = directory / 'audio.vvp'
        compilation = run([str(compiler), '-g2012', '-s', bench, '-o', str(binary)] + sources, directory / 'compile.log', directory)
        report = dict(case=case, compilation=compilation, passed=False,
                      generated_rtl={Path(name).name:digest(Path(name)) for name in rtl})
        if compilation['returncode'] == 0:
            trace = directory / 'trace.tsv'
            simulation = run([str(simulator), str(binary), '+trace=' + trace.as_posix()], directory / 'run.log', directory)
            report['simulation'] = simulation
            if case in ('legacy', 'candidate'):
                marker = 'PASS legacy_audio' if case == 'legacy' else 'PASS real_audio'
                report['passed'] = simulation['returncode'] == 0 and marker in simulation['text'] and 'FATAL:' not in simulation['text']
            else:
                marker = {'early-consume':'unpublished partial consumed', 'ignore-kill':'retirement acknowledged before silence',
                          'early-finish':'false natural completion', 'partial-token':'stale partial response consumed'}[case]
                report['passed'] = simulation['returncode'] not in (0,124) and marker in simulation['text']
            if trace.exists():
                report['trace_sha256'] = digest(trace)
                (directory / 'trace.tsv.gz').write_bytes(gzip.compress(trace.read_bytes(), mtime=0))
        reports.append(report)
        print(case + ': ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
        (output / 'progress.json').write_text(json.dumps(dict(results=reports), indent=2) + '\n', encoding='utf-8')
    changed = [name for name, value in inputs.items() if digest(PROJECT / name) != value]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        tools={str(path):digest(path) for path in (compiler, simulator)}, results=reports, source_changes=changed,
        status='PASS' if all(report['passed'] for report in reports) and not changed else 'FAIL',
        scope='Real TDM arithmetic/envelopes plus staged partial provider. No full live/score renderer, physical sensor, PnR/STA or bitstream acceptance.',
        product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], output=str(output))))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
