"""Populate native candidate with exact devices, linked IDs and independently audited pads.

Carrier outline is provisional 140 x 100mm, not an enclosure or fabrication release.
Native importChanges returned success without populating this headless client;
this explicit device/pad method records every operation instead.
"""
import json
import time
from native_review import ROOT,PROJECT,invoke
from pcb_candidate import PCB

design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
pages=json.loads((ROOT/'pages.json').read_text())

def layout():
    pos={}
    def at(ref,x,y,r=0,axis=None):pos[ref]={'ref':ref,'x_mm':x,'y_mm':y,'rotation':r,'axis':axis}
    for lane in range(6):
        x=[25,70,115][lane%3];top=lane>=3
        def yy(y):return 100-y if top else y
        at(f'J{20+lane}',x,yy(4),axis='x')
        at(f'U{lane+1}',x,yy(22))
        at(f'R{lane+1}',x+13,yy(23),90)
        at(f'C{lane+1}',x+6,yy(22),90)
        for addr in range(14):at(f'R{100+lane*20+addr}',x-16.51+addr*2.54,yy(12),90)
        for i in range(2):at(f'C{100+lane*2+i}',x-10+i*20,yy(23),90)
        for i in range(4):at(f'D{1+lane*4+i}',x-14+i*9,yy(8))
    fixed={
     'J5':(38,38,0,'x'),'J6':(38,62,0,'x'),'J10':(136,44,0,'y'),'J11':(75,51,0,'y'),
     'J12':(123,52,0,'y'),'J13':(5,50,0,None),
     'U7':(53,50,0,None),'U8':(64,45,0,None),'U9':(64,56,0,None),'U10':(53,58,0,None),'U11':(72,65,0,None),
     'U12':(99,52,0,None),'U13':(88,60,0,None),'U14':(84,53,0,None),'U15':(83,43,0,None),
     'U16':(84,63,0,None),'U17':(26,50,0,None),'U18':(38,50,0,None),'Q1':(20,50,0,None),'F1':(13,50,0,None),
     'C7':(53,45,0,None),'C8':(64,40,0,None),'C9':(64,61,0,None),'C10':(53,63,0,None),'C11':(72,69,0,None),
     'C20':(100,44,0,None),'C21':(104,44,0,None),'C22':(94,44,0,None),
     'C23':(93,48,90,None),'C24':(105,48,90,None),'C25':(105,56,90,None),'C26':(105,61,0,None),
     'C27':(116,50,90,None),'C28':(116,54,90,None),'C30':(88,65,0,None),'C31':(88,57,0,None),
     'C32':(47,58,90,None),'C33':(81,57,0,None),'C34':(87,57,90,None),
     'C35':(88,43,90,None),'C36':(81,64,0,None),'C37':(23,45,0,None),'C38':(29,45,0,None),'C39':(38,45,0,None),
     'R30':(82,37,90,None),'R31':(85,37,90,None),'R32':(64,65,0,None),'R33':(58,66,90,None),'R34':(61,66,90,None),
     'R40':(94,60,90,None),'R41':(112,50,0,None),'R42':(112,54,0,None),
     'R60':(81,49,90,None),'R61':(87,49,90,None),'R62':(88,63,90,None),
     'R63':(58,43,0,None),'R64':(58,46,0,None),'R65':(58,49,0,None),
     'R66':(20,54,90,None),'R67':(27,54,0,None),'R68':(32,54,90,None),
     'R69':(32,50,90,None),'R70':(32,46,90,None),'SW1':(96,68,0,None)}
    for ref,v in fixed.items():at(ref,*v)
    for i in range(6):at(f'R{11+i}',44,44+i*2.5,0)
    for i in range(5):
        at(f'SW{i+2}',83+i*12,32)
        at(f'R{53+i}',83+i*12,28.5,0)
    for i in range(3):at(f'R{50+i}',89+i*6,76,0)
    assert set(pos)=={p['ref'] for p in design['parts']},(set(pos)^{p['ref'] for p in design['parts']})
    (ROOT/'pcb-placement-intent.json').write_text(json.dumps({'size_mm':[140,100],'provisional':True,'placements':list(pos.values())},indent=2)+'\n',encoding='utf-8')
    return pos

