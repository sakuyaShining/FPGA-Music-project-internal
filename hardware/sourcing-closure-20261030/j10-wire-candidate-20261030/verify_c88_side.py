from pathlib import Path
import csv,json,sys,zipfile,hashlib
D=Path(__file__).resolve().parent;R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else D.parents[2]
zpath=R/'hardware/delivery-baselines/20261029-r2-s1/control88-frozen-r2-20261029.zip'
with zipfile.ZipFile(zpath) as z:b=z.read('control88-frozen-r2-20261029/source/pcb/PCB1.epcb2')
assert hashlib.sha256(b).hexdigest()=='733e1d9c33d11ef946863dca0bc9f36ae2916b9965d038b147aafea416194eb8'
records=[];pcb=False
for line in b.decode('utf-8-sig').splitlines():
 if not line.strip():continue
 h,v=line.split('||',1);h=json.loads(h);v=v[:-1] if v.endswith('|') else v
 if not v.strip():continue
 v=json.loads(v)
 if h['type']=='DOCHEAD':pcb=v['docType']=='PCB'
 if pcb:records.append((h,v))
cid=next(v['parentId'] for h,v in records if h['type']=='ATTR' and v['key']=='Designator' and v['value']=='J10')
nets={int(json.loads(h['id'])[2]):v['padNet'] for h,v in records if h['type']=='PAD_NET' and json.loads(h['id'])[1]==cid}
rows=list(csv.DictReader((D/'J10-TO-MODULE-CANDIDATE-NOT-RELEASED.csv').open(encoding='utf-8')));assert len(rows)==12 and {int(r['C88_pin']) for r in rows}==set(range(1,13))
seen=set()
for row in rows:
 pin=int(row['C88_pin']);assert row['C88_connector']=='J10' and row['C88_net']==nets[pin]
 targets={int(n) for n in row['module_pins_candidate'].split(',') if n}
 assert not (seen&targets);seen.update(targets)
 if pin==7:assert not targets and row['status']=='HOLD_RESET_BREAKOUT'
 else:assert targets and row['status']=='INDEXED_DOCUMENT_CANDIDATE_VENDOR_CONFIRMATION_REQUIRED'
 if row['C88_net']=='5V_PERIPH':assert targets=={3,4,37,38}
 if row['C88_net']=='GND':assert targets<={1,2,13,31,39,40}
assert 11 not in seen and 12 not in seen and 32 not in seen
v=json.loads((D/'SOURCE-AND-OPEN-ITEMS.json').read_text(encoding='utf-8'));assert not v['full_PDF_visual_review'] and not v['vendor_confirmation_received'] and not v['wire_continuity_tested'] and not v['manufacturing_release']
print(json.dumps({'status':'PASS_C88_SIDE_AND_STRUCTURAL_GUARDS_ONLY','C88_pins_checked':12,'display_reset_target_assigned':False,'unconfirmed_pin11_left_unconnected':True,'module_document_connector_name_and_FT5316_confirmation':'PENDING','full_pinmap_or_physical_assembly_acceptance':False,'manufacturing_release':False}))
