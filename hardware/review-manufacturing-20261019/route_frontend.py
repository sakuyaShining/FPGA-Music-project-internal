"""Native routing trial for explicitly selected sensor nets, with a saved checkpoint."""
import json
import sys
import time
import zipfile
from pathlib import Path
from native_review import ROOT,PROJECT,invoke
from pcb_candidate import PCB

mode=sys.argv[1] if len(sys.argv)>1 else 'lane0'
if mode=='lane0':nets=[f'L0_E{a:02}' for a in range(14)]
elif mode=='electrodes':nets=[f'L{l}_E{a:02}' for l in range(6) for a in range(14)]
elif mode=='mux':nets=[f'L{l}_M{a:02}' for l in range(6) for a in range(16)]
elif mode.startswith('mux_lane_'):
    lane=int(mode.rsplit('_',1)[1]);assert 0<=lane<6
    nets=[f'L{lane}_M{a:02}' for a in range(16)]
elif mode=='power5v':nets=['5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH']
elif mode=='powerprotected':nets=['5V_PROTECTED']
elif mode=='rails3v3':nets=['3V3_IO','DAC_3V3','3V3_PERIPH']
elif mode=='timing':nets=[f'RC{i}' for i in range(6)]
elif mode=='analog':nets=['DAC_CAPP','DAC_CAPM','DAC_VNEG','DAC_LDOO','DAC_XSMT','DAC_L_RAW','DAC_R_RAW','AUX_L','AUX_R']
elif mode=='core':
    design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
    excluded={'GND','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3',
              'DAC_CAPP','DAC_CAPM','DAC_VNEG','DAC_LDOO','DAC_XSMT','DAC_L_RAW','DAC_R_RAW','AUX_L','AUX_R',*[f'RC{i}' for i in range(6)]}
    nets=sorted({n for p in design['parts'] for n in p['nets'].values() if n and n not in excluded and not (n.startswith('L') and len(n)>2 and n[1].isdigit() and n[2]=='_')})
elif mode.startswith('single_'):nets=[mode[len('single_'):]]
else:raise ValueError(mode)
dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
backup=dest/('before-routing-'+mode+'.zip')
if not backup.exists():
    with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PROJECT.rglob('*'):
            if p.is_file() and 'exports' not in p.as_posix():z.write(p,p.relative_to(PROJECT))
print('Routing trial',mode,len(nets),'nets; backup',backup,flush=True)
v=invoke('v2-route-'+mode+'-'+str(time.time_ns()),"""const tab=await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);if(!tab)throw new Error('No PCB');
const all=new Set(await eda.pcb_Net.getAllNetsName());for(const n of __CLI__.args.nets)if(!all.has(n))throw new Error('Missing '+n);
const before={lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length};
const previous=(await eda.pcb_Drc.getCurrentRuleConfiguration()).config;
let result;try{if(__CLI__.args.width){const c=JSON.parse(JSON.stringify(previous));c.Physics.Track.copperThickness1oz.form.data['1'].minValue=__CLI__.args.width.min;c.Physics.Track.copperThickness1oz.form.data['1'].defaultValue=__CLI__.args.width.default;if(!await eda.pcb_Drc.overwriteCurrentRuleConfiguration(c))throw new Error('Width config');}
result=await eda.pcb_Document.autoRouting({RoutingNets:__CLI__.args.nets,layers:[1,2],optimization:0,existingPrimitiveMode:'keep'});}finally{if(__CLI__.args.width)await eda.pcb_Drc.overwriteCurrentRuleConfiguration(previous);await eda.pcb_Document.save();}
const tracks=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>__CLI__.args.nets.includes(p.getState_Net()));
const report={selected:__CLI__.args.nets,before,result,after:{lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length},widths_mil:[...new Set(tracks.map(p=>p.getState_LineWidth()))]};
const file=new File([JSON.stringify(report)],'routing-result.json',{type:'application/json'});await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.resultPath,file,undefined,true);return report;""",{'pcb':PCB,'nets':nets,'resultPath':(PROJECT/'review-exports'/('routing-'+mode+'-result.json')).as_posix(),'width':({'min':.762,'default':1.0} if mode=='power5v' else {'min':.762,'default':.8} if mode=='powerprotected' else {'min':.254,'default':.4} if mode=='rails3v3' else {'min':.2032,'default':.4} if mode=='analog' else None)},900 if mode in ['mux','core'] or mode.startswith('mux_lane_') else 300)
(ROOT/('routing-'+mode+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(v,ensure_ascii=False),flush=True)
