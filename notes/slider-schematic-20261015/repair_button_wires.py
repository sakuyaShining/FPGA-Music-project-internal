"""Recreate button stubs after all placement is final, avoiding drag auto-merges."""
import json
from phase import ROOT,invoke
contract=json.loads((ROOT/'expected-pin-nets.json').read_text())
code="""await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const all=await eda.sch_PrimitiveWire.getAll();const remove=[];
for(const w of all){const l=w.getState_Line();const segments=typeof l[0]==='number'?[l]:l;if(segments.every(s=>s.every((v,i)=>i%2===0?v>=330&&v<=1120:(v===220||v===250))))remove.push(w.getState_PrimitiveId());}
if(!remove.length)throw new Error('No button wire region');await eda.sch_PrimitiveWire.delete(remove);const made=[];
for(const c of await eda.sch_PrimitiveComponent.getAll()){const ref=c.getState_Designator();if(!['SW2','SW3','SW4','SW5','SW6'].includes(ref))continue;
for(const p of await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())){const n=p.getState_PinNumber(),x=p.getState_X(),y=p.getState_Y(),r=p.getState_Rotation();const dx=r===0?30:-30;const net=__CLI__.args.contract[ref][n];const w=await eda.sch_PrimitiveWire.create([x,y,x+dx,y],net);if(!w)throw new Error('Failed button wire');made.push({ref,n,net,id:w.getState_PrimitiveId(),x,y});}}
return {removed:remove,made,saved:await eda.sch_Document.save()};"""
v=invoke('repaired-final-button-wires',code,{'contract':contract});print('removed',len(v['removed']),'created',len(v['made']),'saved',v['saved'])
