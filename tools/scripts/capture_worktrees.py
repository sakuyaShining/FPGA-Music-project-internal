"""Preserve dirty/untracked files and inventory every checkout without changing it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone
import zipfile


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def capture(root, output):
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    names = set(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode('utf-8').split('\0')) - {''}
    names = {n for n in names if not n.startswith('notes/versioning/captures/')}
    dirty = set(git(root, 'diff', '--name-only', '-z', 'HEAD').decode('utf-8').split('\0'))
    dirty.update(git(root, 'ls-files', '-z', '--others', '--exclude-standard').decode('utf-8').split('\0'))
    files = {}
    with zipfile.ZipFile(output / 'working-changes.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            path = root / name
            if path.is_file():
                data = path.read_bytes()
                files[name] = hashlib.sha256(data).hexdigest()
                if name in dirty:
                    archive.writestr(name, data)
    (output / 'changes.patch').write_bytes(git(root, 'diff', '--binary', 'HEAD'))
    record = dict(schema=1, captured_at=datetime.now(timezone.utc).isoformat(), root=str(root),
                  head=git(root, 'rev-parse', 'HEAD').decode().strip(),
                  branch=git(root, 'branch', '--show-current').decode().strip(),
                  status=git(root, 'status', '--porcelain=v1', '-uall').decode('utf-8'),
                  files=files, deleted=sorted(n for n in dirty if n and not (root / n).exists()))
    record['archive_sha256'] = hashlib.sha256((output / 'working-changes.zip').read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('%s: %d files, %d preserved changes' % (root, len(files), len(dirty - {''})))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    roots = [line[9:] for line in git(repo, 'worktree', 'list', '--porcelain').decode('utf-8').splitlines() if line.startswith('worktree ')]
    for i, root in enumerate(roots):
        capture(Path(root), args.output / ('%02d-%s' % (i, Path(root).parent.name)))


if __name__ == '__main__':
    main()
