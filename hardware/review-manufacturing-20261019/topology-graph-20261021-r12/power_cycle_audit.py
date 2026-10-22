"""Find pad-connectivity-preserving 3V3_IO trace removals; no source mutation."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString
from shapely.strtree import STRtree
sys.path.insert(0,str(ROOT))
from resume_offline import read_native
from physical_geometry import actual_pad
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));raw=read_native(pcb)
mask={1:1,15:2,16:4,2:8,12:15};net='3V3_IO';objects=[]
for p in s['pads']:
    if p['net']==net:objects.append(dict(id=p['id'],kind='pad',mask=mask[p['layer']],shape=actual_pad(p),ref=p['ref'],pin=p['n']))
npads=len(objects)
for (k,i),p in raw.items():
    if p.get('netName')!=net:continue
    if k=='LINE' and p.get('layerId') in [1,15,16,2]:
        line=LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)])
        objects.append(dict(id=i,kind='line',layer=p['layerId'],mask=mask[p['layerId']],shape=line.buffer(p['width']*.0254/2,quad_segs=32),length_mm=line.length))
    elif k=='VIA':objects.append(dict(id=i,kind='via',mask=15,shape=Point(p['centerX']*.0254,p['centerY']*.0254).buffer(p['viaDiameter']*.0254/2,quad_segs=32)))
tree=STRtree([p['shape'] for p in objects]);adj=[set() for _ in objects];contacts=0
for i,p in enumerate(objects):
    for j in tree.query(p['shape'].buffer(.0031)):
        j=int(j)
        if j>=i or not p['mask']&objects[j]['mask']:continue
        if p['shape'].distance(objects[j]['shape'])<=.003:
            adj[i].add(j);adj[j].add(i);contacts+=1
def reached(skip):
    seen={0};stack=[0]
    while stack:
        for j in adj[stack.pop()]:
            if j not in seen and j not in skip:seen.add(j);stack.append(j)
    return seen
assert all(i in reached(set()) for i in range(npads)), 'Baseline3V3_IO pad graph is incomplete'
probe=json.loads((OUT/'top-barrier-probe.json').read_text(encoding='utf-8'))
boundary_ids={p['id'] for row in probe['terminals'] for p in row['boundary_lines'] if p['net']==net}
rows=[]
for i,p in enumerate(objects):
    if p['kind']!='line' or p['layer']!=1:continue
    seen=reached({i});pads_ok=all(j in seen for j in range(npads))
    rows.append(dict(id=p['id'],length_mm=p['length_mm'],on_harm_terminal_boundary=p['id'] in boundary_ids,
                     removal_preserves_all_power_pad_connections=pads_ok,disconnected_power_pads=[dict(ref=objects[j]['ref'],pin=objects[j]['pin']) for j in range(npads) if j not in seen]))
report=dict(source_pcb_sha256=cp['pcb_sha256'],native_imported=False,net=net,pad_count=npads,copper_object_count=len(objects),graph_contacts=contacts,
            tested_top_lines=len(rows),individually_redundant_top_lines=sum(r['removal_preserves_all_power_pad_connections'] for r in rows),
            individually_redundant_boundary_lines=[r for r in rows if r['on_harm_terminal_boundary'] and r['removal_preserves_all_power_pad_connections']],
            rows=rows,limitations=['Individual removals are not a jointly removable set.','Pad continuity alone does not establish voltage-drop/transient/thermal adequacy.','No removal is approved or applied.'])
(OUT/'power-cycle-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print({k:v for k,v in report.items() if k not in ['rows','limitations']},flush=True)
