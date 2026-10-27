const P="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7",S="00ba33d542279ea0";
const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!==S||d.parentProjectUuid!==P)throw Error("Wrong owned schematic");
const plan=__CLI__.args.plan;if(plan.length!==35)throw Error("Expected exactly35explicitchanges");
if(globalThis.__sensorTodayFourLayer)throw Error("Trial already started; capture actual phase, never replay");
const cs=await eda.sch_PrimitiveComponent.getAll('part',false);if(cs.length!==28)throw Error("Partschanged");
// Complete all read guards BEFORE the first edit.
for(const c of plan){
 const part=cs.find(p=>p.getState_Designator()===c.ref);const pin=(await part.getAllPins()).find(p=>p.getState_PinNumber()===c.pin);
 if(!pin||pin.getState_NoConnected()!==c.was_NC)throw Error("Pinchanged"+c.ref+'.'+c.pin);
 if(!c.was_NC){const w=await eda.sch_PrimitiveWire.get(c.wire_id),q=await eda.sch_PrimitiveComponent.get(c.port_id);if(w.getState_Net()!==c.wire_old_net||q.getState_Net()!==c.old)throw Error("Oldnchanged"+c.ref+'.'+c.pin);}
}
globalThis.__sensorTodayFourLayer={phase:'schematic-applying',changes:[],newWires:[],newPorts:[]};
for(const c of plan){
 if(c.was_NC){
  const part=cs.find(p=>p.getState_Designator()===c.ref);const pin=(await part.getAllPins()).find(p=>p.getState_PinNumber()===c.pin);
  await pin.setState_NoConnected(false).done();globalThis.__sensorTodayFourLayer.changes.push({ref:c.ref,pin:c.pin,phase:'NCcleared'});
  const x=pin.getState_X(),y=pin.getState_Y(),r=pin.getState_Rotation();if(r!==0&&r!==180)throw Error('Unexpecteddirection');const end=x+(r===180?-45:45);
  const w=await eda.sch_PrimitiveWire.create([x,y,end,y],c.proposed);if(!w)throw Error('NewWirefailed');globalThis.__sensorTodayFourLayer.newWires.push(w.getState_PrimitiveId());
  const q=await eda.sch_PrimitiveComponent.createNetPort('BI',c.proposed,end,y,r===180?0:180,false);if(!q)throw Error('NewPortfailed');globalThis.__sensorTodayFourLayer.newPorts.push(q.getState_PrimitiveId());
 }else{
  if(c.wire_old_net){const w=(await eda.sch_PrimitiveWire.get(c.wire_id)).toAsync();w.setState_Net(c.proposed);await w.done();}
  const q=(await eda.sch_PrimitiveComponent.get(c.port_id)).toAsync();q.setState_Net(c.proposed);q.setState_Name(c.proposed);await q.done();
 }
 globalThis.__sensorTodayFourLayer.changes.push({ref:c.ref,pin:c.pin,old:c.old,net:c.proposed,phase:'wired'});
}
globalThis.__sensorTodayFourLayer.phase='schematic-wired-await-netlist-audit';
const saved=await eda.sch_Document.save();const f=await eda.sch_ManufactureData.getNetlistFile('Sensor14Bank-fourlayer-trial','JLCEDA');
return {state:globalThis.__sensorTodayFourLayer,saved,netlist:f?await f.text():null,wires:(await eda.sch_PrimitiveWire.getAll()).length,ports:(await eda.sch_PrimitiveComponent.getAll('netport',false)).length};
