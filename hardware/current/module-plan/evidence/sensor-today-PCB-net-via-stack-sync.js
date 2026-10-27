const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=="f52674d6627fca6f"||d.parentProjectUuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error('WrongPCB');
const s=globalThis.__sensorTodayFourLayer;if(!s||s.PCBNetSync)throw Error('Unexpectedstage');
const a=__CLI__.args;if(a.pads.length!==35||a.moves.length!==21)throw Error('Planlength');if((await eda.pcb_PrimitiveLine.getAll()).length!==91||(await eda.pcb_PrimitiveVia.getAll()).length!==36||(await eda.pcb_PrimitiveComponent.getAll()).length!==28)throw Error('Objectcount');
for(const x of a.pads){const p=await eda.pcb_PrimitivePad.get(x.id);if(p.getState_Net()!==x.old)throw Error('OldPADnet '+x.id);}
for(const x of a.moves){const p=await eda.pcb_PrimitiveVia.get(x.id);if(p.getState_Net()!=='GND'||Math.hypot(p.getState_X()*.0254-x.old_mm[0],p.getState_Y()*.0254-x.old_mm[1])>.002)throw Error('Viachanged '+x.id);}
s.PCBNetSync={phase:'running',padChanges:[],viaMoves:[]};
for(const x of a.pads){const p=(await eda.pcb_PrimitivePad.get(x.id)).toAsync();p.setState_Net(x.proposed);await p.done();s.PCBNetSync.padChanges.push(x);}
for(const x of a.moves){const p=(await eda.pcb_PrimitiveVia.get(x.id)).toAsync();p.setState_X(x.proposed_mm[0]/.0254);p.setState_Y(x.proposed_mm[1]/.0254);await p.done();s.PCBNetSync.viaMoves.push(x);}
s.PCBNetSync.layerResult=await eda.pcb_Layer.setTheNumberOfCopperLayers(4);const saved=await eda.pcb_Document.save();s.PCBNetSync.phase='saved-await-independent-readback';return {saved,state:s.PCBNetSync};