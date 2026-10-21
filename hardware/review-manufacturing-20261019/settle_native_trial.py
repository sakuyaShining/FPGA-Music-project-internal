"""Save a timed-out task's current copper and restore its exact saved rules.

This captures a candidate only. The owned renderer is subsequently reopened,
which terminates the abandoned routing continuation before independent DRC.
"""
import hashlib
import json
import time
from native_review import ROOT,PROJECT,invoke

rule_path=PROJECT/'review-exports/v2/native-finish-core-1792484883356682500-rules-before.json'
value=invoke('settle-timed-out-core-'+str(time.time_ns()),"""
const f=await eda.sys_FileSystem.readFileFromFileSystem(__CLI__.args.path);if(!f)throw new Error('Missing original rules');
const config=JSON.parse(await f.text());const restored=await eda.pcb_Drc.overwriteCurrentRuleConfiguration(config);
if(!restored)throw new Error('Rule restoration failed');await eda.pcb_Document.save();
return {rules_restored:restored,rule_configuration_equal:JSON.stringify((await eda.pcb_Drc.getCurrentRuleConfiguration()).config)===JSON.stringify(config),
components:(await eda.pcb_PrimitiveComponent.getAll()).length,lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length,
requires_close_reopen_and_native_drc:true};
""",{'path':rule_path.as_posix()},60)
value['original_rules_sha256']=hashlib.sha256(rule_path.read_bytes()).hexdigest()
(ROOT/'native-core-timeout-settle.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
print(json.dumps(value,indent=2),flush=True)
assert value['rules_restored'] and value['rule_configuration_equal'] and value['components']==230
