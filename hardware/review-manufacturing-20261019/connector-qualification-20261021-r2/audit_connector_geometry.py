"""Read current embedded footprints and compare selected manufacturer dimensions.

No EDA permission bypass: read-only saved-file inspection, no native edits/DRC.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PROJECT = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
PCB = PROJECT / 'pcb/PCB1.epcb2'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checkpoint = json.loads((ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text(encoding='utf-8'))
assert sha(PCB) == checkpoint['pcb_sha256']
docs = {}
current = None
for line in PCB.read_text(encoding='utf-8').splitlines():
    if '||' not in line:
        continue
    head, body = line.split('||', 1)
    h = json.loads(head)
    raw = body.rstrip('|')
    value = json.loads(raw) if raw else None
    if h['type'] == 'DOCHEAD':
        current = value['uuid']
        docs.setdefault(current, {'meta': value, 'live': {}})
    if current:
        docs[current]['live'][(h['type'], h.get('id'))] = value
board = next(d for d in docs.values() if d['meta']['docType'] == 'PCB')
attrs = {}
for (kind, ident), value in board['live'].items():
    if kind == 'ATTR' and value:
        attrs.setdefault(value['parentId'], {})[value['key']] = value['value']
captures = json.loads((ROOT/'quality-r1-source-78.json').read_text(encoding='utf-8'))['pads']
rows = []
for ident, a in attrs.items():
    ref = a.get('Designator', '')
    if ref not in ['J13', 'J20', 'J21', 'J22', 'J23', 'J24', 'J25']:
        continue
    pads = [v for (kind, _), v in docs[a['Footprint']]['live'].items() if kind == 'PAD' and v]
    pads.sort(key=lambda v: int(v['num']))
    cap = sorted([p for p in captures if p['ref'] == ref], key=lambda p: int(p['n']))
    assert len(pads) == len(cap)
    # API capture is rounded to 0.1 mil; use embedded native footprint centers
    # for precise mechanical qualification, not rounded displayed coordinates.
    pitch = [math.hypot(pads[i+1]['centerX']-pads[i]['centerX'], pads[i+1]['centerY']-pads[i]['centerY'])*.0254 for i in range(len(pads)-1)]
    holes = [{'pin': p['num'], 'width_mm': p['hole']['width']*.0254,
              'height_mm': p['hole']['height']*.0254, 'plated': p['plated']} for p in pads]
    target_pitch = 2.5 if ref == 'J13' else 2.54
    recommended_hole = 1.0 if ref == 'J13' else 1.02
    assert all(abs(v-target_pitch) < .0001 for v in pitch)
    rows.append(dict(ref=ref, footprint_uuid=a['Footprint'], pins=len(pads),
        pitch_mm=pitch, native_holes=holes, manufacturer_pitch_mm=target_pitch,
        manufacturer_hole_nominal_mm=recommended_hole,
        hole_nominal_delta_mm=[p['width_mm']-recommended_hole for p in holes],
        pitch_matches=True, hole_nominal_matches=all(abs(p['width_mm']-recommended_hole)<.001 for p in holes),
        qualification='pitch_and_nominal_hole_verified_body_and_finished_hole_tolerance_pending',
        manufacturer_source='JST-XH.pdf' if ref == 'J13' else 'XFCN-PZ254V-11-XX.pdf'))
assert len(rows) == 7
native_ok = {rel: sha(PROJECT/rel) == expected for rel, expected in checkpoint['files'].items()}
assert all(native_ok.values())
result = dict(utc=datetime.now(timezone.utc).isoformat(), pcb_sha256=sha(PCB),
    capture_sha256=sha(ROOT/'quality-r1-source-78.json'),
    manufacturer_sha256={name:sha(OUT/name) for name in ['JST-XH.pdf','XFCN-PZ254V-11-XX.pdf']},
    components=rows, native_files_unchanged=native_ok, manufacturing_release=False,
    limitations='Read-only footprint dimensions; no finished-hole tolerance, body/retention/plug fit or new native DRC signoff. Oversize holes are a review item, not automatically a manufacturing defect.')
(OUT/'geometry-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'components':len(rows), 'pitch_matches':all(r['pitch_matches'] for r in rows),
    'holes':[(r['ref'], r['native_holes'][0]['width_mm'],r['manufacturer_hole_nominal_mm']) for r in rows],
    'native_files_unchanged':all(native_ok.values()),'manufacturing_release':False},indent=2))
