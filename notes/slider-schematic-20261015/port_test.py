import json
from phase import invoke
print(json.dumps(invoke('port-only-probe',"await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const ids=await eda.sch_PrimitiveWire.getAllPrimitiveId();const p=await eda.sch_PrimitiveComponent.createNetPort('BI','SENSE_A',80,655,0);const saved=await eda.sch_Document.save();return {ids,created:!!p,id:p?.getState_PrimitiveId(),saved};"),ensure_ascii=True))
