#!/usr/bin/env python3
"""Record or compare a source snapshot; hashes establish identity, not correctness.

python tools/scripts/project_baseline.py --write notes/baselines/2026-10-09.json
python tools/scripts/project_baseline.py --check notes/baselines/2026-10-09.json
Existing snapshots cannot be overwritten. After reviewing a change, write a new one.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ['src', 'tools/host', 'tools/scripts']


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def fingerprints():
    names = git('ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *SCOPE)
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(names.split('\0')))
        if name and (ROOT / name).is_file()
    }


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT,
                        help='Read another checkout; does not modify its files')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', type=Path)
    group.add_argument('--check', type=Path)
    args = parser.parse_args()
    ROOT = args.repo.resolve()
    current = fingerprints()
    if not current:
        raise ValueError('No source files found')
    if args.write:
        target = args.write if args.write.is_absolute() else ROOT / args.write
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot = dict(schema_version=1, captured_at=datetime.now(timezone.utc).isoformat(),
                        source_head=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                        scope=SCOPE, git_status_at_capture=git('status', '--porcelain=v1'),
                        files=current)
        with target.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(snapshot, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print('Recorded %d files: %s' % (len(current), target))
        return 0
    target = args.check if args.check.is_absolute() else ROOT / args.check
    snapshot = json.loads(target.read_text(encoding='utf-8'))
    if snapshot.get('schema_version') != 1 or snapshot.get('scope') != SCOPE or not snapshot.get('files'):
        raise ValueError('Unsupported or empty snapshot')
    recorded = snapshot['files']
    added = sorted(current.keys() - recorded.keys())
    removed = sorted(recorded.keys() - current.keys())
    changed = sorted(name for name in current.keys() & recorded.keys() if current[name] != recorded[name])
    for label, names in [('ADDED', added), ('REMOVED', removed), ('CHANGED', changed)]:
        for name in names:
            print('%s %s' % (label, name))
    print('Source HEAD at capture: %s' % snapshot['source_head'])
    print('Current HEAD: %s' % git('rev-parse', 'HEAD'))
    print('RESULT baseline=%s files=%d added=%d removed=%d changed=%d' % (
        'FAIL' if added or removed or changed else 'PASS', len(current), len(added), len(removed), len(changed)))
    return 1 if added or removed or changed else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Baseline error: %s' % error)
        raise SystemExit(1)
