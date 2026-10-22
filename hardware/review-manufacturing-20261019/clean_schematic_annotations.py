"""Remove accumulated review text by explicit IDs; leave electrical primitives intact."""
import json
import sys
from build_review import schema,notes
from native_review import ROOT,invoke

schema()
ids=json.loads((ROOT/'pages.json').read_text())
for name,page in ids.items():
    if len(sys.argv)>1 and name not in sys.argv[1:]:continue
    v=invoke('v2-clean-annotations-'+name,"""const tab=await eda.dmt_EditorControl.openDocument(__CLI__.args.page);if(!tab)throw new Error('Open failed');
const before=await eda.sch_PrimitiveText.getAllPrimitiveId();if(before.length)await eda.sch_PrimitiveText.delete(before);
const remain=await eda.sch_PrimitiveText.getAllPrimitiveId();if(remain.length)throw new Error('Text deletion did not apply');
const pins=[];for(const c of await eda.sch_PrimitiveComponent.getAll()){if(c.getState_SupplierId())pins.push(...await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId()));}
const top=Math.max(...pins.map(p=>p.getState_Y()))+120,bottom=Math.min(...pins.map(p=>p.getState_Y()))-140;
await eda.sch_PrimitiveText.create(60,top,__CLI__.args.name+' - REVIEW CANDIDATE / NOT FOR FABRICATION',0,null,null,16,true);
for(let i=0;i<__CLI__.args.notes.length;i++)await eda.sch_PrimitiveText.create(60,bottom-i*22,__CLI__.args.notes[i],0,null,null,10,false);
await eda.sch_Document.save();const after=await eda.sch_PrimitiveText.getAllPrimitiveId();if(after.length!==__CLI__.args.notes.length+1)throw new Error('Unexpected annotation count');return {removed:before.length,current:after.length};""",{'page':page,'name':name,'notes':notes[name]},120)
    print(name,v,flush=True)
