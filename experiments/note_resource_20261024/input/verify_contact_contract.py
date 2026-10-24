from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys

from diagnose_timing import digest, output_path, ROOT, PROJECT


FAULTS = {
    'legacy-token-alias': (
        'token = self.source << 31 | self.next_serial',
        'token = generation << 5 | contact',
        'test_late_off_and_move_survive_legacy_generation_wrap_without_alias'),
    'held-retrigger': (
        "if contact in self.rows and self.rows[contact]['held']:",
        "if contact in self.rows and self.rows[contact]['held'] and self.rows[contact]['groups']:",
        'test_stolen_held_contact_does_not_retrigger_or_move_new_owner'),
    'first-layer-only': (
        "return dict(token=token, groups=row['groups'], layers=row['layers'], position=position)",
        "return dict(token=token, groups=row['groups'] & -row['groups'], layers=row['layers'], position=position)",
        'test_all_four_layers_move_together_without_new_identity'),
}


def mutate(source, fault):
    if fault == 'candidate':
        return source
    before, after, test = FAULTS[fault]
    if source.count(before) != 1:
        raise ValueError('Contact mutation anchor changed: '+fault)
    return source.replace(before, after)


def positive_valid(code, text):
    return code == 0 and 'Ran 11 tests' in text and re.search(r'^OK\r?$', text, re.M) is not None


def negative_valid(code, text, target):
    return code not in (0, 124) and re.search(r'^FAIL: '+re.escape(target)+r'\b', text, re.M) is not None


def main():
    parser = argparse.ArgumentParser(description='Isolated contact lifecycle oracle and designated counterexamples; not RTL or physical acceptance')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    sources = [Path(__file__).resolve(), ROOT/'contact_contract.py', ROOT/'tests/test_contact_contract.py',
               ROOT.parent/'reference.py', ROOT/'CONTACT-ADAPTER-CONTRACT.md']
    inputs = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    output.mkdir(parents=True)
    snapshot = output/'original-inputs'
    snapshot.mkdir()
    for source in sources:
        shutil.copyfile(source, snapshot/source.name)
    original = (ROOT/'contact_contract.py').read_text(encoding='utf-8')
    reports = []
    for fault in ('candidate',)+tuple(FAULTS):
        directory = output/fault
        tests = directory/'input/tests'
        tests.mkdir(parents=True)
        model = directory/'input/contact_contract.py'
        selected = mutate(original, fault)
        ast.parse(selected)
        model.write_bytes(selected.encode('utf-8'))
        shutil.copyfile(ROOT/'tests/test_contact_contract.py', tests/'test_contact_contract.py')
        shutil.copyfile(ROOT.parent/'reference.py', directory/'reference.py')
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', str(tests), '-v']
        try:
            process = subprocess.run(command, cwd=directory, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            raw, code = process.stdout, process.returncode
        except subprocess.TimeoutExpired as error:
            raw, code = (error.stdout or b'')+b'\nTIMEOUT\n', 124
        log = directory/'run.log'
        log.write_bytes(raw)
        text = raw.decode('utf-8', errors='replace')
        if fault == 'candidate':
            passed = positive_valid(code, text)
        else:
            passed = negative_valid(code, text, FAULTS[fault][2])
        reports.append(dict(case=fault, passed=passed, returncode=code, command=command,
            target_test=FAULTS[fault][2] if fault in FAULTS else None, log_sha256=digest(log),
            model_sha256=digest(model), test_sha256=digest(tests/'test_contact_contract.py'),
            resource_reference_sha256=digest(directory/'reference.py')))
        print(fault+': '+('PASS' if passed else 'FAIL'), flush=True)
    changed = [name for name, expected in inputs.items() if digest(PROJECT/name) != expected]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        python=dict(path=sys.executable, sha256=digest(Path(sys.executable))), source_changes=changed,
        reports=reports, status='PASS' if all(report['passed'] for report in reports) and not changed else 'FAIL',
        scope='Transaction oracle against existing independent shared-resource model; no RTL/ready-valid/PCM/sensor qualification',
        rtl_adapter_implemented=False, hardware_accessed=False, product_acceptance=False)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
