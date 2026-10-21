"""Audit saved/reopened native copper and archive the 74-open local exchange."""
import hashlib,json,math,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union
from resume_offline import read_native
from physical_geometry import connected_subset
from native_review import PROJECT
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
old=read_native(OUT/'before-native.epcb2');PCB=PROJECT/'pcb/PCB1.epcb2';new=read_native(PCB)
plan=read(OUT/'local-power-bus-with-return-plan.json');cap=read(OUT/'verified-source-74.json')
drc_path=ROOT/'drc-stage-local-power-bus-r3.json';meta_path=ROOT/'drc-stage-local-power-bus-r3.meta.json'
drc=read(drc_path);meta=read(meta_path);assert meta['source_stable_during_drc'] and sha(PCB)==meta['pcb_sha256_after']
counts={c['name']:c.get('count',0) for c in drc}
assert counts.get('Clearance Error',0)==0 and counts.get('Physics Error',counts.get('Physical Error',0))==0
assert counts['Connection Error']==74
pending=[n['name'] for c in drc if c['name']=='Connection Error' for n in c['list']]
previous=read(ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json')
assert set(pending)==set(previous['pending_nets'])-{'5V_PERIPH'}
for kind in ['COMPONENT','ATTR','PAD','REGION','STRING','NET','PAD_NET','RULE','RULE_SELECTOR','POUR']:
    assert {i:p for (k,i),p in old.items() if k==kind}=={i:p for (k,i),p in new.items() if k==kind},kind
oldlines=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width'])
    for (k,i),p in old.items() if k=='LINE' and p.get('layerId') in [1,2]]
newlines=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width'])
    for (k,i),p in new.items() if k=='LINE' and p.get('layerId') in [1,2]]
expected=[p for p in oldlines if p['id'] not in plan['remove_line_ids']]+plan['additive_power_lines']+plan['bus_lines']+plan['ground_lines']
shape=lambda ls:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32) for p in ls])
geometry=[]
for net in ['5V_PERIPH','BUS_RETURN','GND']:
    for layer in [1,2]:
        a=shape([p for p in expected if p['net']==net and p['layer']==layer]);b=shape([p for p in newlines if p['net']==net and p['layer']==layer])
        missing=a.difference(b.buffer(.000005));extra=b.difference(a.buffer(.000005))
        assert missing.is_empty and extra.is_empty,(net,layer,missing.area,extra.area)
        geometry.append(dict(net=net,layer=layer,expected_and_native_copper_equivalent=True))
unselected={i:p for (k,i),p in old.items() if k=='LINE' and p.get('netName') not in ['5V_PERIPH','BUS_RETURN','GND']}
assert all(new['LINE',i]==p for i,p in unselected.items())
oldvias={i:p for (k,i),p in old.items() if k=='VIA'};newvias={i:p for (k,i),p in new.items() if k=='VIA'}
assert all(newvias[i]==p for i,p in oldvias.items()) and len(newvias)==len(oldvias)+4
actual_vias=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for i,p in newvias.items()]
for net in ['5V_PERIPH','BUS_RETURN']:
    assert connected_subset([p for p in cap['pads'] if p['net']==net],[p for p in newlines if p['net']==net],[p for p in actual_vias if p['net']==net])['complete'],net
micro=[p for p in newlines if p['id'] not in {p['id'] for p in cap['lines']}]
assert len(micro)==28 and max(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in micro)<=.003
descriptor=PROJECT/(PROJECT.name+'.eprj3')
audit=read(OUT/'apply-audit.json')
with zipfile.ZipFile(Path(audit['snapshot'])/'native-quality-r1-before-local-exchange.zip') as z:prior=json.loads(z.read(descriptor.name))
current=read(descriptor);descriptor_changes=[]
def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a.keys()|b.keys():differences(a.get(k),b.get(k),path+'/'+k)
    elif a!=b:descriptor_changes.append(dict(path=path,before=a,after=b))
differences(prior,current)
assert {c['path'] for c in descriptor_changes}=={'/profile/pcbs/c3fd8656cf425e9f/version','/profile/pcbs/c3fd8656cf425e9f/updateTime'}
assert all(sha(PROJECT/p)==h for p,h in previous['files'].items() if p not in ['pcb/PCB1.epcb2',descriptor.name])
delivery=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
archive=delivery/'native-230-0clear-74open-local-power-bus-r3-20261021-CANDIDATE.zip'
assert not archive.exists(),'Do not overwrite an existing native checkpoint'
files={p:sha(PROJECT/p) for p in previous['files']}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(PROJECT/p,p)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and set(z.namelist())==set(files)
    assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in files.items())
checkpoint=dict(components=230,lines=len(cap['lines']),native_copper_line_records=len(newlines),native_microtracks=len(micro),
    vias=len(newvias),pads=len(cap['pads']),poured=2,clearance_errors=0,physical_errors=0,unconnected_errors=74,
    pending_nets=pending,power_net_closed=True,all_mux_and_rc_signal_nets_closed=True,
    manufacturing_release=False,native_zip=str(archive),native_zip_sha256=sha(archive),
    drc_stage='local-power-bus-r3',drc_sha256=sha(drc_path),pcb_sha256=sha(PCB),files=files,
    previous_checkpoint='route-checkpoint-0clear-78open-quality-r1-20261021.json',
    source_capture='joint-routing-20261021-r3/verified-source-74.json',source_capture_sha256=sha(OUT/'verified-source-74.json'),
    note='API line count after reopen is 3262; 28 native microtracks remain real copper and must be included in later geometry planning.')
name='route-checkpoint-0clear-74open-local-power-bus-r3-20261021.json'
save(ROOT/name,checkpoint);save(delivery/'CURRENT-CHECKPOINT.json',checkpoint)
state=dict(updated_utc=datetime.now(timezone.utc).isoformat(),checkpoint=name,source_capture=checkpoint['source_capture'],
    drc_file=drc_path.name,pcb_sha256=sha(PCB),unconnected_errors=74,manufacturing_release=False)
save(ROOT/'CURRENT-STATE.json',state);save(delivery/'CURRENT-STATE.json',state)
verification=dict(native_geometry_checks=geometry,native_components_pads_attributes_nets_rules_pour_definitions_unchanged=True,
    other_17_project_files_unchanged=True,descriptor_changes_only_pcb_save_metadata=descriptor_changes,
    original_529_vias_preserved=True,new_vias=4,both_power_and_bus_return_complete=True,
    full_native_drc=counts,native_drc_source_stable=True,archive_crc_and_19_hashes_verified=True,
    checkpoint_sha256=sha(ROOT/name),manufacturing_release=False)
save(OUT/'final-verification.json',verification)
print(json.dumps(dict(checkpoint=name,pcb_sha256=sha(PCB),api_lines=len(cap['lines']),native_microtracks=len(micro),
    vias=len(newvias),unconnected_errors=74,native_zip=str(archive),native_zip_sha256=sha(archive),manufacturing_release=False),indent=2))
