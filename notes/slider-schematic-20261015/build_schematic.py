"""Turn the backed-up sourcing sheet into a connected prototype draft."""
import csv
import json
from phase import ROOT, REPO, invoke

CAT={p['mpn']:p for p in json.loads((REPO/'hardware/pitch-sliders/selection-20261015/catalog-checked.json').read_text(encoding='utf-8'))}
P1='ba336973a1f81bda'
SCH='7a8553eae6bc33bb'

def prepare():
    code="""const p=await eda.dmt_Project.getCurrentProjectInfo();if(p?.friendlyName!=='FPGA-Music-Slider-Prototype-20261015')throw new Error('Wrong project');
await eda.dmt_EditorControl.openDocument(__CLI__.args.page);
return {doc:await eda.dmt_SelectControl.getCurrentDocumentInfo(),parts:(await eda.sch_PrimitiveComponent.getAll()).filter(c=>c.getState_SupplierId()).map(c=>({ref:c.getState_Designator(),id:c.getState_PrimitiveId(),pins:[]}))};"""
    print(json.dumps(invoke('activate',code,{'page':P1}),ensure_ascii=True))
    code="""const pins=[];for(const c of await eda.sch_PrimitiveComponent.getAll()){if(!c.getState_SupplierId())continue;const pp=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());pins.push({ref:c.getState_Designator(),pins:pp.map(p=>({n:p.getState_PinNumber(),r:p.getState_Rotation(),x:p.getState_X(),y:p.getState_Y()}))});}return pins;"""
    print(json.dumps(invoke('pin-directions',code),ensure_ascii=True))

def pages():
    code="""const pages=await eda.dmt_Schematic.getAllSchematicPagesInfo();const result={};
await eda.dmt_Schematic.modifySchematicPageName(__CLI__.args.p1,'01_Core_and_controls');result.core=__CLI__.args.p1;
for(const [key,name] of [['rc','02_Electrodes_and_RC'],['support','03_Power_and_interface']]){let p=pages.find(p=>p.name===name);let id=p?.uuid;if(!id){id=await eda.dmt_Schematic.createSchematicPage(__CLI__.args.sch);if(!id)throw new Error('Create page failed');await eda.dmt_Schematic.modifySchematicPageName(id,name);}result[key]=id;}return result;"""
    data=invoke('pages',code,{'p1':P1,'sch':SCH})
    (ROOT/'pages.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');print(data)

def part(ref,mpn,x,y):
    return dict(ref=ref,mpn=mpn,x=x,y=y,**{k:CAT[mpn][k] for k in ('lcsc','deviceUuid','libraryUuid')})

def placements():
    pp=json.loads((ROOT/'pages.json').read_text())
    rows=[]
    for i in range(12):rows.append(part(f'R{21+i}','0603WAF1001T5E',220+(i%3)*300,700-(i//3)*125))
    for i in range(2):rows.append(part(f'R{1+i}','RC0603FR-0747KL',230+i*470,150))
    for i in range(6):
        mpn=['CL10C100JB8NNNC','GRM1885C1H470JA01D','CL10C101JB8NNNC'][i%3]
        rows.append(part(f'C{16+i}',mpn,170+(i%3)*340,225-(i//3)*70))
    support=[]
    for i in range(6):support.append(part(f'C{1+i}','CL10B104KB8NNNC',150+(i%3)*340,690-(i//3)*100))
    support.append(part('C7','CL10A105KO8NNNC',150,490))
    for i in range(2):support.append(part(f'R{3+i}','RC0603FR-07220RL',490+i*340,490))
    for i in range(8):
        mpn='0603WAF2201T5E' if i<2 else ('0603WAF4701T5E' if i==2 else 'RC0603FR-0710KL')
        support.append(part(f'R{41+i}',mpn,150+(i%4)*250,385-(i//4)*95))
    for i in range(2):support.append(part(f'R{51+i}','0603WAF4701T5E',150+i*250,180))
    header=json.loads((ROOT/'evidence/search-header.json').read_text(encoding='utf-8'))['value']
    h=next(h for h in header if h['supplierId']=='C247920' and h['manufacturerId']=='2.54-1*12P反弯针')
    support.append(dict(ref='J1',mpn=h['manufacturerId'],x=820,y=160,lcsc=h['supplierId'],deviceUuid=h['uuid'],libraryUuid=h['libraryUuid']))
    (ROOT/'connector-candidate.json').write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);const previous=await eda.sch_PrimitiveComponent.getAll();const made=[];
for(const p of __CLI__.args.items){let c=previous.find(c=>c.getState_Designator()===p.ref);if(c){if(c.getState_SupplierId()!==p.lcsc)throw new Error('Mismatch '+p.ref);}else{c=await eda.sch_PrimitiveComponent.create({libraryUuid:p.libraryUuid,uuid:p.deviceUuid},p.x,p.y,undefined,0,false,true,true);if(!c)throw new Error('Create '+p.ref);const e=c.toAsync();e.setState_Designator(p.ref);await e.done();}const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());made.push({ref:p.ref,id:c.getState_PrimitiveId(),mpn:c.getState_ManufacturerId(),lcsc:c.getState_SupplierId(),pins:pins.map(p=>({n:p.getState_PinNumber(),name:p.getState_PinName(),r:p.getState_Rotation(),x:p.getState_X(),y:p.getState_Y()}))});}return {saved:await eda.sch_Document.save(),made};"""
    for key,items in [('rc',rows),('support',support)]:
        result=invoke('placed-'+key,code,{'page':pp[key],'items':items});print(key,len(result['made']),result['saved'])

if __name__=='__main__':
    import sys
    {'prepare':prepare,'pages':pages,'placements':placements}[sys.argv[1]]()
