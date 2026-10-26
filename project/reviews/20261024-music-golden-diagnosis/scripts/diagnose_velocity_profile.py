from pathlib import Path
from datetime import datetime, timezone
import argparse
import importlib.util
import json
import shutil
import traceback


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output = root / 'velocity-profile-diagnosis'
    output.mkdir()
    common = module_from_file('variant_common', root / 'common.py')
    diagnosis = module_from_file('diagnosis_helpers', Path(__file__).with_name('diagnose_music_golden.py'))
    source = root / 'handoff_support/resource_safety_20261016'
    origin = json.loads((root / 'SOURCE-ORIGIN.json').read_text(encoding='utf-8'))
    assert all(diagnosis.digest(root / name) == value for name, value in origin['inputs'].items())
    golden = json.loads((source / 'evidence/music-equivalence-all.json').read_text(encoding='utf-8'))
    for name in ('sustain.hex', 'strike.hex'):
        shutil.copyfile(source / name, root / name)
    results = {}
    cases = [('compat', 'tb_music', 'tb_compat_music.v', ['dut.core', 'ref_top']),
             ('layers', 'tb_layers', 'tb_layers.v', ['dut.core']),
             ('sensor', 'tb_sensor_layers', 'tb_sensor_layers.v', ['dut.music.core'])]
    for name, top, bench, paths in cases:
        print('RUN legacy-velocity-off ' + name, flush=True)
        try:
            original = (source / bench).read_text(encoding='utf-8').replace('"../', '"../../')
            probe = 'initial begin\nrepeat(4000) @(negedge clk);\n'
            for path in paths:
                probe += '$display("DIAG ' + path + ' r_vel_sens=%h native_vscale=%d", ' + path + '.r_vel_sens, ' + path + '.vel_vscale);\n'
                probe += 'force ' + path + ".vel_vscale = 9'd0;\n"
            probe += 'end\n'
            assert original.count('endmodule') == 1
            (root / bench).write_text(original.replace('endmodule', probe + 'endmodule'), encoding='utf-8')
            reference = source / 'evidence' / (name + '-all.tsv')
            assert diagnosis.digest(reference) == golden['traces'][name + '-all']['sha256']
            files = [path for path in common.sources() if path.name not in ('joint_timing_top.v', 'probe_scan_store.v')]
            files += [root / bench, root / 'tb/vendor_ram16sdp4.v']
            common.run([common.IV, '-g2012', '-DTIMING_RTL_SIM', '-I', str(root / 'engine/src'),
                        '-s', top, '-o', str(output / (name + '.vvp')), *map(str, files)], 'legacy-velocity-compile-' + name)
            trace = output / (name + '.tsv')
            log = common.run([common.VVP, str(output / (name + '.vvp')), '+trace=' + trace.as_posix()],
                             'legacy-velocity-run-' + name, root / 'engine/src')
            comparison = diagnosis.compare(reference, trace)
            results[name] = dict(status='MATCH' if comparison['equal'] else 'DIFFERENT', log=log,
                                 testbench_sha256=diagnosis.digest(root / bench), comparison=comparison)
            print(name + ': ' + results[name]['status'], flush=True)
        except Exception:
            results[name] = dict(status='ERROR', error=traceback.format_exc())
            print(results[name]['error'], flush=True)
        (output / 'progress.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    source_changes = [name for name, value in origin['inputs'].items() if diagnosis.digest(root / name) != value]
    report = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(),
                  source_origin_sha256=diagnosis.digest(root / 'SOURCE-ORIGIN.json'),
                  source_manifest_sha256=origin['manifest_sha256'], runner_sha256=diagnosis.digest(Path(__file__)),
                  helper_sha256=diagnosis.digest(Path(diagnosis.__file__)), results=results,
                  experiment='At cycle4000 force velocity vscale off in testbenches only; leave registers, tables and all product RTL unchanged.',
                  interpretation='Diagnostic control, not current-default acceptance, product fix or permission to disable velocity expression.',
                  source_changes=source_changes, product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(results={name: result['status'] for name, result in results.items()}, source_changes=source_changes)), flush=True)


if __name__ == '__main__':
    main()
