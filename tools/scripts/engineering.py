"""Verify and export the published engineering candidates into isolated workspaces.

All tests run on a new export. No device/CAD operations are performed.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'project/versions/engineering-sources-20261023.json'
sha = lambda data: hashlib.sha256(data).hexdigest()


def safe(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe relative path: ' + name)
    return Path(*p.parts)


def read_manifest(root=ROOT):
    return json.loads((root/MANIFEST).read_text(encoding='utf8'))


def content(root, item):
    stored = (root/safe(item['stored'])).read_bytes()
    if sha(stored) != item['stored_sha256']:
        raise ValueError('Stored identity changed: ' + item['stored'])
    if item['codec'] not in ('raw', 'gzip'):
        raise ValueError('Unknown codec')
    raw = gzip.decompress(stored) if item['codec'] == 'gzip' else stored
    if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
        raise ValueError('Source identity changed: ' + item['stored'])
    return raw


def check(root=ROOT):
    m = read_manifest(root)
    count = 0
    for area, entry in m['areas'].items():
        expected = set()
        for name, item in entry['files'].items():
            safe(name)
            if not item['stored'].startswith(area + '/current/'):
                raise ValueError('Wrong area: ' + name)
            content(root, item)
            expected.add(item['stored'])
            count += 1
        for path in (root/area/'current').rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            relative = path.relative_to(root).as_posix()
            if relative not in expected and path != root/area/'current'/'README.md':
                raise ValueError('Unregistered engineering file: ' + relative)
    return dict(status='PASS', files=count, captured_at=m['captured_at'],
                scope='Engineering input identities, not Git publication, live freshness or product acceptance',
                product_acceptance=False)


def export(area, output, root=ROOT):
    output = output.resolve()
    source = root.resolve()
    if output == source or source in output.parents:
        raise ValueError('Export must be outside the source repository')
    if output.exists():
        raise ValueError('Refuse to overwrite existing output: ' + str(output))
    check(root)
    m = read_manifest(root)
    entry = m['areas'][area]
    # Validate before creating the destination, including all decoded golden data.
    for name, item in entry['files'].items():
        safe(name)
        content(root, item)
    output.mkdir(parents=True)
    for name, item in entry['files'].items():
        p = output/safe(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content(root, item))
    for name in ('README.md', 'AGENTS.md'):
        src = root/area/'current'/name
        if src.exists():
            shutil.copyfile(src, output/name)
    provenance = dict(manifest=MANIFEST, manifest_sha256=sha((root/MANIFEST).read_bytes()),
                      area=area, captured_at=m['captured_at'], source_branch=m['source_branch'],
                      inputs={n:i['sha256'] for n,i in entry['files'].items()},
                      validation_inherited=False, product_acceptance=False)
    (output/'SOURCE-ORIGIN.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf8')
    return provenance


def run_tests(area, output):
    provenance = export(area, output)
    output = output.resolve()
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
    commands = []
    if area == 'fpga':
        for key, tool, fallback in [('FPGA_IVERILOG','iverilog','D:/iverilog/bin/iverilog.exe'),
                                    ('FPGA_VVP','vvp','D:/iverilog/bin/vvp.exe')]:
            value = env.get(key) or shutil.which(tool) or (fallback if Path(fallback).is_file() else None)
            if not value:
                raise ValueError('Missing tool: ' + key)
            env[key] = str(Path(value).resolve())
        commands = [([sys.executable,'tools/scripts/gen_vel_wtab.py','--check'], 'velocity-table'),
                    ([sys.executable,'tools/run_sims.py','-v'], 'seven-simulations'),
                    ([sys.executable,'check_engine_compat.py'], 'music-golden'),
                    ([sys.executable,'check_pitch.py'], 'pitch-reference')]
    elif area == 'host':
        env['PYTHONPATH'] = os.pathsep.join([str(output/'tools/scripts'), str(output/'tools/host')])
        commands = [([sys.executable,'-m','unittest','discover','-s','tools/host','-p','test_*.py','-v'], 'host-offline')]
    else:
        raise ValueError('Hardware export is checked by identity; no automatic CAD execution')
    log_dir = output/'publication-validation'
    log_dir.mkdir()
    results = []
    for cmd, label in commands:
        print('RUN ' + label, flush=True)
        try:
            result = subprocess.run(cmd, cwd=output, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=1800)
            log, rc = result.stdout, result.returncode
        except subprocess.TimeoutExpired as error:
            log, rc = (error.stdout or b'') + b'\nTIMEOUT\n', 124
        (log_dir/(label+'.log')).write_bytes(log)
        # Guard scripts that print PASS but accidentally return zero on a fatal error.
        text = log.decode('utf8', errors='replace')
        ok = rc == 0 and 'FATAL:' not in text and '[FAIL]' not in text
        results.append(dict(name=label, command=cmd, returncode=rc, passed=ok,
                            log_sha256=sha(log)))
        print(label + ': ' + ('PASS' if ok else 'FAIL'), flush=True)
    report = dict(tested_at=datetime.now(timezone.utc).isoformat(), area=area,
                  manifest_sha256=provenance['manifest_sha256'], results=results,
                  inputs=provenance['inputs'],
                  status='PASS' if all(x['passed'] for x in results) else 'FAIL',
                  product_acceptance=False, hardware_accessed=False)
    (log_dir/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))
    return 0 if report['status']=='PASS' else 1


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    for name in ('export','test'):
        p=sub.add_parser(name)
        p.add_argument('--area',choices=['fpga','hardware','host'],required=True)
        p.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if a.command=='check':
        print(json.dumps(check()))
    elif a.command=='export':
        export(a.area,a.output)
        print(json.dumps(dict(status='EXPORTED',area=a.area,output=str(a.output))))
    else:
        return run_tests(a.area,a.output)
    return 0


if __name__=='__main__':
    sys.exit(main())
