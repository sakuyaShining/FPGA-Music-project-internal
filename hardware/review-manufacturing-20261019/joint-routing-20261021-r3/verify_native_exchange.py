"""Reconcile editor line splitting by geometry, not persistent segment IDs."""
import hashlib,json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'local-power-bus-with-return-plan.json');old=read(Path(plan['source_file']))
new=read(OUT/'applied-source.json');audit=read(OUT/'apply-audit.json')
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
assert sha(PCB)==audit['applied_pcb_sha256']
assert audit['all_pads_unchanged'] and all(audit['unselected_copper_unchanged'].values()) and audit['original_via_ids_preserved']
expected_lines=[p for p in old['lines'] if p['id'] not in plan['remove_line_ids']]+plan['additive_power_lines']+plan['bus_lines']+plan['ground_lines']
expected_vias=old['vias']+plan['additive_power_vias']+plan['bus_vias']+plan['ground_vias']
shapes=lambda ls:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32) for p in ls])
checks=[]
# Five nanometres covers sub-0.0001mil saved/API coordinate rounding. It is a
# comparison tolerance only; no native clearance or width rule is changed.
tol=.000005
for net in ['5V_PERIPH','BUS_RETURN','GND']:
    for layer in [1,2]:
        e=shapes([p for p in expected_lines if p['net']==net and p['layer']==layer])
        a=shapes([p for p in new['lines'] if p['net']==net and p['layer']==layer])
        missing=e.difference(a.buffer(tol));extra=a.difference(e.buffer(tol))
        checks.append(dict(net=net,layer=layer,missing_copper_area_mm2=missing.area,unexpected_copper_area_mm2=extra.area,
            equivalent_within_rounding=missing.is_empty and extra.is_empty))
        assert missing.is_empty and extra.is_empty,checks[-1]
assert len(expected_vias)==len(new['vias'])
for p in expected_vias:
    matches=[q for q in new['vias'] if q['net']==p['net'] and abs(q['x']-p['x'])<.00011 and abs(q['y']-p['y'])<.00011]
    assert len(matches)==1
    q=matches[0]
    for field in ['diameter','hole']:assert abs(q[field]-p[field])<.05001
old_ids={p['id']:p for p in old['lines']};new_ids={p['id'] for p in new['lines']}
auto_split=[dict(id=i,net=p['net']) for i,p in old_ids.items() if i not in new_ids and i not in plan['remove_line_ids']]
assert len(auto_split)==3 and all(p['net']=='5V_PERIPH' for p in auto_split)
result=dict(source_pcb_sha256=plan['native_pcb_sha256'],applied_pcb_sha256=sha(PCB),
    native_auto_split_old_tracks=auto_split,copper_shape_checks=checks,comparison_tolerance_mm=tol,
    all_expected_copper_preserved=True,no_unplanned_copper=True,original_vias_preserved=True,
    source_sha256={n:sha(OUT/n) for n in ['local-power-bus-with-return-plan.json','applied-source.json','apply-audit.json']},
    requires_full_native_drc=True,manufacturing_release=False)
(OUT/'native-geometry-reconciliation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
