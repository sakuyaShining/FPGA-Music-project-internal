"""One-time management preparation; reads producer inputs without editing them."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/scripts'))
import design_governance as g


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def main():
    root = g.ROOT
    review_dir = root / 'project/reviews/20261023-main-authority'
    if review_dir.exists():
        raise ValueError('Refuse to replace existing review inputs')
    manifest = g.read_json(root / 'project/versions/latest-design-inputs-20261023.json')
    suffixes = ['.v', '.sv', '.vh', '.hex', '.cst', '.sdc', '.py', '.md', '.json', '.csv', '.txt', '.log', '.toml']
    fpga = dict(id='fpga', activity='active', root='D:/FPGA-Project/codex-builds/fpga-m1-agent-work',
                owner=dict(thread_id=None, label='Independent FPGA session; exact session identity not registered'),
                publication_status='UNMERGED_WIP_WITH_OLDER_RECOVERY_ARCHIVE', observation_max_hours=6,
                recovery_manifest='project/versions/latest-design-inputs-20261023.json', published_ref=None,
                exclude_dirs=['sim_build', 'sim_work', '__pycache__', 'node_modules', '.git'],
                exclude_prefixes=['build_', 'synth_'], watch=[])
    for name in ('.', 'engine/src', 'engine/rtl', 'rtl', 'constraints', 'tb', 'sim', 'tools', 'project', 'reference', 'handoff_support'):
        fpga['watch'].append(dict(path=name, recursive=name != '.', suffixes=suffixes, max_bytes=2_000_000))
    fpga['watch'].append(dict(path='evidence', recursive=True, suffixes=['.json', '.log', '.txt'], max_bytes=200_000))
    hwroot = Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware/review-manufacturing-20261019')
    hardware = dict(id='hardware', activity='active', root=str(hwroot),
                    owner=dict(thread_id='01a15ee5-fa24-7501-8475-ad28a0f08939', label='查看 huangyongtao 最新进展'),
                    publication_status='LIVE_CONSTRUCTION_NOT_MANUFACTURING_RELEASE', observation_max_hours=6,
                    recovery_manifest='project/versions/latest-design-inputs-20261023.json', published_ref=None,
                    exclude_dirs=['.git', '__pycache__'], exclude_prefixes=[], watch=[])
    for name, item in manifest['files'].items():
        if name.startswith('hardware/'):
            hardware['watch'].append(dict(path=Path(item['source_path']).relative_to(hwroot).as_posix()))
    registry = dict(schema=1, scope='Declared active roots only; inaccessible roots are UNOBSERVED. Dormant sources require review before activation.',
                    producers=[fpga, hardware,
                               dict(id='host', activity='dormant', owner='No current owner registered',
                                    sources=['ca03', '6e70'], activation_requires_review=True)])
    write(root / 'project/producers.json', registry)
    # This is a draft preparation pointer, finalized after human-source review.
    write(root / 'project/governance.json', dict(producer_registry='project/producers.json'))
    observation = g.observe(review_dir / 'observation.json')
    summary = {}
    evidence = {}
    for producer, prefix in ((fpga, 'fpga/'), (hardware, 'hardware/')):
        ident = producer['id']
        obs = observation['producers'][ident]
        if obs['status'] != 'OBSERVED':
            raise ValueError('Cannot prepare review from ' + ident + ': ' + obs['status'])
        old = {}
        for name, item in manifest['files'].items():
            if name.startswith(prefix):
                rel = Path(item['source_path']).relative_to(Path(producer['root'])).as_posix()
                old[rel] = item
        changes = g.compare_files(old, obs['files'])
        summary[ident] = dict(compared_to_archive=changes, observed_files=len(obs['files']), omissions=obs.get('omissions', []))
        # Preserve changed design/context text so a different machine can read it.
        for rel in changes['modified'] + changes['added']:
            if Path(rel).suffix not in {'.md', '.json'} or rel.startswith('evidence/'):
                continue
            p = Path(producer['root']) / rel
            data = p.read_bytes()
            if g.digest(data) != obs['files'][rel]['sha256']:
                raise ValueError('Producer changed after observation: ' + str(p))
            target = review_dir / 'evidence' / ident / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            evidence[target.relative_to(root).as_posix()] = dict(source=str(p), sha256=g.digest(data))
    write(review_dir / 'changes-from-v2.json', dict(observed_at=observation['observed_at'], summary=summary, evidence=evidence,
          scope='Observed changes need review; archive remains immutable and no source acceptance is inherited'))
    print(json.dumps(dict(observed_at=observation['observed_at'], summary=summary, evidence_files=len(evidence)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
