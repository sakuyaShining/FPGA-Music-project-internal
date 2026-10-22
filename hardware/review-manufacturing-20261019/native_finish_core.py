"""One bounded native routing trial after clearing unfinished core fragments.

Only pending signal nets are requested. Existing copper is kept, the native
minimum/clearance rules are unchanged, and the temporary default width is
restored even when routing reports an error. A source backup precedes routing.
"""
import json
import re
import time
import zipfile
from pathlib import Path
from native_review import ROOT,PROJECT,invoke

drc=json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8'))
protected={'GND','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3'}
nets=[n['name'] for c in drc if c['name']=='Connection Error' for n in c['list'] if n['name'] not in protected and not re.fullmatch(r'L[0-5]_[EM]\d\d|RC[0-5]',n['name'])]
assert len(nets)==25
name='native-finish-core-'+str(time.time_ns());dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
backup=dest/(name+'-before-CANDIDATE.zip')
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
    for p in PROJECT.rglob('*'):
        if p.is_file() and 'review-exports' not in p.relative_to(PROJECT).parts:archive.write(p,p.relative_to(PROJECT))
print('NATIVE CORE TRIAL',len(nets),'nets; backup',backup,flush=True)
value=invoke(name,"""
const ns=new Set(__CLI__.args.nets);const previous=(await eda.pcb_Drc.getCurrentRuleConfiguration()).config;
const file=new File([JSON.stringify(previous)],'rules-before.json',{type:'application/json'});if(!await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.rulePath,file,undefined,true))throw new Error('Rule checkpoint');
const identities=()=>eda.pcb_PrimitiveComponent.getAll().then(cs=>cs.map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]));
const lineState=()=>eda.pcb_PrimitiveLine.getAll().then(ps=>ps.filter(p=>!ns.has(p.getState_Net())).map(p=>[p.getState_PrimitiveId(),p.getState_Net(),p.getState_Layer(),p.getState_StartX(),p.getState_StartY(),p.getState_EndX(),p.getState_EndY(),p.getState_LineWidth()]).sort((a,b)=>a[0].localeCompare(b[0])));
const viaState=()=>eda.pcb_PrimitiveVia.getAll().then(ps=>ps.filter(p=>!ns.has(p.getState_Net())).map(p=>[p.getState_PrimitiveId(),p.getState_Net(),p.getState_X(),p.getState_Y(),p.getState_Diameter(),p.getState_HoleDiameter()]).sort((a,b)=>a[0].localeCompare(b[0])));
const before={components:await identities(),lines:await lineState(),vias:await viaState()};if(before.components.length!==230)throw new Error('Wrong project');
let result=null,error=null,restored=false;
try{const c=JSON.parse(JSON.stringify(previous));const field=c.Physics.Track.copperThickness1oz.form.data['1'];if(typeof field.minValue!=='number')throw new Error('Unknown native width rule');field.defaultValue=field.minValue;if(!await eda.pcb_Drc.overwriteCurrentRuleConfiguration(c))throw new Error('Set signal default');result=await eda.pcb_Document.autoRouting({RoutingNets:__CLI__.args.nets,layers:[1,2],optimization:0,existingPrimitiveMode:'keep'});}
catch(e){error=String(e);}
finally{restored=await eda.pcb_Drc.overwriteCurrentRuleConfiguration(previous);await eda.pcb_Document.save();}
return {selected:__CLI__.args.nets,result,error,rules_restored:restored,
device_identity_and_placement_unchanged:JSON.stringify(before.components)===JSON.stringify(await identities()),
unselected_tracks_unchanged:JSON.stringify(before.lines)===JSON.stringify(await lineState()),
unselected_vias_unchanged:JSON.stringify(before.vias)===JSON.stringify(await viaState()),
counts:{lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length},requires_ground_rebuild_and_native_drc:true};
""",{'nets':nets,'rulePath':(PROJECT/'review-exports/v2'/(name+'-rules-before.json')).as_posix()},370)
(ROOT/(name+'-audit.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
print(json.dumps(value,indent=2),flush=True)
assert not value['error'] and value['rules_restored'] and value['device_identity_and_placement_unchanged']
assert value['unselected_tracks_unchanged'] and value['unselected_vias_unchanged']
