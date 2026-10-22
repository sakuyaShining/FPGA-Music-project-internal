import json
from phase import invoke
print(json.dumps(invoke('probe-wire-read',"return {wires:(await eda.sch_PrimitiveWire.getAll()).map(w=>({id:w.getState_PrimitiveId(),line:w.getState_Line(),net:w.getState_Net()}))};"),ensure_ascii=True))
print(json.dumps(invoke('probe-net-port',"const p=await eda.sch_PrimitiveComponent.createNetPort('BI','SENSE_A',80,655,0);return {created:!!p,id:p?.getState_PrimitiveId(),saved:await eda.sch_Document.save()};"),ensure_ascii=True))
