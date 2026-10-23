from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT/'project/reviews/20261024-engineering-publication'
sys.path.insert(0, str(ROOT/'tools/scripts'))
import design_governance as governance
import engineering


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def main():
    if (FOLDER/'review.json').exists():
        raise ValueError('Review already finalized; do not renew by rerunning')
    manifest = engineering.read_manifest(ROOT)
    inspection = engineering.check(ROOT)
    validation = FOLDER/'validation'
    runs = {
        'fpga-initial': Path('D:/FPGA-Project/review/collaboration-fpga-20261024-01'),
        'fpga': Path('D:/FPGA-Project/review/collaboration-fpga-20261024-02'),
        'host-initial': Path('D:/FPGA-Project/review/collaboration-host-20261024-01'),
        'host': Path('D:/FPGA-Project/review/collaboration-host-20261024-02'),
        'hardware': Path('D:/FPGA-Project/review/collaboration-hardware-20261024-01')
    }
    results = {}
    for label, directory in runs.items():
        target = validation/label
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(directory/'SOURCE-ORIGIN.json', target/'SOURCE-ORIGIN.json')
        logs = directory/'publication-validation'
        if logs.exists():
            for path in logs.iterdir():
                if path.is_file():
                    shutil.copyfile(path, target/path.name)
        origin = json.loads((target/'SOURCE-ORIGIN.json').read_text(encoding='utf8'))
        expected = {name:item['sha256'] for name,item in manifest['areas'][origin['area']]['files'].items()}
        same = origin['inputs'] == expected
        results[label] = dict(source_inputs_match_checkpoint=same, area=origin['area'])
        if not label.endswith('-initial') and not same:
            raise ValueError('Tested area differs from checkpoint: '+label)
        if (target/'results.json').exists():
            results[label]['result'] = json.loads((target/'results.json').read_text(encoding='utf8'))
    sources = dict(checked=0, modified=[], missing=[])
    for area, entry in manifest['areas'].items():
        for name,item in entry['files'].items():
            source = item['source']
            try:
                if '!' in source:
                    archive,member = source.split('!',1)
                    with zipfile.ZipFile(archive) as opened:
                        raw = opened.read(member)
                else:
                    raw = Path(source).read_bytes()
            except (OSError,KeyError) as error:
                sources['missing'].append(dict(area=area,path=name,reason=str(error)))
                continue
            sources['checked'] += 1
            expected = item.get('upstream_sha256',item['sha256'])
            if digest(raw) != expected:
                sources['modified'].append(dict(area=area,path=name))
    write(validation/'upstream-source-comparison.json', sources)
    if sources['modified'] or sources['missing']:
        raise ValueError('Producer changed since capture; inspect source comparison')
    raw_observation = FOLDER/'observation.json'
    observation = governance.read_json(raw_observation)
    previous_policy = governance.read_json(ROOT/'project/governance.json')
    previous = governance.read_json(ROOT/previous_policy['review_record'])
    old_producers = governance.reviewed_producers(ROOT,previous)
    changes = {name:governance.compare_files(old_producers[name]['files'],value['files'])
               for name,value in observation['producers'].items()}
    evidence = {path.relative_to(ROOT).as_posix():digest(path.read_bytes())
                for path in validation.rglob('*') if path.is_file()}
    stamp = datetime.now(timezone.utc).isoformat()
    review = dict(schema=1, reviewed_at=stamp,
                  observer_role='User-authorized continuation of engineering publication; no functional producer ownership taken',
                  previous_review=previous_policy['review_record'],
                  previous_review_sha256=previous_policy['review_sha256'],
                  raw_observation=raw_observation.relative_to(ROOT).as_posix(),
                  raw_observation_sha256=digest(raw_observation.read_bytes()),
                  producer_ids=list(observation['producers']), changes_since_previous_review=changes,
                  verdict='REVIEWED_WITH_DECLARED_WIP', engineering_inputs=inspection,
                  engineering_manifest_sha256=digest((ROOT/engineering.MANIFEST).read_bytes()),
                  upstream_source_comparison=sources, isolated_validation=results,
                  evidence=evidence,
                  assessment=dict(
                      fpga='Seven focused simulations, velocity generator and pitch reference/fault tests pass. Historical music golden regression fails at compat cycle6662. Later layer/sensor golden cases were not run by the fail-fast script. One declaration-order-only adaptation enables elaboration; no PnR/STA/board acceptance.',
                      host='100 offline tests pass after capturing missing retrigger measurement helper; hardware/FPGA protocol compatibility unverified.',
                      hardware='Native byte export verified; author-recorded e098c5db47 connections13nets227components616vias. Retained aaa37 baseline is separate. No CAD execution/fabrication acceptance.',
                      procurement='New JLCPCB order document reads old53-component prototype and cannot describe the active227-component carrier; do not adopt missing-power/AUX assumptions, pin remaps or estimated totals.',
                      publication='Named task branch packages editable candidates. Actual remote head/PR determines publication; main merge still requires user approval. Producer future changes are not included.',
                      product='J11 cancellation/J10 retention and other existing goals unchanged. No new music semantics or circuit decisions adopted.'),
                  product_acceptance=False, new_cad_operations=False, hardware_accessed=False)
    write(FOLDER/'review.json',review)
    policy = previous_policy
    policy.update(review_record=(FOLDER/'review.json').relative_to(ROOT).as_posix(),
                  review_sha256=digest((FOLDER/'review.json').read_bytes()),reviewed_at=stamp)
    for name in list(policy['controlled_files']):
        policy['controlled_files'][name] = digest((ROOT/name).read_bytes())
    for name in [engineering.MANIFEST,'project/ENGINEERING.md','project/COLLABORATION-CHECKPOINT-20261024.md',
                 'tools/scripts/engineering.py','tools/requirements-engineering-host.txt',*evidence]:
        policy['controlled_files'][name] = digest((ROOT/name).read_bytes())
    policy['controlled_files'][raw_observation.relative_to(ROOT).as_posix()] = digest(raw_observation.read_bytes())
    write(ROOT/'project/governance.json',policy)
    print(json.dumps(dict(status='REVIEWED_WITH_DECLARED_WIP',input_files=inspection['files'],
                         results={key:value.get('result',{}).get('status','IDENTITY_ONLY') for key,value in results.items()},
                         source_comparison=sources)))


if __name__ == '__main__':
    main()