if __name__=='__main__':
    pos=layout()
    linked=invoke('v2-sch-link-ids',"""const r={};for(const id of __CLI__.args.pages){await eda.dmt_EditorControl.openDocument(id);for(const c of await eda.sch_PrimitiveComponent.getAll()){if(c.getState_SupplierId())r[c.getState_Designator()]=c.getState_UniqueId();}}return r;""",{'pages':list(pages.values())},150)
    (ROOT/'schematic-link-ids.json').write_text(json.dumps(linked,indent=2)+'\n',encoding='utf-8')
    assert set(linked)=={p['ref'] for p in design['parts']}
    code="""const pi=await eda.dmt_Project.getCurrentProjectInfo();if(pi.friendlyName!==__CLI__.args.name)throw new Error('Wrong project');await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const old=await eda.pcb_PrimitiveComponent.getAll();const out=[];
for(const p of __CLI__.args.items){let c=old.find(c=>c.getState_Designator()===p.ref);if(!c){c=await eda.pcb_PrimitiveComponent.create({libraryUuid:p.libraryUuid,uuid:p.uuid},1,p.px,p.py,p.rotation,false);if(!c)throw new Error('Create '+p.ref);c=await eda.pcb_PrimitiveComponent.modify(c,{designator:p.ref,uniqueId:p.link});}
if(c.getState_SupplierId()!==p.code)throw new Error('C-code mismatch '+p.ref);
let pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
if(p.axis){const xs=pads.map(q=>q.getState_X()),ys=pads.map(q=>q.getState_Y());const alongX=Math.max(...xs)-Math.min(...xs)>Math.max(...ys)-Math.min(...ys);if(alongX!==(p.axis==='x')){c=await eda.pcb_PrimitiveComponent.modify(c,{rotation:(c.getState_Rotation()+90)%360});pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());}}
const xs=pads.map(q=>q.getState_X()),ys=pads.map(q=>q.getState_Y());const cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
c=await eda.pcb_PrimitiveComponent.modify(c,{x:c.getState_X()+p.px-cx,y:c.getState_Y()+p.py-cy});pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
for(const q of pads){const n=q.getState_PadNumber();if(!(n in p.nets))throw new Error('Unexpected pad '+p.ref+'.'+n);const e=q.toAsync();e.setState_Net(p.nets[n]||'');await e.done();}
const nums=[...new Set(pads.map(q=>q.getState_PadNumber()))];if(nums.length!==Object.keys(p.nets).length)throw new Error('Missing pad '+p.ref);
out.push({ref:p.ref,pads:pads.length,uniqueId:c.getState_UniqueId()});}
if(!await eda.pcb_Document.save())throw new Error('Save');return out;"""
    for i in range(0,len(design['parts']),20):
        batch=[]
        for p in design['parts'][i:i+20]:
            q=pos[p['ref']]
            batch.append(dict(p,px=q['x_mm']/0.0254,py=q['y_mm']/0.0254,rotation=q['rotation'],axis=q['axis'],link=linked[p['ref']]))
        v=invoke(f'v2-pcb-populate-{i//20:02}',code,{'name':PROJECT.name,'pcb':PCB,'items':batch},150)
        print('PCB batch',i//20,len(v),'done',flush=True)
    # One closed provisional board outline; do not overwrite existing geometry.
    print(invoke('v2-pcb-outline',"""await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const all=await eda.pcb_PrimitivePolyline.getAll();if(!all.some(p=>p.getState_Layer()===11)){const polygon=eda.pcb_MathPolygon.createPolygon([0,0,'L',__CLI__.args.w,0,__CLI__.args.w,__CLI__.args.h,0,__CLI__.args.h,0,0]);await eda.pcb_PrimitivePolyline.create('',11,polygon,4,true);}await eda.pcb_Document.save();return {components:(await eda.pcb_PrimitiveComponent.getAll()).length,outline_mm:[140,100],provisional:true};""",{'pcb':PCB,'w':140/0.0254,'h':100/0.0254},120),flush=True)
