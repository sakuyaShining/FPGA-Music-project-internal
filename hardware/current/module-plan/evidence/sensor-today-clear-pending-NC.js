const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=="00ba33d542279ea0"||d.parentProjectUuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error('Wrongdocument');
const cs=await eda.sch_PrimitiveComponent.getAll('part',false),c=cs.find(p=>p.getState_Designator()==='D3');
const pin=(await c.getAllPins()).find(p=>p.getState_PinNumber()==='10');
if(!pin.getState_NoConnected())throw Error('Pin already changed; inspect first');
globalThis.__sensorTodayFourLayer.phase='repair-D3.10-NC-actual-readback';
const result=await pin.setState_NoConnected(false).done();
await new Promise(r=>setTimeout(r,300));
const fresh=(await (await eda.sch_PrimitiveComponent.get(c.getState_PrimitiveId())).getAllPins()).find(p=>p.getState_PinNumber()==='10');
return {doneResult:result,pin:fresh,NCcleared:!fresh.getState_NoConnected(),saved:await eda.sch_Document.save(),state:globalThis.__sensorTodayFourLayer};
