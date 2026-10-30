"""Read exact frozen archive. Instance attributes override embedded device defaults."""
from pathlib import Path
import json,csv,io,hashlib,zipfile,collections,sys
D=Path(__file__).resolve().parent;R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else D.parents[1]
Z=R/'hardware/delivery-baselines/20261029-r2-s1/control88-frozen-r2-20261029.zip';prefix='control88-frozen-r2-20261029/'
def sha(b):return hashlib.sha256(b).hexdigest()
def docs(data):
 result=[];current=None
 for line in data.decode('utf-8-sig').splitlines():
  if not line.strip():continue
  h,v=line.split('||',1);h=json.loads(h);v=v[:-1] if v.endswith('|') else v
  if not v.strip():continue
  v=json.loads(v)
  if h['type']=='DOCHEAD':current={'head':v,'records':[]};result.append(current)
  current['records'].append((h,v))
 return result
def components(documents,typ):
 libs={d['head']['uuid']:d for d in documents};out={}
 for d in documents:
  if d['head']['docType']!=typ:continue
  attrs=collections.defaultdict(dict);component_attrs={h['id']:v.get('attrs',{}) for h,v in d['records'] if h['type']=='COMPONENT'}
  for h,v in d['records']:
   if h['type']=='ATTR':attrs[v.get('parentId')][v['key']]=v.get('value')
  for cid,a in attrs.items():
   ref=a.get('Designator')
   if not ref or not a.get('Device'):continue
   device=libs[a['Device']];metadata=next(v for h,v in device['records'] if h['type']=='META');default=metadata['attributes']
   a={**component_attrs.get(cid,{}),**a}
   resolved={**default,**a};out[ref]={'component':cid,'instance':a,'device_defaults':default,'resolved':resolved}
 return out
with zipfile.ZipFile(Z) as z:
 manifest=json.loads(z.read(prefix+'MANIFEST.json'));input_hashes={}
 # Verify the original published archive, including exact schematic attributes.
 for n,s in manifest['files_sha256'].items():assert sha(z.read(prefix+n))==s,n
 q='source/pcb/PCB1.epcb2';pcbdata=z.read(prefix+q);assert sha(pcbdata)=='733e1d9c33d11ef946863dca0bc9f36ae2916b9965d038b147aafea416194eb8';input_hashes[q]=sha(pcbdata)
 pc=components(docs(pcbdata),'PCB');sch={};sheet_of={}
 for n in z.namelist():
  if not n.endswith('.esch2'):continue
  data=z.read(n);cc=components(docs(data),'SCH_PAGE');assert not(set(cc)&set(sch));sch.update(cc);sheet_of.update({k:n[len(prefix):] for k in cc});input_hashes[n[len(prefix):]]=sha(data)
 bompath='manufacturing/Control88-R2-BOM.csv';bomdata=z.read(prefix+bompath);input_hashes[bompath]=sha(bomdata);bom={v['Designator']:v for v in csv.DictReader(io.StringIO(bomdata.decode('utf-8-sig')))}
assert len(bom)==len(pc)==len(sch)==88
differences=[]
for ref,v in bom.items():
 for source,data in [('PCB',pc[ref]),('SCH_PAGE',sch[ref])]:
  a=data['resolved']
  for field,key in [('LCSC','Supplier Part'),('MPN','Manufacturer Part')]:
   if v[field]!=a[key]:differences.append({'ref':ref,'source':source,'field':field,'BOM':v[field],'resolved':a[key]})
assert not differences,differences
refs=['C8','C9','C10','C11','C22','C23','C24','C25','C33','C34','C35','C36','CX1'];rows=[]
for ref in refs:
 a=sch[ref];resolved=a['resolved'];defaults=a['device_defaults'];p=pc[ref]['resolved']
 assert resolved['Supplier Part']==p['Supplier Part']==bom[ref]['LCSC']=='C14663'
 assert resolved['Manufacturer Part']==p['Manufacturer Part']==bom[ref]['MPN']=='CC0603KRX7R9BB104'
 assert defaults['Supplier Part']=='C1591'
 rows.append({'designator':ref,'sheet':sheet_of[ref],'schematic_instance_supplier':a['instance']['Supplier Part'],'schematic_instance_MPN':a['instance']['Manufacturer Part'],'schematic_device_default_supplier':defaults['Supplier Part'],'schematic_device_default_MPN':defaults['Manufacturer Part'],'PCB_resolved_supplier':p['Supplier Part'],'PCB_resolved_MPN':p['Manufacturer Part'],'BOM_supplier':bom[ref]['LCSC'],'BOM_MPN':bom[ref]['MPN'],'stale_datasheet_URL':resolved.get('Datasheet'),'footprint_uuid_same':a['instance']['Footprint']==pc[ref]['instance']['Footprint']})
 assert rows[-1]['footprint_uuid_same']
assert all('CL10B104KB8NNNC' in r['stale_datasheet_URL'] for r in rows)
out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);(D/'CONTROL88-CAP-13-READBACK.csv').write_bytes(out.getvalue().encode())
report={'schema':1,'status':'PASS_FROZEN_R2_88_BOM_PCB_SCHEMATIC_RESOLVED_IDENTITIES','archive_relative_to_repo':Z.relative_to(R).as_posix(),'archive_sha256':sha(Z.read_bytes()),'all_original_manifest_file_hashes_pass':True,'PCB_sha256':sha(pcbdata),'components_checked':88,'identity_mismatches':differences,'affected_capacitors':refs,'all13_instance_overrides_C14663':True,'all13_PCB_BOM_C14663':True,'all13_embedded_schematic_device_defaults_C1591':True,'all13_same_footprint_uuid':True,'stale_datasheet_URL_count':13,'conclusion':'The13 alleged BOM-vs-schematic component mismatches are not present in the frozen R2 resolved instance attributes. They arise from comparing embedded original device defaults/datasheet links with already-overridden actual instances. No new part substitution was performed. Datasheet links/default metadata remain stale documentation.','supplier_availability_and_quote':'PENDING; snapshots are separate from actual assembly reservation','source_edits':[],'manufacturing_release':False,'inputs':input_hashes,'evidence':{'readback_csv_sha256':sha((D/'CONTROL88-CAP-13-READBACK.csv').read_bytes())}}
(D/'CONTROL88-IDENTITY-AUDIT.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in report.items() if k!='inputs'}))
