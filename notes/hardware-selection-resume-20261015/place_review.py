"""Place major candidate parts in the already-backed-up, existing review sheet.

This is a sourcing sheet with NO wires and addIntoPcb=false. It is not a circuit
or manufacturing release. The smaller passive BOM is supplied separately.
"""
import json
from pathlib import Path
from cli_runner import call,ROOT

REPO=ROOT.parents[1]
CATALOG=REPO/'hardware/pitch-sliders/selection-20261015/catalog-checked.json'


def main():
    session=json.loads((ROOT/'evidence/open-prototype-resumed.json').read_text(encoding='utf-8'))['value']['sessionId']
    catalog={p['mpn']:p for p in json.loads(CATALOG.read_text(encoding='utf-8'))}
    placements=[
        ('U1','CD74HC4067M96',160,600),('U2','CD74HC4067M96',480,600),
        ('U3','SN74LVC14ADR',820,600),('U4','SN74LV595ADR',160,380),
        ('U5','SN74LV165ADR',480,380),('U6','24LC256-I/SN',820,380),
        ('SW1','EC11E15244B2',160,240),
    ]+[(f'SW{i+2}','TS-1187A-B-A-B',440+i*120,240) for i in range(5)]
    items=[dict(ref=ref,mpn=mpn,x=x,y=y,**{k:catalog[mpn][k] for k in ('lcsc','deviceUuid','libraryUuid')})
           for ref,mpn,x,y in placements]
    code="""const project=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(project?.friendlyName!=='FPGA-Music-Slider-Prototype-20261015'||doc?.uuid!=='ba336973a1f81bda')throw new Error('Wrong project/page');
const previous=await eda.sch_PrimitiveComponent.getAll();const made=[];
for(const p of __CLI__.args.items){
 let c=previous.find(c=>c.getState_Designator()===p.ref);
 if(c){if(c.getState_SupplierId()!==p.lcsc)throw new Error('Existing designator mismatch '+p.ref);}
 else{c=await eda.sch_PrimitiveComponent.create({libraryUuid:p.libraryUuid,uuid:p.deviceUuid},p.x,p.y,undefined,0,false,true,false);
 if(!c)throw new Error('Placement failed '+p.ref);const edit=c.toAsync();edit.setState_Designator(p.ref);await edit.done();}
 made.push({ref:p.ref,id:c.getState_PrimitiveId(),lcsc:p.lcsc,mpn:p.mpn});
}
const text=await eda.sch_PrimitiveText.create(65,780,'SOURCING REVIEW ONLY - NOT WIRED - NOT FOR MANUFACTURING',0,null,null,13,true);
const saved=await eda.sch_Document.save();if(!saved)throw new Error('Save failed');return {made,saved};"""
    result=call('placed-major-candidates',['invoke','--session',session,'--ext-uuid','eda',
        '--code',code,'--args',json.dumps({'items':items}),'--timeout','60000'],75)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
