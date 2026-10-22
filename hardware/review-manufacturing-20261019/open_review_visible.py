"""Reopen only this task's saved candidate visibly for native copper rebuilding."""
import json
import time
from native_review import ROOT,PROJECT,call,invoke

sid=json.loads((ROOT/'evidence/open.json').read_text())['value']['sessionId']
print(call('ground-ui-close',['session','close','--session',sid,'--destroy']),flush=True)
value=call('ground-ui-open',['open','--path',(PROJECT/(PROJECT.name+'.eprj3')).as_posix(),'--headless','false'],120)
(ROOT/'evidence/open.json').write_text(json.dumps({'ok':True,'value':value}),encoding='utf-8')
time.sleep(3)
for attempt in range(20):
    result=invoke('ground-ui-focus-'+str(attempt),"""await eda.dmt_Project.getCurrentProjectInfo();const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');return {tab,doc:await eda.dmt_SelectControl.getCurrentDocumentInfo()};""")
    if result.get('tab') and result.get('doc',{}).get('documentType')==3:break
    time.sleep(2)
else:raise RuntimeError('Could not focus candidate PCB')
print(invoke('ground-ui-prepare',"""await eda.pcb_Drc.stopRealTimeDrc();await eda.pcb_SelectControl.clearSelected();return {pours:(await eda.pcb_PrimitivePour.getAll()).map(p=>({id:p.getState_PrimitiveId(),name:p.getState_PourName(),layer:p.getState_Layer()})),components:(await eda.pcb_PrimitiveComponent.getAll()).length};"""),flush=True)
