"""Read-only native visual export bound to the saved 78-open checkpoint."""
import hashlib
import json
import base64
from native_review import ROOT, PROJECT, invoke

out = ROOT / 'visual-review-78open'
out.mkdir(exist_ok=True)
pcb = PROJECT / 'pcb/PCB1.epcb2'
sha = lambda: hashlib.sha256(pcb.read_bytes()).hexdigest()
manifest = json.loads((ROOT/'route-checkpoint-0clear-78open.json').read_text())
before = sha()
assert before == manifest['pcb_sha256']
result = invoke('checkpoint78-visual-export-base64', """const f=await eda.pcb_ManufactureData.getPdfFile('pcb-native-78open-REVIEW','paged',{displayAttributesAsMenu:true,showOutlineOnly:false});if(!f)throw new Error('No PDF');const a=new Uint8Array(await f.arrayBuffer()),t='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let s='';for(let i=0;i<a.length;i+=3){const n=(a[i]<<16)|((a[i+1]||0)<<8)|(a[i+2]||0);s+=t[(n>>>18)&63]+t[(n>>>12)&63]+(i+1<a.length?t[(n>>>6)&63]:'=')+(i+2<a.length?t[n&63]:'=');}return {size:f.size,base64:s};""", {'pcb':'c3fd8656cf425e9f'}, 180)
(out/'pcb-native-78open-REVIEW.pdf').write_bytes(base64.b64decode(result.pop('base64')))
assert sha() == before
(out/'export-audit.json').write_text(json.dumps({'source_pcb_sha256':before,'source_unchanged':True,'native_export':result,'manufacturing_release':False},indent=2),encoding='utf-8')
print(json.dumps(result), flush=True)
