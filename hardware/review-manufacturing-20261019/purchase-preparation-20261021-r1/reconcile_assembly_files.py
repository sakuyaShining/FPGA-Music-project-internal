"""Check historical native CPL against present saved placement before filtering.

This does not claim a fresh native export or DRC. Every output stays NOT FOR ORDER.
"""
import csv,hashlib,io,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from resume_offline import read_native
from current_state import current_checkpoint
pcb=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path,manifest,_=current_checkpoint(ROOT.parent)
before=h(pcb);assert before==manifest['pcb_sha256']
source=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2/cpl-DRAFT-NOT-FOR-ORDER.csv')
rows=list(csv.DictReader(io.StringIO(source.read_text(encoding='utf-16')),delimiter='\t'))
assert len(rows)==230 and len({r['Designator'] for r in rows})==230
live=read_native(pcb)
attributes={}
for (kind,_),p in live.items():
    if kind=='ATTR':attributes.setdefault(p['parentId'],{})[p['key']]=p['value']
placed={attributes[id]['Designator']:p for (kind,id),p in live.items() if kind=='COMPONENT'}
assert set(placed)=={r['Designator'] for r in rows}
master=json.loads((ROOT/'purchase-master.json').read_text(encoding='utf-8'))
parts={ref:p for p in master['board_bom'] for ref in p['refs'].split(',')}
factory={ref for ref,p in parts.items() if p['assembly']=='工厂SMT供料'}
assert len(factory)==217
errors=[];max_position_error=0
mm=lambda s:float(s.removesuffix('mm'))
for r in rows:
    ref=r['Designator'];p=placed[ref]
    err=max(abs(mm(r['Ref X'])-p['x']*.0254),abs(mm(r['Ref Y'])-p['y']*.0254));max_position_error=max(max_position_error,err)
    angle=abs((float(r['Rotation'])-p['angle']+180)%360-180)
    if err>.0011 or angle>1e-5 or r['Layer']!=('T' if p['layerId']==1 else 'B') or r['Footprint']!=parts[ref]['footprint']:
        errors.append(dict(ref=ref,origin_error_mm=err,rotation_error_deg=angle,layer=r['Layer'],native_layer=p['layerId'],footprint=r['Footprint'],expected_footprint=parts[ref]['footprint']))
report={'historical_native_cpl':str(source),'source_sha256':h(source),'current_pcb_sha256':before,
    'native_placed_components':230,'factory_selected_refs':217,'current_checkpoint':manifest_path.name,'maximum_origin_rounding_error_mm':max_position_error,
    'issues':errors,'fresh_native_export':False,'manufacturing_release':False}
(ROOT/'placement-reconciliation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert not errors,errors[:10]
def save(name,fields,records):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
bom=[{'Comment':p['mpn'],'Designator':p['refs'],'Footprint':p['footprint'],'LCSC Part #':p['code']} for p in master['board_bom'] if p['assembly']=='工厂SMT供料']
save('jlc-bom-217-DRAFT-NOT-FOR-ORDER.csv',list(bom[0]),bom)
filtered=[r for r in rows if r['Designator'] in factory]
save('native-cpl-217-FILTERED-HISTORICAL-NOT-FOR-ORDER.csv',list(rows[0]),filtered)
assert {r['Designator'] for r in filtered}==factory
assert h(pcb)==before
report.update(bom_part_types=len(bom),bom_ref_count=217,filtered_cpl_rows=217,bom_cpl_ref_sets_equal=True,
    all_230_saved_origins_rotations_layers_and_footprint_names_match=True,
    caution='Historical native CPL placement matches current saved board; fresh external-file export remains gated. Current r3 full DRC is 0 clearance/0 physical/74 connections; not released for fabrication')
(ROOT/'placement-reconciliation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
