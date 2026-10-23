"""One-time, read-only capture of selected active project inputs.

Archives source/context, not generated builds or a product acceptance result.
Refuses existing destinations; source hashes are checked again after reading.
"""
from pathlib import Path
import datetime, hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[2]
FPGA = Path('D:/FPGA-Project/codex-builds/fpga-m1-agent-work')
HW = Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware/review-manufacturing-20261019')
OUT = ROOT / 'project/archives/latest-design-inputs-20261023.zip'
MANIFEST = ROOT / 'project/versions/latest-design-inputs-20261023.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists() or MANIFEST.exists():
        raise ValueError('Refuse to replace an existing capture')
    selected = {}
    suffixes = {'.v', '.sv', '.vh', '.hex', '.cst', '.sdc', '.py', '.md', '.json', '.csv', '.txt', '.log', '.toml'}
    for p in FPGA.iterdir():
        if p.is_file() and p.suffix in suffixes:
            selected['fpga/' + p.name] = p
    for prefix in ('engine/src', 'engine/rtl', 'rtl', 'constraints', 'tb', 'sim', 'tools', 'project', 'reference', 'handoff_support'):
        base = FPGA / prefix
        if not base.is_dir():
            continue
        for p in base.rglob('*'):
            rel = p.relative_to(base)
            if any(x in {'sim_build', 'sim_work', '__pycache__', 'node_modules', '.git'} or x.startswith(('build_', 'synth_')) for x in rel.parts):
                continue
            if p.is_file() and not p.is_symlink() and p.suffix in suffixes and p.stat().st_size < 2_000_000:
                selected['fpga/' + p.relative_to(FPGA).as_posix()] = p
    # Small original receipts remain claims tied to their own source identity.
    for p in (FPGA / 'evidence').rglob('*'):
        if p.is_file() and not p.is_symlink() and p.suffix in {'.json', '.log', '.txt'} and p.stat().st_size < 200_000:
            selected['fpga/' + p.relative_to(FPGA).as_posix()] = p
    regional = json.loads((HW / 'REGIONAL-WORK-IN-PROGRESS.json').read_text(encoding='utf-8'))
    u9 = Path(regional['active_native_construction']['state']).parent
    scope = HW / 'u8-power-corridor-20261022/address3-local-recovery/single-touch-scope'
    hardware = {
        'REGIONAL-WORK-IN-PROGRESS.json': HW / 'REGIONAL-WORK-IN-PROGRESS.json',
        'AUTONOMOUS-CURRENT.md': HW / 'AUTONOMOUS-CURRENT.md',
        'single-touch/SCOPE-CHANGE.md': scope / 'SCOPE-CHANGE.md',
        'single-touch/README.md': scope / 'README.md',
        'verified/native-WORK-IN-PROGRESS.zip': Path(regional['pending_trial']['native_package']),
    }
    for name in ('README.md', 'construction-state.json', 'regional-native-review.json', 'three-component-check.json', 'control-branches-native-review.json', 'construction-native-NOT-FOR-FAB.zip'):
        if (u9 / name).is_file():
            hardware['active/' + name] = u9 / name
    for name, path in hardware.items():
        selected['hardware/' + name] = path
    captured_at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    blobs = {name: path.read_bytes() for name, path in sorted(selected.items())}
    unstable = [str(path) for name, path in selected.items() if sha(path.read_bytes()) != sha(blobs[name])]
    if unstable:
        raise ValueError('Active inputs changed during capture; retry with new verified input set: ' + repr(unstable))
    records = {name: dict(source_path=str(selected[name]), bytes=len(data), sha256=sha(data)) for name, data in blobs.items()}
    old = json.loads((ROOT / 'project/handoff.json').read_text(encoding='utf-8'))['fpga_handoff']['effective_build_inputs']
    effective = {name[len('fpga/'):]: item['sha256'] for name, item in records.items() if any(name.startswith('fpga/' + pre + '/') for pre in ('engine/src', 'engine/rtl', 'rtl', 'constraints')) and len(Path(name).parts) == (4 if name.startswith('fpga/engine/') else 3) and Path(name).suffix in {'.v', '.sv', '.vh', '.hex', '.cst', '.sdc'}}
    result = dict(schema=1, captured_at=captured_at, classification='Observed WIP source and context; not an atomic CAD transaction or product acceptance',
                  archive=OUT.relative_to(ROOT).as_posix(), files=records, effective_build_inputs=effective,
                  changed_registered_inputs=[p for p, h in old.items() if effective.get(p) != h],
                  added_build_inputs=sorted(set(effective) - set(old)),
                  exclusions=['Generated build/simulation directories and bitstreams', 'Large derived golden traces and installed tools', 'Full live hardware working directory; only listed context and existing recovery ZIPs captured'],
                  validation_inherited=False, product_accepted=False, manufacturing_release=False,
                  capture_consistency='Every selected file reread before writing; cross-file/native-state atomicity not asserted')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in blobs.items():
            z.writestr(name, data)
        z.writestr('CAPTURE-MANIFEST.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    result['archive_sha256'] = sha(OUT.read_bytes())
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(files=len(records), archive_bytes=OUT.stat().st_size, fpga_inputs=len(effective), changed=result['changed_registered_inputs'], added=result['added_build_inputs']), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
