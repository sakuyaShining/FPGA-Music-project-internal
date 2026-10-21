"""Incremental rail-bleed addition; preserve every existing schematic/PCB association."""
import json
from build_review import schema,parts,PAGES,place
from native_review import ROOT,PROJECT,invoke
from pcb_candidate import PCB

schema()
page=PAGES[13]
new=[p for p in parts if p['ref'] in ['R71','R72','R73']]
place(page)  # Existing references are read, never deleted or recreated.
ids=json.loads((ROOT/'pages.json').read_text())
v=invoke('v2-append-rail-bleed-wires',"""if(!await eda.dmt_EditorControl.openDocument(__CLI__.args.page))throw new Error('No sheet');
let f=await eda.sch_ManufactureData.getNetlistFile('before-bleed','JLCEDA');const before=JSON.parse(await f.text());const cs=await eda.sch_PrimitiveComponent.getAll();const links={};
for(const p of __CLI__.args.parts){const c=cs.find(c=>c.getState_Designator()===p.ref);if(!c)throw new Error('Missing '+p.ref);links[p.ref]=c.getState_UniqueId();const info=before.components[c.getState_UniqueId()]?.pinInfoMap||{};
for(const q of await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())){const num=q.getState_PinNumber(),net=p.nets[num];if(info[num]?.net===net)continue;const x=q.getState_X(),y=q.getState_Y(),r=q.getState_Rotation(),dx=r===0?80:r===180?-80:0,dy=r===90?80:r===270?-80:0;
if(!dx&&!dy)throw new Error('Pin rotation');await eda.sch_PrimitiveWire.create([x,y,x+dx,y+dy],net);await eda.sch_PrimitiveComponent.createNetPort('BI',net,x+dx,y+dy,r);}}
await eda.sch_Document.save();f=await eda.sch_ManufactureData.getNetlistFile('after-bleed','JLCEDA');return {links,netlist:await f.text()};""",{'page':ids[page],'parts':new},180)
(ROOT/'v2-sch-netlist.json').write_text(v['netlist'],encoding='utf-8')
source=json.loads(v['netlist'])['components']
netfile=PROJECT/'review-exports/v2-schematic-netlist.json';netfile.write_text(v['netlist'],encoding='utf-8')
targets={'R71':(78,62.5),'R72':(121,58),'R73':(29,58)}
batch=[]
for p in new:
    uid=v['links'][p['ref']];x,y=targets[p['ref']]
    batch.append(dict(p,link=uid,channel=source[uid]['props']['Channel ID'],px=x/.0254,py=y/.0254))
w=invoke('v2-append-pcb-rail-bleeds',"""if(!await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb))throw new Error('No PCB');const lineCount=(await eda.pcb_PrimitiveLine.getAll()).length;const old=await eda.pcb_PrimitiveComponent.getAll();
for(const p of __CLI__.args.parts){let c=old.find(q=>q.getState_Designator()===p.ref);if(!c)c=await eda.pcb_PrimitiveComponent.create({libraryUuid:p.libraryUuid,uuid:p.uuid},1,p.px,p.py,0,false);if(!c||c.getState_SupplierId()!==p.code)throw new Error('Device '+p.ref);
c=await eda.pcb_PrimitiveComponent.modify(c,{designator:p.ref,uniqueId:p.link,otherProperty:{...c.getState_OtherProperty(),'Channel ID':p.channel}});let pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());const xs=pads.map(q=>q.getState_X()),ys=pads.map(q=>q.getState_Y());c=await eda.pcb_PrimitiveComponent.modify(c,{x:c.getState_X()+p.px-(Math.min(...xs)+Math.max(...xs))/2,y:c.getState_Y()+p.py-(Math.min(...ys)+Math.max(...ys))/2});pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
for(const q of pads){const e=q.toAsync();e.setState_Net(p.nets[q.getState_PadNumber()]);await e.done();}}
const f=await eda.sys_FileSystem.readFileFromFileSystem(__CLI__.args.netfile);if(!await eda.pcb_Net.setNetlist('JLCEDA',await f.text()))throw new Error('Netlist sync');await eda.pcb_Document.save();if((await eda.pcb_PrimitiveLine.getAll()).length!==lineCount)throw new Error('Existing copper changed');return {components:(await eda.pcb_PrimitiveComponent.getAll()).length,lines_preserved:lineCount,netlist:await eda.pcb_Net.getNetlist('JLCEDA')};""",{'pcb':PCB,'parts':batch,'netfile':netfile.as_posix()},180)
(ROOT/'v2-pcb-netlist.json').write_text(w.pop('netlist'),encoding='utf-8')
intent=json.loads((ROOT/'pcb-placement-intent.json').read_text())
existing={p['ref'] for p in intent['placements']}
for ref,(x,y) in targets.items():
    if ref not in existing:intent['placements'].append(dict(ref=ref,x_mm=x,y_mm=y,rotation=0,axis=None))
(ROOT/'pcb-placement-intent.json').write_text(json.dumps(intent,indent=2)+'\n',encoding='utf-8')
links=json.loads((ROOT/'schematic-link-ids.json').read_text());links.update(v['links'])
(ROOT/'schematic-link-ids.json').write_text(json.dumps(links,indent=2)+'\n',encoding='utf-8')
print('Incremental bleeds, existing copper retained:',w,flush=True)
