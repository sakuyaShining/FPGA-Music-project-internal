
const a=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==a.project||doc?.documentType!==3)throw new Error('Wrong PCB');await eda.pcb_Drc.stopRealTimeDrc();const createdL=[],createdV=[];
try{
await eda.pcb_PrimitiveLine.delete(a.remove_lines.map(p=>p.id));await eda.pcb_PrimitiveVia.delete(a.remove_vias.map(p=>p.id));
for(const p of a.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via creation');createdV.push(q.getState_PrimitiveId());}
for(const p of a.lines){if(![1,16,2].includes(p.layer))throw new Error('Unexpected layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line creation');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {ok:true,createdL,createdV};
}catch(e){return {ok:false,error:String(e),createdL,createdV,partial_native_state_requires_review:true};}
