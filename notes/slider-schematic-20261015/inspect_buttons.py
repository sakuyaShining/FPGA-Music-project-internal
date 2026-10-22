import json
from phase import ROOT,invoke
pins=json.loads((ROOT/'evidence/wired-core.json').read_text())['value']['pins']
pins=[p for p in pins if p['ref'] in ['SW2','SW5','SW6']]
print(json.dumps(invoke('button-position-check',"await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const all=await eda.sch_PrimitiveComponent.getAll();const r=[];for(const p of __CLI__.args.pins){const c=all.find(c=>c.getState_Designator()===p.ref);const pp=(await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())).find(q=>q.getState_PinNumber()===p.pin);const w=await eda.sch_PrimitiveWire.get(p.wire);const port=await eda.sch_PrimitiveComponent.get(p.label);r.push({ref:p.ref,n:p.pin,x:pp.getState_X(),y:pp.getState_Y(),wire:p.wire,line:w?.getState_Line(),net:w?.getState_Net(),port:{x:port.getState_X(),y:port.getState_Y(),r:port.getState_Rotation()}});}return r;",{'pins':pins}),ensure_ascii=True))
