const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=="00ba33d542279ea0"||d.parentProjectUuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error('Wrongdocument');
const st=globalThis.__sensorTodayFourLayer;if(!st||st.clearRemainingNC)throw Error('Unexpected prior clearstage');
st.clearRemainingNC={phase:'clearing-only-five-no-geometry',pins:[]};
for(const x of [['D3','9'],['D3','7'],['D3','6'],['D4','10'],['D4','9']]){
 const c=(await eda.sch_PrimitiveComponent.getAll('part',false)).find(p=>p.getState_Designator()===x[0]);const pin=(await c.getAllPins()).find(p=>p.getState_PinNumber()===x[1]);
 if(pin.getState_NoConnected())await pin.setState_NoConnected(false).done();
 st.clearRemainingNC.pins.push(x.join('.'));
}
const saved=await eda.sch_Document.save();const status=[];
for(const x of [['D3','9'],['D3','7'],['D3','6'],['D4','10'],['D4','9']]){const c=(await eda.sch_PrimitiveComponent.getAll('part',false)).find(p=>p.getState_Designator()===x[0]);const pin=(await c.getAllPins()).find(p=>p.getState_PinNumber()===x[1]);status.push({ref:x[0],pin:x[1],NC:pin.getState_NoConnected()});}
st.clearRemainingNC.phase='saved-check-actual-pins';return {saved,status,state:st};
