const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=="00ba33d542279ea0"||d.parentProjectUuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error('Wrongdocument');
const st=globalThis.__sensorTodayFourLayer;if(!st||st.repairPending)throw Error('Unexpected prior repair state; inspect first');
const plan=__CLI__.args.plan;if(plan.length!==19)throw Error('Expected19pending pins only');
if((await eda.sch_PrimitiveWire.getAll()).length!==135||(await eda.sch_PrimitiveComponent.getAll('netport',false)).length!==135)throw Error('Actual partial counts changed');
st.repairPending={phase:'finishing-only19actual-pending',done:[],newWires:[],newPorts:[]};
for(const c of plan){
 st.repairPending.active=c.ref+'.'+c.pin;
 if(c.was_NC){
  const part=(await eda.sch_PrimitiveComponent.getAll('part',false)).find(p=>p.getState_Designator()===c.ref);
  let pin=(await part.getAllPins()).find(p=>p.getState_PinNumber()===c.pin);
  if(pin.getState_NoConnected())await pin.setState_NoConnected(false).done();
  await new Promise(r=>setTimeout(r,300));
  pin=(await (await eda.sch_PrimitiveComponent.get(part.getState_PrimitiveId())).getAllPins()).find(p=>p.getState_PinNumber()===c.pin);
  if(pin.getState_NoConnected())throw Error('NCclear not committed '+st.repairPending.active);
  const x=pin.getState_X(),y=pin.getState_Y(),r=pin.getState_Rotation();if(r!==0&&r!==180)throw Error('Pinrotation');const end=x+(r===180?-45:45);
  const w=await eda.sch_PrimitiveWire.create([x,y,end,y],c.proposed);if(!w)throw Error('Pendingwirefailed');st.repairPending.newWires.push({pin:st.repairPending.active,id:w.getState_PrimitiveId()});
  const q=await eda.sch_PrimitiveComponent.createNetPort('BI',c.proposed,end,y,r===180?0:180,false);if(!q)throw Error('Pendingportfailed');st.repairPending.newPorts.push({pin:st.repairPending.active,id:q.getState_PrimitiveId()});
 }else{
  const w=await eda.sch_PrimitiveWire.get(c.wire_id);const q=await eda.sch_PrimitiveComponent.get(c.port_id);if(w.getState_Net()!==c.wire_old_net||q.getState_Net()!==c.old)throw Error('Pendingoldnetchanged');
  if(c.wire_old_net){const a=w.toAsync();a.setState_Net(c.proposed);await a.done();}
  const a=q.toAsync();a.setState_Net(c.proposed);a.setState_Name(c.proposed);await a.done();
 }
 st.repairPending.done.push({ref:c.ref,pin:c.pin,net:c.proposed});
}
st.repairPending.phase='pending19finished';st.phase='schematic-wired-await35PAD-netlist-audit';
const saved=await eda.sch_Document.save();const f=await eda.sch_ManufactureData.getNetlistFile('Sensor14Bank-fourlayer-trial','JLCEDA');
return {state:st,saved,netlist:f?await f.text():null,drc:await eda.sch_Drc.check(true,false,true),wires:(await eda.sch_PrimitiveWire.getAll()).length,ports:(await eda.sch_PrimitiveComponent.getAll('netport',false)).length};
