"""Append v2 pages and rebuild only changed electrical sheets, preserving v1 evidence."""
import json
import shutil
from native_review import ROOT, invoke

archive=ROOT/'evidence/v2/v1-text'
archive.mkdir(parents=True,exist_ok=True)
for name in ['design.json','expected-pin-nets.json','native-protel.net','native-bom.tsv',
             'native-drc.json','connectivity-audit.json','pin-net-audit.csv','pages.json',
             'procurement-native-candidate.csv','harness-contract.csv']:
    p=ROOT/name
    if p.exists() and not (archive/name).exists():shutil.copy2(p,archive/name)

from build_review import schema, PAGES
schema()
ids=json.loads((ROOT/'pages.json').read_text())
inventory=invoke('v2-find-created-pages','return await eda.dmt_Schematic.getAllSchematicPagesInfo();')
unrecorded=[p for p in inventory if p['uuid'] not in ids.values()]
missing=[p for p in PAGES if p not in ids]
for name,p in zip(missing,unrecorded):ids[name]=p['uuid']
missing=[p for p in PAGES if p not in ids]
if missing:
    result=invoke('v2-create-additional-pages',"""const old=await eda.dmt_Schematic.getAllSchematicPagesInfo();const sch=old[0].parentSchematicUuid;const r={};
for(const name of __CLI__.args.names){const id=await eda.dmt_Schematic.createSchematicPage(sch);if(!id)throw new Error('Create page');await new Promise(r=>setTimeout(r,1600));r[name]=id;}return r;""",{'names':missing},120)
    ids.update(result)
(ROOT/'pages.json').write_text(json.dumps(ids,indent=2)+'\n',encoding='utf-8')
print(invoke('v2-normalize-page-names',"""for(const [name,id] of Object.entries(__CLI__.args.ids)){await eda.dmt_Schematic.modifySchematicPageName(id,name);await new Promise(r=>setTimeout(r,150));}return await eda.dmt_Schematic.getAllSchematicPagesInfo();""",{'ids':ids},120))
print('v2 pages ready',len(ids),flush=True)
