
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');await eda.pcb_Drc.stopRealTimeDrc();
if(!await eda.pcb_PrimitiveLine.delete(d.remove_lines.map(p=>p.id)))throw new Error('Delete line');if(!await eda.pcb_PrimitiveVia.delete(d.remove_vias.map(p=>p.id)))throw new Error('Delete via');let createdL=[],createdV=[];
for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
for(const p of d.lines){const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdL,createdV,removedL:d.remove_lines.map(p=>p.id),removedV:d.remove_vias.map(p=>p.id)};
