"""Bind a complete source tree to results and builds; identity never implies acceptance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ('src', 'tools/host', 'tools/scripts', 'docs/02-技术方案/regmap_baseline.csv', '.gitignore')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files(root):
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                                     '--others', '--exclude-standard', '--', *SCOPE]).decode('utf-8').split('\0')
    return {n: sha((root/n).read_bytes()) for n in sorted(set(names)) if n and (root/n).is_file()}


def required(root):
    project = root/'src/gowin/tdm_synth/tdm_synth.gprj'
    dependencies = {project.relative_to(root).as_posix()}
    for f in ET.parse(project).findall('.//File'):
        if f.attrib.get('enable', '1') == '1':
            dependencies.add((project.parent/f.attrib['path']).resolve().relative_to(root).as_posix())
    dependencies.update(p.relative_to(root).as_posix() for p in project.parent.glob('*.hex'))
    return dependencies


def check(root, manifest):
    record = json.loads(manifest.read_text(encoding='utf-8'))
    if record.get('schema') != 1 or record.get('scope') != list(SCOPE) or not record.get('files'):
        raise ValueError('Unsupported or empty manifest')
    actual, expected = files(root), record['files']
    errors = ['missing build dependency: '+n for n in sorted(required(root)-expected.keys())]
    for n in sorted(actual.keys() | expected.keys()):
        if actual.get(n) != expected.get(n): errors.append('source drift: '+n)
    if record.get('tree_sha256') != sha(json.dumps(expected,sort_keys=True).encode('utf-8')):
        errors.append('invalid manifest digest')
    return record, errors


def exclusive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='action', required=True)
    write = sub.add_parser('capture')
    write.add_argument('manifest', type=Path)
    write.add_argument('--label', required=True)
    verify = sub.add_parser('check')
    verify.add_argument('manifest', type=Path)
    build = sub.add_parser('bind-build')
    build.add_argument('manifest', type=Path)
    build.add_argument('--bitstream', type=Path, required=True)
    build.add_argument('--log', type=Path, required=True)
    build.add_argument('--command', required=True)
    build.add_argument('--configuration', required=True)
    build.add_argument('--output', type=Path, required=True)
    artifact = sub.add_parser('check-build')
    artifact.add_argument('record', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == 'check-build':
        bound = json.loads(args.record.read_text(encoding='utf-8'))
        if bound.get('schema') != 1: raise ValueError('Unsupported build record')
        manifest = Path(bound['source_manifest'])
        if not manifest.is_absolute(): manifest = root/manifest
        record, errors = check(root,manifest)
        if record['tree_sha256'] != bound['source_tree_sha256']: errors.append('wrong source manifest')
        for key in ('bitstream','log'):
            path=Path(bound[key])
            if not path.is_absolute(): path=root/path
            if not path.is_file() or sha(path.read_bytes())!=bound[key+'_sha256']: errors.append('artifact mismatch: '+key)
        for error in errors: print('FAIL',error)
        print('RESULT build_identity='+('FAIL' if errors else 'PASS'))
        return int(bool(errors))
    if args.action == 'capture':
        current=files(root)
        if not current or required(root)-current.keys(): raise ValueError('Incomplete source tree')
        exclusive(args.manifest, dict(schema=1, label=args.label, scope=list(SCOPE), files=current,
            tree_sha256=sha(json.dumps(current,sort_keys=True).encode('utf-8')),
            source_head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip(),
            captured_at=datetime.now(timezone.utc).isoformat(), python=sys.version,
            status=subprocess.check_output(['git','-C',str(root),'status','--porcelain']).decode('utf-8')))
        print('Captured %d source inputs; no acceptance implied' % len(current))
        return 0
    record, errors=check(root,args.manifest)
    for e in errors: print('FAIL',e)
    if errors: return 1
    if args.action == 'bind-build':
        if not args.bitstream.is_file() or not args.log.is_file(): raise ValueError('Missing build output')
        if args.bitstream.stat().st_size==0 or args.log.stat().st_size==0: raise ValueError('Empty build output')
        exclusive(args.output, dict(schema=1, source_manifest=str(args.manifest),
            source_tree_sha256=record['tree_sha256'], configuration=args.configuration,
            command=args.command, bitstream=str(args.bitstream.resolve()),
            bitstream_sha256=sha(args.bitstream.read_bytes()), log=str(args.log.resolve()),
            log_sha256=sha(args.log.read_bytes()), bound_at=datetime.now(timezone.utc).isoformat(),
            acceptance='identity-bound-only; review timing and hardware results separately'))
    print('RESULT project_version=PASS files=%d' % len(record['files']))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,subprocess.CalledProcessError,ET.ParseError,KeyError) as e:
        print('FAIL',e)
        raise SystemExit(1)
