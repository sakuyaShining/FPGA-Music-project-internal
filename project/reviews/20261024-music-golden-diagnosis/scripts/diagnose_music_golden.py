from pathlib import Path
from datetime import datetime, timezone
from itertools import zip_longest
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import traceback


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(reference, actual):
    first = None
    count = 0
    fields = {}
    reference_lines = 0
    actual_lines = 0
    with reference.open(encoding='utf-8') as expected, actual.open(encoding='utf-8') as observed:
        for line_number, pair in enumerate(zip_longest(expected, observed), 1):
            left, right = pair
            reference_lines += left is not None
            actual_lines += right is not None
            if left == right:
                continue
            count += 1
            left_fields = (left or '').split()
            right_fields = (right or '').split()
            changed = [index for index, values in enumerate(zip_longest(left_fields, right_fields)) if values[0] != values[1]]
            for index in changed:
                fields[str(index)] = fields.get(str(index), 0) + 1
            if first is None:
                first = dict(line=line_number, expected=(left or '').rstrip(), actual=(right or '').rstrip(), changed_columns_zero_based=changed)
    return dict(equal=count == 0, differing_lines=count, first_difference=first,
                differing_column_counts=fields, expected_lines=reference_lines, actual_lines=actual_lines,
                reference_sha256=digest(reference), actual_sha256=digest(actual))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output = root / 'golden-diagnosis'
    output.mkdir()
    spec = importlib.util.spec_from_file_location('isolated_common', root / 'common.py')
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    source = root / 'handoff_support/resource_safety_20261016'
    golden = json.loads((source / 'evidence/music-equivalence-all.json').read_text(encoding='utf-8'))
    origin = json.loads((root / 'SOURCE-ORIGIN.json').read_text(encoding='utf-8'))
    before = {name: digest(root / name) for name in origin['inputs']}
    for name in ('sustain.hex', 'strike.hex'):
        shutil.copyfile(source / name, root / name)
    results = {}
    for name, top, bench in [('compat', 'tb_music', 'tb_compat_music.v'),
                             ('layers', 'tb_layers', 'tb_layers.v'),
                             ('sensor', 'tb_sensor_layers', 'tb_sensor_layers.v')]:
        print('RUN ' + name, flush=True)
        try:
            (root / bench).write_text((source / bench).read_text(encoding='utf-8').replace('"../', '"../../'), encoding='utf-8')
            reference = source / 'evidence' / (name + '-all.tsv')
            assert digest(reference) == golden['traces'][name + '-all']['sha256']
            files = [path for path in common.sources() if path.name not in ('joint_timing_top.v', 'probe_scan_store.v')]
            files += [root / bench, root / 'tb/vendor_ram16sdp4.v']
            common.run([common.IV, '-g2012', '-DTIMING_RTL_SIM', '-I', str(root / 'engine/src'),
                        '-s', top, '-o', str(output / (name + '.vvp')), *map(str, files)], 'diagnosis-compile-' + name)
            trace = output / (name + '.tsv')
            log = common.run([common.VVP, str(output / (name + '.vvp')), '+trace=' + trace.as_posix()],
                             'diagnosis-run-' + name, root / 'engine/src')
            comparison = compare(reference, trace)
            results[name] = dict(status='MATCH' if comparison['equal'] else 'DIFFERENT',
                                 bench_sha256=digest(root / bench), log=log, comparison=comparison)
            print(name + ': ' + results[name]['status'] + ' first=' + str(comparison['first_difference']), flush=True)
        except Exception:
            results[name] = dict(status='ERROR', error=traceback.format_exc())
            print(results[name]['error'], flush=True)
        (output / 'progress.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    source_changes = [name for name, value in before.items() if digest(root / name) != value]
    report = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(),
                  source_origin_sha256=digest(root / 'SOURCE-ORIGIN.json'), source_manifest_sha256=origin['manifest_sha256'],
                  runner_sha256=digest(Path(__file__)), results=results, source_changes=source_changes,
                  tools={name: subprocess.run([value, '-V'], capture_output=True).stdout.decode('utf-8', errors='replace')
                         for name, value in [('iverilog', common.IV), ('vvp', common.VVP)]},
                  all_golden_equal=all(result['status'] == 'MATCH' for result in results.values()),
                  hardware_accessed=False, product_acceptance=False)
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(results={name: result['status'] for name, result in results.items()}, source_changes=source_changes)), flush=True)


if __name__ == '__main__':
    main()
