"""Rebuild only the isolated candidate using its recorded page IDs."""
import json
import sys
from build_review import schema, parts, PAGES, place, wire
from native_review import ROOT, PROJECT, invoke

guard=invoke('rebuild-pcb-guard',"""const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');if(!tab)throw new Error('Cannot inspect PCB');return (await eda.pcb_PrimitiveComponent.getAll()).length;""")
if guard:raise RuntimeError('PCB is populated. Full-page rebuilding would replace association IDs; use incremental schematic updates.')
schema()
ids=json.loads((ROOT/'pages.json').read_text())
code="""const project=await eda.dmt_Project.getCurrentProjectInfo();if(project.friendlyName!==__CLI__.args.name)throw new Error('Wrong project');
await eda.dmt_EditorControl.openDocument(__CLI__.args.page);
const ws=await eda.sch_PrimitiveWire.getAllPrimitiveId();if(ws.length)await eda.sch_PrimitiveWire.delete(ws);
const cs=await eda.sch_PrimitiveComponent.getAll();if(cs.length)await eda.sch_PrimitiveComponent.delete(cs.map(c=>c.getState_PrimitiveId()));
const texts=await eda.sch_PrimitiveText.getAllPrimitiveId();if(texts.length)await eda.sch_PrimitiveText.delete(texts);
if(!await eda.sch_Document.save())throw new Error('Save');return {cleared:cs.length};"""
for page in [p for p in PAGES if len(sys.argv)==1 or p in sys.argv[1:]]:
    print(page,invoke('v1-clear-'+page,code,{'page':ids[page],'name':PROJECT.name}),flush=True)
    place(page)
    wire(page)
