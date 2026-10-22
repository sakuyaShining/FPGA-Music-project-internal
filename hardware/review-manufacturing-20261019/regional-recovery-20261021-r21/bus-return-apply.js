
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');let createdV=[];
try{for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdV};
}catch(e){if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_Document.save();throw e;}
