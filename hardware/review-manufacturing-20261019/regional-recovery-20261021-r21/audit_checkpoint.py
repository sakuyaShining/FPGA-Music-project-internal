"""Audit actual saved copper against each declared edit stage and preserve a checkpoint."""
from pathlib import Path
import sys,json,hashlib,zipfile,math
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;R22=ROOT/'regional-corridor-routing-20261021-r22';R23=ROOT/'regional-net-rebuild-20261021-r23'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from four_layer_geometry import connected
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class TextSource:
    def __init__(self,s):self.s=s
    def read_text(self,encoding):return self.s
def archived(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        return read_native(TextSource(z.read('pcb/PCB1.epcb2').decode('utf8')))
source=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');final=read_native(PROJECT/'pcb/PCB1.epcb2')
meta=read(R23/'checkpoint-meta.json');cap=read(R23/'checkpoint-capture.json');assert sha(PROJECT/'pcb/PCB1.epcb2')==meta['pcb_sha256']
assert all(sha(Path(info['source_project'])/rel)==h for rel,h in info['source_files'].items())
stable=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');assert all(sha(Path(stable['project'])/rel)==h for rel,h in stable['files'].items())
for k,p in source.items():
    if k[0] not in ['DOCHEAD','LINE','VIA','POURED']:assert final[k]==p,('Non-copper changed',k)
protected=lambda p:p.startswith('I2S_') or __import__('re').fullmatch(r'RC[0-5]',p) or __import__('re').match(r'L[0-5]_',p)
assert {k:p for k,p in source.items() if k[0] in ['LINE','VIA'] and protected(p.get('netName',''))}=={k:p for k,p in final.items() if k[0] in ['LINE','VIA'] and protected(p.get('netName',''))}
def lines(doc):return {i:dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in doc.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]}
def grouped(data):
    groups={}
    for p in data.values():groups.setdefault((p['net'],p['layer']),[]).append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32))
    return {k:unary_union(v) for k,v in groups.items()}
snap1=archived(BASE/'before-r31-power.zip');snap2=archived(BASE/'before-power-corridor.zip');snap3=archived(R23/'before-combined.zip')
before_ground=archived(BASE/'native-r21-after-r23-WORK-IN-PROGRESS.zip')
stages=[('initial_signal_and_power',source,snap1,[read(BASE/'accepted-batch.json')]),('r31_branch',snap1,snap2,[read(BASE/'r31-power-plan.json')]),('supply_corridor_and_display_mosi',snap2,snap3,[read(BASE/'power-corridor-plan.json'),read(R22/'accepted-complete-copper.json')]),('reset_and_complete_supplies',snap3,before_ground,[read(R23/'combined-plan.json')]),('explicit_ground_pad_repair',before_ground,final,[read(R23/'ground-pad-repair-plan.json')])]
reconciled=[]
for name,before,after,plans in stages:
    expected=lines(before);counter=0
    for plan in plans:
        for p in plan.get('remove_lines',[]):assert p['id'] in expected,(name,p['id']);del expected[p['id']]
        for p in plan['lines']:expected['added-'+str(counter)]=p;counter+=1
    e=grouped(expected);a=grouped(lines(after));assert set(e)==set(a),(name,'net/layer groups differ')
    errors=[];worst=0
    for key in e:
        distance=e[key].hausdorff_distance(a[key]);worst=max(worst,distance)
        # Account for the native editor's observed 0.0000254mm cleanup rounding.
        outside=e[key].difference(a[key].buffer(.00006)).area+a[key].difference(e[key].buffer(.00006)).area
        if outside>1e-6:errors.append(dict(net=key[0],layer=key[1],outside_area_mm2=outside,hausdorff_mm=distance))
    assert not errors,(name,errors)
    reconciled.append(dict(stage=name,actual_copper_matches_declared=True,max_hausdorff_mm=worst,tolerance_mm=.00006))
counts={x['name']:x['count'] for x in read(R23/'checkpoint-drc.json')};assert set(counts)<= {'Connection Error'},counts
assert all(n['name']!='GND' for g in read(R23/'checkpoint-drc.json') for n in g['list']),'Ground disconnections remain'
netproof={}
ls=list(lines(final).values())
for net in ['3V3_IO','3V3_PERIPH','VIS_CS_N','VIS_BL_EN','DISP_MOSI','TP_RESET_N','DISP_SCK']:
    netproof[net]=connected([p for p in cap['pads'] if p['net']==net],[p for p in ls if p['net']==net],[p for p in cap['vias'] if p['net']==net]);assert netproof[net]['complete'],net
planes=poured_planes(final);oldplanes=poured_planes(source);contacts=[]
ground_ids=set(read(BASE/'native-batch-ground-apply.json')['createdV'])|set(read(R22/'native-ground-apply.json')['createdV'])|set(read(R23/'native-ground-apply.json')['createdV'])|set(read(R23/'native-ground-pad-repair.json')['createdV'])
for p in cap['vias']:
    if p['id'] not in ground_ids:continue
    q=Point(p['x']*.0254,p['y']*.0254);ring=q.buffer(p['diameter']*.0254/2,quad_segs=48).difference(q.buffer(p['hole']*.0254/2,quad_segs=48));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]};assert min(areas.values())>=.15
    contacts.append(dict(id=p['id'],actual_contact_mm2=areas))
audio=[]
for net in ['I2S_BCK','I2S_DIN','I2S_LRCK']:
    excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in cap['vias'] if p['net'] in ['I2S_BCK','I2S_DIN','I2S_LRCK']]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['layer']==12 and p['net'] in ['I2S_BCK','I2S_DIN','I2S_LRCK']])
    traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in ls if p['net']==net and p['layer']==2];length=sum(q.length for q in traces)
    before=sum(q.intersection(oldplanes[16]).length for q in traces)/length;after=sum(q.intersection(planes[16]).length for q in traces)/length;assert after>=before-1e-6,(net,before,after)
    audio.append(dict(net=net,before_fraction=before,after_fraction=after,si_signoff=False))
remaining=[dict(net=n['name'],objects=len(n['list'])) for g in read(R23/'checkpoint-drc.json') if g['name']=='Connection Error' for n in g['list']]
archive=BASE/'native-r21-after-r23-ground-repair-WORK-IN-PROGRESS.zip'
assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in PROJECT.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
result=dict(pcb_sha256=meta['pcb_sha256'],source_R19_files_unchanged=True,stable_R15_files_unchanged=True,components_pads_rules_stackup_outline_net_membership_unchanged=True,audio_and_sensor_copper_unchanged=True,copper_reconciliation=reconciled,native_drc=counts,continuity=netproof,new_ground_stitches=len(contacts),actual_ground_contacts=contacts,audio_reference_projection=audio,remaining_nets=remaining,vias=len(cap['vias']),pads=len(cap['pads']),native_lines=len(ls),archive=str(archive),archive_sha256=sha(archive),manufacturing_release=False,status='regional_construction_checkpoint_not_promoted_over_R15',limitations=['Remaining nets are not routed; original R15 remains the stable routing checkpoint','Reference-plane projections and nearby stitches are geometric evidence, not signal/power integrity or sensor qualification','TP_RESET_N is a 66.87mm, four-via construction route; optimize before release','Factory stackup, mechanical fit, actual hardware tests, final CPL and final firmware remain open'])
(BASE/'checkpoint-review.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k not in ['actual_ground_contacts','audio_reference_projection']},indent=2),flush=True)
