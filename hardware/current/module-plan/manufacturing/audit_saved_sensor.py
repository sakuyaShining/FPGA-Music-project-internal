"""Extract and audit the exact saved sensor candidate; never exports Gerber or qualifies fab."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, math

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'hardware/current/module-plan'
EVIDENCE = BASE / 'evidence'
OUTPUT = Path(__file__).parent
PCB_HASH = '617f550eadc818ffab26a3992f2a86bb9f72ed027043c6e64a0c0428077ba643'
SCH_HASH = '7710964c5831a580909709aab0ddb271cef88779a11f585de45149c6046e12eb'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def documents(path):
    docs=[]; current=None
    for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip():continue
        h,v=line.split('||',1)
        h=json.loads(h)
        v=v[:-1] if v.endswith('|') else v
        if not v.strip():continue
        v=json.loads(v)
        if h['type']=='DOCHEAD':
            current={'head':v,'records':[]};docs.append(current)
        if current is None:raise ValueError('Record before DOCHEAD on line '+str(number))
        current['records'].append((h,v))
    return docs

def write_json(name,value):
    (OUTPUT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))

def write_csv(name,rows,columns):
    with (OUTPUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    pcb=EVIDENCE/'sensor-fourlayer-native-current.epcb2'
    sch=EVIDENCE/'sensor-fourlayer-native-current.esch2'
    assert sha(pcb)==PCB_HASH,'PCB source differs from approved35 scope'
    assert sha(sch)==SCH_HASH,'Schematic source differs from pinned capture'
    docs=documents(pcb);boards=[d for d in docs if d['head']['docType']=='PCB']
    assert len(boards)==1,'Ambiguous PCB document'
    board=boards[0];records=board['records'];devices={};footprints={}
    for doc in docs:
        meta=next((v for h,v in doc['records'] if h['type']=='META'),{})
        if doc['head']['docType']=='DEVICE':devices[doc['head']['uuid']]=meta
        elif doc['head']['docType']=='FOOTPRINT':footprints[doc['head']['uuid']]=doc
    attributes=defaultdict(dict)
    for h,v in records:
        if h['type']=='ATTR':attributes[v['parentId']][v['key']]=v['value']
    parts=[];placements=[];all_refs=set();pad_map={}
    for h,v in records:
        if h['type']=='PAD_NET':pad_map.setdefault(h['id'],[]).append(v)
        if h['type']!='COMPONENT':continue
        a=attributes[h['id']];ref=a['Designator'];assert ref not in all_refs;all_refs.add(ref)
        device=devices[a['Device']];props={**device.get('attributes',{}),**v.get('attrs',{}),**a}
        foot=footprints[a['Footprint']];pads=[x for hh,x in foot['records'] if hh['type']=='PAD']
        mounting='TH' if any(p.get('hole') for p in pads) else 'SMT'
        assert v['layerId'] in (1,2),'Component not on assembly side'
        row=dict(Designator=ref,MPN=props['Manufacturer Part'],LCSC=props['Supplier Part'],Manufacturer=props.get('Manufacturer',''),Package=props.get('Supplier Footprint',''),Footprint=a['Footprint'],Mounting=mounting,Side='Top' if v['layerId']==1 else 'Bottom',Quantity=1)
        parts.append(row)
        placements.append(dict(Designator=ref,MidX_mm=round(v['x']*.0254,6),MidY_mm=round(v['y']*.0254,6),Layer=row['Side'],NativeRotation_deg=v['angle'],Mounting=mounting,Origin='native footprint placement origin; positive Y up; not vendor-export verified',ComponentID=h['id']))
    assert len(parts)==28 and len(all_refs)==28
    expected=json.loads((EVIDENCE/'sensor-front-native-BOM-current.json').read_text(encoding='utf-8'))
    expected_refs={ref:(row['MPN'],row['supplier_part']) for row in expected['rows'] for ref in row['refs']}
    assert {p['Designator']:(p['MPN'],p['LCSC']) for p in parts}==expected_refs,'Current board BOM differs from reviewed electrical allocation'
    assert len([p for p in parts if p['Mounting']=='SMT'])==26
    grouped=defaultdict(list)
    for p in parts:grouped[(p['MPN'],p['LCSC'],p['Package'],p['Mounting'])].append(p['Designator'])
    bom=[]
    for (mpn,lcsc,package,mount),refs in sorted(grouped.items()):
        bom.append(dict(Comment=mpn,Designator=','.join(sorted(refs)),Footprint=package,**{'LCSC Part #':lcsc},Quantity_per_board=len(refs),Quantity_six_boards=len(refs)*6,Assembly='factory SMT' if mount=='SMT' else 'factory TH preferred; user may solder headers'))
    write_csv('sensor-BOM-per-board-DRAFT.csv',bom,['Comment','Designator','Footprint','LCSC Part #','Quantity_per_board','Quantity_six_boards','Assembly'])
    write_csv('sensor-native-placement-DRAFT.csv',placements,['Designator','MidX_mm','MidY_mm','Layer','NativeRotation_deg','Mounting','Origin','ComponentID'])
    layers={str(h['id']):v for h,v in records if h['type']=='LAYER'}
    active_copper=[v for v in layers.values() if v.get('use') and v.get('layerType') in ['TOP','BOTTOM','SIGNAL','PLANE','INNER']]
    physical=[dict(record_id=h.get('id'),**v) for h,v in records if h['type']=='LAYER_PHYS']
    outlines=[v for h,v in records if h['type']=='POLY' and v.get('layerId')==11]
    counts=Counter(h['type'] for h,v in records)
    assert counts['LINE']==302 and counts['VIA']==51 and counts['COMPONENT']==28 and counts['PAD_NET']==150
    numeric=json.loads((EVIDENCE/'sensor35-numeric-review-current.json').read_text(encoding='utf-8'))
    assert numeric['source_sha256']==PCB_HASH and len(numeric['rows'])==35
    lines={h['id']:v for h,v in records if h['type']=='LINE'}
    vias={h['id']:v for h,v in records if h['type']=='VIA'}
    approved=json.loads((ROOT/'project/reviews/20261027-hardware-consolidation/sensor35-approval.json').read_text(encoding='utf-8'))
    assert approved['approval'] and approved['pcb_sha256']==PCB_HASH
    assert sha(EVIDENCE/'sensor35-numeric-review-current.json')==approved['numeric_report_sha256']
    scope_rows=[]
    for row in numeric['rows']:
        line=lines[row['line_id']]
        assert line['netName']==row['net'] and line['layerId']==row['layer']
        for terminal in row['terminals']:
            via=vias[terminal['paired_GND_via']]
            assert via['netName'] in ['Ground','GND']
            xy=[via['centerX']*.0254,via['centerY']*.0254]
            assert math.dist(xy,terminal['paired_GND_xy_mm'])<.00001
            centre=math.dist(terminal['xy'],xy)
            assert abs(centre-terminal['return_centres_mm'])<.00001
            assert centre<=1.50001
            assert terminal['copper_to_GND_min_mm']>=.1651
            assert terminal['paired_hole_edges_mm']>=.2999
        scope_rows.append(dict(number=row['number'],line_id=row['line_id'],net=row['net'],layer=row['layer'],paired_returns_checked=len(row['terminals'])))
    assert len(set(r['line_id'] for r in scope_rows))==35
    write_json('sensor-35-scope-verification.json',dict(status='PASS_LIMITED_SCOPE_IDENTITY_AND_REPORTED_DIMENSIONS',pcb_sha256=PCB_HASH,rows=scope_rows,note='Checks exact source IDs, approved numeric-report hash and actual return-via centres. Does not rerun Ground polygon geometry or native DRC, and does not waive other constraints.',manufacturing_release=False))
    write_json('sensor-source-manufacturing-audit.json',dict(status='DRAFT_INPUTS_EXTRACTED_NATIVE_EXPORT_AND_STACKUP_PENDING',pcb_sha256=PCB_HASH,schematic_sha256=SCH_HASH,pcb_uuid=board['head']['uuid'],components=parts,counts=dict(counts),active_layers=layers,physical_stack_records=physical,outline=outlines,smt_per_board=26,th_per_board=2,boards_needed=6,total_smt=156,total_th=12,bom_matches_reviewed_allocation=True,source_geometry_changed=False,native_manufacture_export_verified=False,placement_rotation_vendor_verified=False,physical_stack_verified=False,scope35_accepted=True,manufacturing_release=False,physical_tests='UNMEASURED'))
    print(json.dumps(dict(components=28,smt=26,th=2,needed_boards=6,scope35='PASS',native_export='PENDING',physical_stack='PENDING',pcb_sha256=PCB_HASH)))

if __name__=='__main__':main()
