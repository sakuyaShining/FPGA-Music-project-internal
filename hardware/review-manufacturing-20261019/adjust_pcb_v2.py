"""Resolve first-pass copper clearances and shorten PCM5122 local loops."""
import json
import sys
from native_review import ROOT,invoke
from pcb_candidate import PCB

targets={
 'U7':(53,49,0),'U10':(53,57,0),'C7':(53,43.5,0),'C9':(71,57,0),'C10':(49,57,0),'C32':(47,66,90),
 'C34':(81,53,90),'C36':(81,67,0),'R63':(57.5,40,0),'R64':(57.5,42,0),'R65':(57.5,44,0),
 'C20':(96,46.8,90),'C21':(98.5,46.8,90),'C22':(96,57,0),'C24':(101.5,46.6,90),
 'C25':(102,57.5,0),'R40':(98.6,58,90),'R41':(110,44.5,0),'R42':(110,42.5,0),
 'C27':(114,44.5,90),'C28':(114,42,90),'J12':(123,43.5,None),
 'R50':(108,64,0),'R51':(108,67,0),'R52':(108,70,0)}
for lane in range(6):
    x=[25,70,115][lane%3];y=88 if lane>=3 else 12
    for addr in range(14):targets[f'R{100+lane*20+addr}']=(x-19.05+addr*2.54,y,90)

# Second pass uses actual native device envelopes with a 0.5mm device clearance.
targets.update({
 'J10':(128,44,None),'J11':(128,76,None),'U10':(52,56.5,90),
 'C8':(71.5,42,0),'C9':(72,57,0),'C10':(45.8,59,0),
 'U13':(117,62,0),'C30':(111.5,61,0),'C31':(122,62,0),
 'C20':(96,46.2,90),'C21':(98.5,46.2,90),'C24':(101.5,46.2,90),
 'C23':(92.5,49,90),'C22':(95.5,57.3,0),'R40':(107,59,90),
 'C27':(115,47,90),'C28':(115,42,90),
 'C33':(79.2,57.8,0),'C34':(79.5,53,90),'R60':(78,49,90),
 'R63':(47,32,0),'R64':(51,32,0),'R65':(55,32,0),
 'R30':(77,39,90),'R31':(88,38.6,90),'R6':(125,73,90)})
for i in range(5):
    targets[f'SW{i+2}']=(77+i*11,33,0)
    targets[f'R{53+i}']=(77+i*11,28,0)
for lane in range(3):targets[f'U{lane+1}']=([25,70,115][lane],22,180)
for lane in range(3,6):
    x=[25,70,115][lane%3]
    for addr in range(14):targets[f'R{100+lane*20+addr}']=(x-19.05+addr*2.54,88,270)
targets.update({'J10':(128,36,None),'J11':(128,68,None),'R3':(125,27,90),
                'C23':(92.4,49,90),'R40':(108,58,90),'R71':(78,62.5,0)})

code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const old=await eda.pcb_PrimitiveComponent.getAll();const out=[];
for(const p of __CLI__.args.items){let c=old.find(c=>c.getState_Designator()===p.ref);if(!c)throw new Error('Missing '+p.ref);if(p.rotation!==null)c=await eda.pcb_PrimitiveComponent.modify(c,{rotation:p.rotation});const pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());const xs=pads.map(q=>q.getState_X()),ys=pads.map(q=>q.getState_Y());const x=(Math.min(...xs)+Math.max(...xs))/2,y=(Math.min(...ys)+Math.max(...ys))/2;await eda.pcb_PrimitiveComponent.modify(c,{x:c.getState_X()+p.x-x,y:c.getState_Y()+p.y-y});out.push(p.ref);}await eda.pcb_Document.save();return out;"""
items=[dict(ref=r,x=x/.0254,y=y/.0254,rotation=a) for r,(x,y,a) in targets.items() if len(sys.argv)==1 or r in sys.argv[1:]]
for i in range(0,len(items),20):
    print(invoke(f'v2-pcb-adjust-{i//20}',code,{'pcb':PCB,'items':items[i:i+20]},150),flush=True)
intent=json.loads((ROOT/'pcb-placement-intent.json').read_text())
for p in intent['placements']:
    if p['ref'] in targets:
        x,y,a=targets[p['ref']];p.update(x_mm=x,y_mm=y)
        if a is not None:p['rotation']=a
(ROOT/'pcb-placement-intent.json').write_text(json.dumps(intent,indent=2)+'\n',encoding='utf-8')
