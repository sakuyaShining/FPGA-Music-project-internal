#!/usr/bin/env python3
"""Verify a sealed PCB handoff; optionally restore its split recovery archive.

A record marked ``storage: "release"`` keeps its bytes outside the Git tree.
Its identity (path, bytes, sha256) still lives in the manifest, so a clone can
prove exactly what it is missing and fetch only that from the declared release.
When such a file is present locally it is verified byte-for-byte like any other.
"""
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


def external_root(args, root):
    """Directory that may hold release-hosted blobs, mirroring checkpoint paths."""
    return args.external_root.resolve() if args.external_root else root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=Path(__file__).resolve().parents[2] / 'hardware/checkpoints/pcb-951ce88a-20261025')
    parser.add_argument('--git-ref', help='Also compare every in-tree payload against the specified committed Git blob')
    parser.add_argument('--restore-archive', type=Path, help='New ZIP output path; refuses an existing file')
    parser.add_argument('--external-root', type=Path, help='Directory holding downloaded release blobs, mirroring checkpoint-relative paths')
    parser.add_argument('--require-external', action='store_true', help='Treat a missing release-hosted blob as a failure')
    args = parser.parse_args()
    root = args.checkpoint.resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    external_block = manifest.get('external_storage') or {}
    declared = set(external_block.get('files') or [])
    release = external_block.get('release') or {}
    external_dir = external_root(args, root)
    errors = []
    present, absent = [], []
    repo = Path(__file__).resolve().parents[2]
    in_tree = 0
    for record in manifest['files']:
        is_external = record.get('storage') == 'release'
        if is_external and record['path'] not in declared:
            errors.append('external record missing from external_storage.files: ' + record['path'])
            continue
        if not is_external and record['path'] in declared:
            errors.append('external_storage.files lists an in-tree record: ' + record['path'])
            continue
        path = safe_path(external_dir if is_external else root, record['path'])
        if is_external:
            if not path.is_file():
                absent.append(record['path'])
                continue
            if path.stat().st_size != record['bytes'] or digest_file(path) != record['sha256']:
                errors.append('external bytes differ: ' + record['path'])
            else:
                present.append(record['path'])
            continue
        in_tree += 1
        if not path.is_file() or path.stat().st_size != record['bytes'] or digest_file(path) != record['sha256']:
            errors.append(record['path'])
            continue
        if args.git_ref:
            relative = path.relative_to(repo).as_posix()
            result = subprocess.run(['git', 'show', args.git_ref + ':' + relative], cwd=repo, capture_output=True)
            if result.returncode or hashlib.sha256(result.stdout).hexdigest() != record['sha256']:
                errors.append('git:' + relative)
    archive = manifest['recovery_archive']
    missing = [part for part in archive['parts'] if not safe_path(external_dir, part).is_file()]
    combined = hashlib.sha256()
    total = 0
    archive_state = 'verified_local'
    if missing:
        undeclared = [part for part in missing if part not in declared]
        if undeclared:
            errors.append('missing archive part (not declared external): ' + ','.join(undeclared))
        if release.get('combined_recovery_sha256') != archive['sha256']:
            errors.append('release does not declare the sealed recovery archive sha256')
        archive_state = 'external'
    else:
        for part in archive['parts']:
            with safe_path(external_dir, part).open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    combined.update(block)
                    total += len(block)
        if total != archive['bytes'] or combined.hexdigest() != archive['sha256']:
            errors.append('combined recovery archive')
    if absent and (args.require_external or args.restore_archive):
        errors.append('release-hosted blobs absent locally: ' + ','.join(absent))
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
                with safe_path(external_dir, part).open('rb') as source:
                    shutil.copyfileobj(source, target, 1024 * 1024)
        if digest_file(output) != archive['sha256']:
            raise ValueError('Restored archive hash differs')
        restored = str(output)
    print(json.dumps({
        'status': 'PASS',
        'files': len(manifest['files']),
        'files_in_tree': in_tree,
        'external_declared': len(declared),
        'external_verified_local': len(present),
        'external_absent_local': len(absent),
        'recovery_archive': archive_state,
        'source_pcb_sha256': manifest['native_pcb_sha256'],
        'archive_sha256': combined.hexdigest() if archive_state == 'verified_local' else archive['sha256'],
        'git_ref': args.git_ref,
        'restored_archive': restored,
        'scope': 'In-tree payload bytes and Git blob identity verified; release-hosted blobs pinned by sha256 and verified byte-for-byte when present locally; no new CAD/DRC/physical acceptance',
        'manufacturing_release': False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
