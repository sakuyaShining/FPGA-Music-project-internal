"""Execute reviewed routing stages, renewing only our own saved headless session."""
import json
import subprocess
import sys
import time
from native_review import ROOT,PROJECT,call,invoke

def renew(stage):
    sid=json.loads((ROOT/'evidence/open.json').read_text())['value']['sessionId']
    print(call('v2-pipeline-close-'+stage,['session','close','--session',sid,'--destroy']),flush=True)
    descriptor=PROJECT/(PROJECT.name+'.eprj3')
    data=json.loads(descriptor.read_text(encoding='utf-8'))
    valid=set(data.get('profile',{}).get('sheets',{}))|set(data.get('profile',{}).get('pcbs',{}))
    if data.get('default_sheet') not in valid:
        (ROOT/'evidence/v2/descriptor-before-default-fix.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        data['default_sheet']='ba336973a1f81bda'
        descriptor.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    v=call('v2-pipeline-open-'+stage,['open','--path',(PROJECT/(PROJECT.name+'.eprj3')).as_posix(),'--headless','true'],120)
    (ROOT/'evidence/open.json').write_text(json.dumps({'ok':True,'value':v}),encoding='utf-8')
    time.sleep(3)
    for attempt in range(20):
        result=invoke('v2-pipeline-focus-'+stage+'-'+str(attempt),"""await eda.dmt_Project.getCurrentProjectInfo();const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');return {tab,doc:await eda.dmt_SelectControl.getCurrentDocumentInfo()};""")
        if result.get('tab') and result.get('doc',{}).get('documentType')==3:break
        time.sleep(2)
    else:raise RuntimeError('Could not activate saved PCB')
    invoke('v2-stop-realtime-'+stage,'return await eda.pcb_Drc.stopRealTimeDrc();')

if __name__=='__main__':
    stages=sys.argv[1:] or ['timing','mux','analog','core']
    for i,stage in enumerate(stages):
        if i%2==0:renew(stage)
        print('START STAGE',stage,flush=True)
        subprocess.run([sys.executable,'-X','utf8',str(ROOT/'route_frontend.py'),stage],check=True)
        print('SAVED STAGE',stage,flush=True)
    print('All requested routing stages saved. Full connectivity/DRC review is still required.',flush=True)
