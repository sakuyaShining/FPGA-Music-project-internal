"""One-time read-only import of selected engineering inputs; no CAD or board IO."""
from pathlib import Path
from datetime import datetime, timezone
import gzip, hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[2]
sha = lambda b: hashlib.sha256(b).hexdigest()
stamp = datetime.now(timezone.utc).isoformat()
manifest = dict(schema=1, captured_at=stamp, source_branch='codex/current-engineering-sources-20261023',
                role='Editable development candidates; no full-product acceptance', areas={})
read_sources = {}


def add(area, relative, data, source):
    base = ROOT / area / 'current'
    destination = base / relative
    if destination.exists():
        raise ValueError('Refuse overwrite: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stored = gzip.compress(data, mtime=0) if relative.endswith('.tsv') else data
    if relative.endswith('.tsv'):
        destination = destination.with_name(destination.name + '.gz')
    destination.write_bytes(stored)
    manifest['areas'][area]['files'][relative] = dict(
        stored=destination.relative_to(ROOT).as_posix(), bytes=len(data), sha256=sha(data),
        stored_sha256=sha(stored), codec='gzip' if relative.endswith('.tsv') else 'raw', source=source)


def copy(area, base, name, dest=None):
    p = base / name
    raw = p.read_bytes()
    read_sources[str(p)] = sha(raw)
    add(area, dest or name, raw, str(p))


for area in ('fpga', 'hardware', 'host'):
    if (ROOT / area / 'current').exists():
        raise ValueError('Existing import: ' + area)
    manifest['areas'][area] = dict(files={}, validation_inherited=False, product_acceptance=False)

f = Path('D:/FPGA-Project/codex-builds/fpga-m1-agent-work')
for directory in ('engine', 'rtl', 'constraints', 'tb', 'sim', 'tools', 'reference', 'handoff_support'):
    for p in sorted((f / directory).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.vvp', '.vcd'}:
            copy('fpga', f, p.relative_to(f).as_posix())
for p in sorted(f.iterdir()):
    if not p.is_file():
        continue
    if p.suffix in {'.py', '.v', '.vh', '.hex'}:
        copy('fpga', f, p.name)
    elif p.suffix in {'.md', '.json', '.csv'}:
        copy('fpga', f, p.name, 'upstream-notes/' + p.name)
manifest['areas']['fpga']['scope'] = 'Complete selected source/test/build/reference trees and root scripts/data; historical narratives isolated in upstream-notes. Generated builds omitted.'

h = Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware')
review = h / 'review-manufacturing-20261019'
u9 = review / 'u8-power-corridor-20261022/address3-local-recovery/retained-control-recovery/u9-layout'
native = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-U9ControlWork-20261023')
zp = u9 / 'construction-native-NOT-FOR-FAB.zip'
raw = zp.read_bytes(); read_sources[str(zp)] = sha(raw)
with zipfile.ZipFile(zp) as z:
    for name in z.namelist():
        if name.endswith('/'):
            continue
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        data = z.read(name)
        if name != 'CHECKPOINT-README.md':
            assert (native/name).is_file() and sha((native/name).read_bytes()) == sha(data), name
            read_sources[str(native/name)] = sha(data)
        add('hardware', 'native/' + name, data, str(zp) + '!' + name)
for name in ('REGIONAL-WORK-IN-PROGRESS.json', 'AUTONOMOUS-CURRENT.md'):
    copy('hardware', review, name, 'context/' + name)
for name in ('construction-state.json', 'README.md', 'construction-capture.json', 'construction-drc.json',
             'mosi-main-native-review.json', 'mosi-main-connected-ground-review.json'):
    copy('hardware', u9, name, 'context/u9/' + name)
for sub in ('purchase-preparation-20261021-r1',):
    for p in sorted((review/sub).iterdir()):
        if p.is_file() and p.suffix in {'.json', '.csv', '.md'}:
            copy('hardware', review, p.relative_to(review).as_posix(), 'context/' + p.relative_to(review).as_posix())
for p in sorted(h.rglob('expected-pin-nets.json')):
    copy('hardware', h, p.relative_to(h).as_posix(), 'interface-references/' + p.relative_to(h).as_posix())
manifest['areas']['hardware']['scope'] = 'Saved native project, current construction/DRC evidence and procurement context. No runtime sessions, derived routing experiments or manufacturing release; historical absolute paths are provenance only.'

c = Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
for p in sorted((c/'tools/host').rglob('*')):
    if p.is_file() and not any(part in {'__pycache__', 'build', 'dist'} for part in p.parts) and p.suffix in {'.py', '.json', '.qss', '.ttf', '.md'}:
        copy('host', c, p.relative_to(c).as_posix())
version=json.loads((c/'tools/host/host_version.json').read_text(encoding='utf8'))
for name in version['inputs']:
    if name.startswith('tools/scripts/'):
        copy('host', c, name)
manifest['areas']['host'].update(scope='ca03 host-workbench 11 source, assets, tests and protocol helper; no compatibility claim with current FPGA candidate.',
                                source_thread='01a130bf-52f5-7311-b486-1270b5a0e3d4', dormant=True)

changed=[name for name,digest in read_sources.items() if sha(Path(name).read_bytes()) != digest]
if changed:
    raise ValueError('Source changed during capture: ' + repr(changed))
out=ROOT/'project/versions/engineering-sources-20261023.json'
out.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
print(json.dumps(dict(captured_at=stamp, files={k:len(v['files']) for k,v in manifest['areas'].items()})))
