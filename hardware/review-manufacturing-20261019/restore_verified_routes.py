"""Restore exact native electrode/RC copper from the zero-clearance checkpoint.

The SES round trip rounded some fixed tracks. Keep the new core/MUX routing,
but replace all E00..E13 and RC0..RC5 copper with the saved native coordinates.
Preserves all 230 device identities and every pad/net association.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path
from native_review import ROOT, PROJECT, invoke

source=ROOT/'pcb-copper-before-offline-import.json'
data=json.loads(source.read_text(encoding='utf-8'))
selected=lambda n:bool(re.fullmatch(r'L[0-5]_E\d\d|RC[0-5]',n))
lines=[p for p in data['lines'] if selected(p['net'])]
vias=[p for p in data['vias'] if selected(p['net'])]
assert len(lines)==634 and len(vias)==36
dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
backup=dest/'before-verified-electrode-restore.zip'
if (ROOT/'verified-electrode-restore-audit.json').exists():raise RuntimeError('Restore already applied; inspect before rerunning')
if not backup.exists():
    with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PROJECT.rglob('*'):
            if p.is_file() and 'exports' not in p.as_posix():z.write(p,p.relative_to(PROJECT))
payload=PROJECT/'review-exports/v2/verified-electrode-restore.json'
payload.write_text(json.dumps({'lines':lines,'vias':vias}),encoding='utf-8')
value=invoke('v2-restore-exact-electrode-timing-copper',r"""
const payload=await eda.sys_FileSystem.readFileFromFileSystem(__CLI__.args.path);const data=JSON.parse(await payload.text());
const selected=n=>/^L[0-5]_E\d\d$/.test(n)||/^RC[0-5]$/.test(n);
const before=(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y()]);
const ls=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>selected(p.getState_Net()));
const vs=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>selected(p.getState_Net()));
if(ls.length&&!await eda.pcb_PrimitiveLine.delete(ls.map(p=>p.getState_PrimitiveId())))throw new Error('Line removal');
if(vs.length&&!await eda.pcb_PrimitiveVia.delete(vs.map(p=>p.getState_PrimitiveId())))throw new Error('Via removal');
for(const p of data.lines)if(!await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false))throw new Error('Track create');
for(const p of data.vias)if(!await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter,0,null,null,false))throw new Error('Via create');
const after=(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y()]);
if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('Device change');
await eda.pcb_Document.save();return {removed_lines:ls.length,removed_vias:vs.length,restored_lines:data.lines.length,restored_vias:data.vias.length,components:after.length,device_identity_placement_unchanged:true,total_lines:(await eda.pcb_PrimitiveLine.getAll()).length,total_vias:(await eda.pcb_PrimitiveVia.getAll()).length};
""",{'path':payload.as_posix()},240)
value['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
value['source_drc_evidence']='evidence/reboot-drc-after-fixes.json: no clearance errors before first SES import'
(ROOT/'verified-electrode-restore-audit.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
print(value,flush=True)
