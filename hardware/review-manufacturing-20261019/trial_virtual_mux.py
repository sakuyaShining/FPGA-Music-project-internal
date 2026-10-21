"""Local Freerouting trial after removing one lane's copper only in DSN copy.

The native candidate remains intact throughout. No result is auto-imported.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from native_review import ROOT,PROJECT,invoke
from offline_route import JAR,JAR_SHA,DEST
from sanitize_dsn import sanitize

mode=sys.argv[1]
warm='--warm' in sys.argv[2:]
design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'));nets={n for p in design['parts'] for n in p['nets'].values() if n}
groups={
 'controls-ui':{'PRESET0','PRESET1','PRESET2','PRESET3','EDIT','ENC_PUSH','ENC_B','ENC_A'},
 'scan-bus':{'ADDR0','ADDR1','ADDR2','ADDR3','MUX_DISABLE','RC_DRIVE','SCAN_LATCH'},
 'shared-bus':{'BUS_SCK','BUS_MOSI','BUS_RETURN','INPUT_LOAD_N','HARM_CS_N','VIS_CS_N','VIS_DC','LCD_RESET_N','TP_RESET_N','RA_MISO'},
 'display-side':{'DISP_HARM_CS_N','DISP_MOSI','DISP_RESET_N','DISP_SCK','DISP_VIS_CS_N','DISP_VIS_DC','VIS_BL_EN','TP_RESET_MOD_N','TP_INT_MOD','TP_INT','I2C_MOD_SCL','I2C_MOD_SDA','I2C_SCL','I2C_SDA'},
 'audio-inv':{'INV0','INV1','INV2','INV3','INV4','INV5','SENSE_3','SENSE_5','I2S_BCK','I2S_DIN','I2S_LRCK','DAC_XSMT'},
}
if mode in ['signals','core']:
    lane='signals'
    protected={'GND','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3',
               'DAC_CAPP','DAC_CAPM','DAC_VNEG','DAC_LDOO','DAC_L_RAW','DAC_R_RAW','AUX_L','AUX_R'}
    selected={n for n in nets if not re.fullmatch(r'L[0-5]_E\d\d',n)}-protected
    if mode=='core':selected={n for n in selected if not re.fullmatch(r'L[0-5]_M\d\d|RC[0-5]',n)}
    label=mode
elif mode in groups:
    selected=groups[mode];assert selected<=nets;lane=mode;label=mode
else:
    lane=int(mode);assert 0<=lane<6
    selected={f'L{lane}_M{i:02}' for i in range(16)}|{f'RC{lane}'};label=f'lane{lane}'
if warm:label+='-warm'
name=f'virtual-{label}-{time.time_ns()}';out=DEST/'routing-work'/name;out.mkdir(parents=True)
source=PROJECT/'review-exports/v2'/(name+'.dsn')
actual=invoke(name+'-export',"""const f=await eda.pcb_ManufactureData.getDsnFile('virtual-copper-trial');if(!f)throw new Error('No DSN');if(!await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path,f,undefined,true))throw new Error('Export');return {vias:(await eda.pcb_PrimitiveVia.getAll()).map(v=>({id:v.getState_PrimitiveId(),x:v.getState_X(),y:v.getState_Y()})),components:(await eda.pcb_PrimitiveComponent.getAll()).length};""",{'path':source.as_posix()},180)
assert actual['components']==230
text=source.read_text(encoding='utf-8');shutil.copy2(source,out/'native.dsn')
text,metadata=sanitize(text,actual['vias'],selected,selected_width_mil=6,new_clearance_mil=6.5 if mode=='core' or warm else 7)
tokens=re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+',text);stack=[];root=None
for token in tokens:
    if token=='(':
        node=[]
        if stack:stack[-1].append(node)
        else:assert root is None;root=node
        stack.append(node)
    elif token==')':assert stack;stack.pop()
    else:assert stack;stack[-1].append(token)
assert not stack
wiring=next(n for n in root if isinstance(n,list) and n and n[0]=='wiring')
removed=[];kept=[];unlocked=0
for item in wiring[1:]:
    net=next((n[1] for n in item if isinstance(n,list) and n and n[0]=='net'),None) if isinstance(item,list) else None
    net=json.loads(net) if net and net.startswith('"') else net
    if isinstance(item,list) and item and item[0] in ['wire','via'] and net in selected:
        if warm:
            item[:]=[n for n in item if not(isinstance(n,list) and n and n[0]=='type')]
            kept.append(item);unlocked+=1
        else:removed.append(item)
    else:kept.append(item)
wiring[1:]=kept
def serialize(node):return '('+' '.join(serialize(n) if isinstance(n,list) else n for n in node)+')'
(out/'input.dsn').write_text(serialize(root)+'\n',encoding='utf-8')
assert hashlib.sha256(JAR.read_bytes()).hexdigest()==JAR_SHA
args=['java','-Xmx512m','-jar',str(JAR),'-de',str(out/'input.dsn'),'-do',str(out/'result.ses'),
      '--router.autorouter.max_passes='+('30' if warm else '8'),'--router.fanout.enabled=false','--router.optimizer.enabled=false',
      '--router.automatic_neckdown=false',
      '--router.strict_drc=true','--router.job_timeout='+('00:08:00' if warm else '00:04:00'),'--router.autorouter.ignore_net_classes='+','.join(sorted(nets-selected)),
      '--router.result_json='+str(out/'result.json'),'-da','--gui.enabled=false','--api_server.enabled=false',
      '--logging.file.enabled=false','--user_data_path=D:/FPGA-Project/codex-tools/freerouting/'+name]
audit={'lane':lane,'selected':sorted(selected),'native_pcb_mutated':False,'removed_exchange_objects':len(removed),
       'unlocked_exchange_objects':unlocked,'sanitization':metadata,'args':args,'manufacturing_release':False}
(out/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
(ROOT/f'virtual-{label}-latest.json').write_text(json.dumps({'directory':str(out),'native_imported':False},indent=2),encoding='utf-8')
print('VIRTUAL TRIAL',out,'removed',len(removed),'unlocked',unlocked,'exchange objects',flush=True)
with (out/'run.log').open('w',encoding='utf-8') as log:
    result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=540 if warm else 300)
audit['exit_code']=result.returncode;audit['ses_exists']=(out/'result.ses').is_file()
(out/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('VIRTUAL RESULT',audit['exit_code'],audit['ses_exists'],out,flush=True)
