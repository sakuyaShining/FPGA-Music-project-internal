const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=="00ba33d542279ea0"||d.parentProjectUuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error('Wrongdocument');
const st=globalThis.__sensorTodayFourLayer;if(!st||st.finishFiveGeometry||st.clearRemainingNC?.phase!=='saved-check-actual-pins')throw Error('Unexpected stage');
if((await eda.sch_PrimitiveWire.getAll()).length!==136)throw Error('Unexpected count');
st.finishFiveGeometry={phase:'running',done:[],createdWires:[],createdPorts:[]};
for(const c of __CLI__.args.plan){
 const id=c.ref+'.'+c.pin;st.finishFiveGeometry.active=id;
 const part=(await eda.sch_PrimitiveComponent.getAll('part',false)).find(p=>p.getState_Designator()===c.ref);const pin=(await part.getAllPins()).find(p=>p.getState_PinNumber()===c.pin);
 if(pin.getState_NoConnected())throw Error('NCstillset '+id);
 const x=pin.getState_X(),y=pin.getState_Y(),r=pin.getState_Rotation(),end=x+(r===180?-45:45);if(r!==0&&r!==180)throw Error('rotation');
 const w=await eda.sch_PrimitiveWire.create([x,y,end,y],c.proposed);st.finishFiveGeometry.createdWires.push({pin:id,id:w.getState_PrimitiveId()});
 const q=await eda.sch_PrimitiveComponent.createNetPort('BI',c.proposed,end,y,r===180?0:180,false);st.finishFiveGeometry.createdPorts.push({pin:id,id:q.getState_PrimitiveId()});
 st.finishFiveGeometry.done.push({ref:c.ref,pin:c.pin,net:c.proposed});await eda.sch_Document.save();
}
st.finishFiveGeometry.phase='saved';return {state:st,wires:(await eda.sch_PrimitiveWire.getAll()).length,ports:(await eda.sch_PrimitiveComponent.getAll('netport',false)).length};