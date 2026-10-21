"""Native PCB import and pad inventory. Never generates a fabrication release."""
import json
import sys
from native_review import ROOT,PROJECT,invoke

PCB='c3fd8656cf425e9f'
SCH='7a8553eae6bc33bb'

def inventory():
    value=invoke('v2-pcb-pad-inventory',"""await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const out=[];
for(const c of await eda.pcb_PrimitiveComponent.getAll()){const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());out.push({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation(),layer:c.getState_Layer(),code:c.getState_SupplierId(),footprint:c.getState_Footprint(),pads:(pins||[]).map(p=>({id:p.getState_PrimitiveId(),n:p.getState_PadNumber(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),rotation:p.getState_Rotation(),shape:p.getState_Pad(),hole:p.getState_Hole()}))});}return out;""",{'pcb':PCB},150)
    (ROOT/'pcb-pad-inventory.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PCB inventory',len(value),'components',sum(len(p['pads']) for p in value),'pads',flush=True)
    return value

if __name__=='__main__':
    if sys.argv[1]=='import':
        print(invoke('v2-pcb-import',"""const p=await eda.dmt_Project.getCurrentProjectInfo();if(p.friendlyName!==__CLI__.args.name)throw new Error('Wrong project');await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const before=(await eda.pcb_PrimitiveComponent.getAll()).length;if(before)throw new Error('PCB not empty; inspect before reimport');const imported=await eda.pcb_Document.importChanges(__CLI__.args.sch);if(!imported)throw new Error('Import failed');await eda.pcb_Document.save();return {imported,boards:await eda.dmt_Board.getAllBoardsInfo(),count:(await eda.pcb_PrimitiveComponent.getAll()).length};""",{'pcb':PCB,'sch':SCH,'name':PROJECT.name},240),flush=True)
    elif sys.argv[1]=='inventory':inventory()
