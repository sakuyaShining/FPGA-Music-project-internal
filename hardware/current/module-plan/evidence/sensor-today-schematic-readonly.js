const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7")throw Error("Wrong owned project");
await eda.dmt_EditorControl.openDocument("00ba33d542279ea0");
const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d.uuid!=="00ba33d542279ea0"||d.parentProjectUuid!==p.uuid)throw Error("Wrong schematic");
const parts=await eda.sch_PrimitiveComponent.getAll('part',false);
if(parts.length!==28)throw Error("Unexpected part count");
const pins=[];for(const c of parts){for(const pin of await c.getAllPins())pins.push({ref:c.getState_Designator(),pin:pin.getState_PinNumber(),data:pin});}
return {read_only:true,project_uuid:p.uuid,doc:d,parts,pins,wires:await eda.sch_PrimitiveWire.getAll(),ports:await eda.sch_PrimitiveComponent.getAll('netport',false)};
