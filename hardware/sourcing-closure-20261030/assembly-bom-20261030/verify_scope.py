from pathlib import Path
import sys,json,csv,io,zipfile,hashlib,collections
D=Path(__file__).resolve().parent;R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else D.parents[2]
audit=json.loads((D/'BOM-SCOPE-AUDIT.json').read_text(encoding='utf-8'));inp=audit['inputs']
with zipfile.ZipFile(R/'hardware/delivery-baselines/20261029-r2-s1/control88-frozen-r2-20261029.zip') as z:b=z.read('control88-frozen-r2-20261029/manufacturing/Control88-R2-BOM.csv')
assert hashlib.sha256(b).hexdigest()==inp['C88_frozen_BOM_sha256'];base={f'C88.{r["Designator"]}':(r['LCSC'],r['MPN']) for r in csv.DictReader(io.StringIO(b.decode('utf-8-sig')))}
p=R/'hardware/sensor14-s2-20261030/Sensor14Bank-S2-BOM-FACTORY.csv';assert hashlib.sha256(p.read_bytes()).hexdigest()==inp['S2_BOM_sha256']
for row in csv.DictReader(p.open(encoding='utf-8-sig')):
 for bank in range(6):
  for ref in row['Designator'].split(','):base[f'B{bank}.{ref.strip()}']=(row['LCSC Part #'],row['Comment'])
sys.path.insert(0,str(R/'hardware/sensor14-s2-20261030/verification/support'));from native_documents import documents
p=R/'hardware/electrode-fullpanel-450-20261030/candidate/Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2';assert hashlib.sha256(p.read_bytes()).hexdigest()==inp['EP84_source_sha256'];docs=documents(p);libs={d['head']['uuid']:d for d in docs};board=next(d for d in docs if d['head']['docType']=='PCB');attrs=collections.defaultdict(dict)
for h,v in board['records']:
 if h['type']=='ATTR':attrs[v['parentId']][v['key']]=v['value']
ep={}
for h,v in board['records']:
 if h['type']!='COMPONENT':continue
 a=attrs[h['id']];assert v['layerId']==2
 m=next(v for h,v in libs[a['Device']]['records'] if h['type']=='META')['attributes'];assert m['Supplier Part']=='C22465876'
 ep['EP84.'+a['Designator']]=(m['Supplier Part'],m['Manufacturer Part'])
assert len(base)==256 and len(ep)==6
for name,alternative,include_ep in [('C88-S2x6-FROZEN-NET-38SKU-256pcs.csv',False,False),('C88-S2x6-ALT-C1591-QUOTE-37SKU-256pcs.csv',True,False),('C88-S2x6-EP84-SOURCE-QUOTE-38SKU-262pcs.csv',False,True)]:
 expected=dict(base)
 if alternative:expected={k:('C1591','CL10B104KB8NNNC') if k.startswith('C88.') and v[0]=='C14663' else v for k,v in expected.items()}
 if include_ep:expected.update(ep)
 found={};rows=list(csv.DictReader((D/name).open(encoding='utf-8')))
 for row in rows:
  refs=row['board_refs'].split(';');assert len(refs)==int(row['net_quantity_only'])
  assert int(row['C88_qty'])==sum(r.startswith('C88.') for r in refs)
  assert int(row['six_S2_qty'])==sum(r.startswith('B') for r in refs)
  assert int(row['EP84_header_qty'])==sum(r.startswith('EP84.') for r in refs)
  for ref in refs:assert ref not in found;found[ref]=(row['LCSC'],row['MPN'])
 assert found==expected,name
 assert len(rows)==len({v[0] for v in expected.values()})
print(json.dumps({'status':'PASS_ALL_BOARD_REFS_AND_MPN_COUNTS_AGAINST_NATIVE_AND_FROZEN_INPUTS','frozen_net_parts':256,'frozen_SKUs':38,'quote_option_SKUs':37,'including_EP84_net_parts':262,'native_source_changed':False,'manufacturing_release':False}))
