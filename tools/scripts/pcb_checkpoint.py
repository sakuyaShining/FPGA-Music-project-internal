#!/usr/bin/env python3
"""Verify a sealed PCB handoff; optionally restore its split recovery archive."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError('Path outside checkpoint: ' + relative)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=Path(__file__).resolve().parents[2] / 'hardware/checkpoints/pcb-951ce88a-20261025')
    parser.add_argument('--git-ref', help='Also compare every payload against the specified committed Git blob')
    parser.add_argument('--restore-archive', type=Path, help='New ZIP output path; refuses an existing file')
    args = parser.parse_args()
    root = args.checkpoint.resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    errors = []
    repo = Path(__file__).resolve().parents[2]
    for record in manifest['files']:
        path = safe_path(root, record['path'])
        if not path.is_file() or path.stat().st_size != record['bytes'] or digest_file(path) != record['sha256']:
            errors.append(record['path'])
            continue
        if args.git_ref:
            relative = path.relative_to(repo).as_posix()
            result = subprocess.run(['git', 'show', args.git_ref + ':' + relative], cwd=repo, capture_output=True)
            if result.returncode or hashlib.sha256(result.stdout).hexdigest() != record['sha256']:
                errors.append('git:' + relative)
    archive = manifest['recovery_archive']
    combined = hashlib.sha256()
    total = 0
    for part in archive['parts']:
        path = safe_path(root, part)
        if not path.is_file():
            errors.append('missing archive part:' + part)
            continue
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                combined.update(block)
                total += len(block)
    if total != archive['bytes'] or combined.hexdigest() != archive['sha256']:
        errors.append('combined recovery archive')
    if errors:
        print(json.dumps({'status': 'FAIL', 'errors': errors}, ensure_ascii=False, indent=2))
        return 1
    restored = None
    if args.restore_archive:
        output = args.restore_archive.resolve()
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as target:
            for part in archive['parts']:
                with safe_path(root, part).open('rb') as source:
                    shutil.copyfileobj(source, target, 1024 * 1024)
        if digest_file(output) != archive['sha256']:
            raise ValueError('Restored archive hash differs')
        restored = str(output)
    print(json.dumps({'status': 'PASS', 'files': len(manifest['files']), 'source_pcb_sha256': manifest['native_pcb_sha256'], 'archive_sha256': combined.hexdigest(), 'git_ref': args.git_ref, 'restored_archive': restored, 'scope': 'Payload and Git byte identity only; no new CAD/DRC/physical acceptance', 'manufacturing_release': False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
