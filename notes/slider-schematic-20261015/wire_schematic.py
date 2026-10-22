"""Wire real library pin coordinates; separately audit native exported connectivity."""
import csv
import json
from phase import ROOT,REPO,PROJECT,invoke

PAGES=json.loads((ROOT/'pages.json').read_text())

def expected():
    rows=list(csv.DictReader((REPO/'notes/slider-prototype-20261015/connections-review.csv').open(encoding='utf-8-sig')))
    nets={}
    for r in rows:
        ref=r['Reference']
        if ref.startswith('E') or ref=='J_FPGA':continue
        nets.setdefault(ref,{})[r['Pin']]=r['Net']
    nets['SW1']={'A':'ENC_A','B':'ENC_B','C':'GND','D':'ENC_PUSH','E':'GND','6':None,'7':None}
    for i in range(5):
        n=f'PRESET_{i}' if i<4 else 'EDIT'
        nets[f'SW{i+2}']={'1':n,'2':n,'3':'GND','4':'GND'}
    nets['J1']={str(i+1):n for i,n in enumerate(['3V3','GND','BUS_SCK','BUS_MOSI','SCAN_LATCH','INPUT_LOAD_N','INPUT_DATA','FPGA_SENSE_A','FPGA_SENSE_B','STORE_SDA','STORE_SCL','GND'])}
    nets['J2']={str(i+1):f'STRIP{i//3}_E{i%3}' for i in range(12)}
    for pp in nets.values():
        for k,v in pp.items():
            if v and v.startswith('NC_'):pp[k]=None
    (ROOT/'expected-pin-nets.json').write_text(json.dumps(nets,indent=2)+'\n',encoding='utf-8')
    return nets

def add_electrode_header():
    h=json.loads((ROOT/'connector-candidate.json').read_text(encoding='utf-8'))
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);let c=(await eda.sch_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()==='J2');if(!c){c=await eda.sch_PrimitiveComponent.create({libraryUuid:__CLI__.args.h.libraryUuid,uuid:__CLI__.args.h.uuid},1030,500,undefined,0,false,true,true);if(!c)throw new Error('Header placement');const e=c.toAsync();e.setState_Designator('J2');await e.done();}return {id:c.getState_PrimitiveId(),saved:await eda.sch_Document.save()};"""
    print(invoke('electrode-header',code,{'page':PAGES['rc'],'h':h}))

def wire(key):
    nets=expected()
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);
const wireIds=await eda.sch_PrimitiveWire.getAllPrimitiveId();if(wireIds.length)throw new Error('Already has wires; inspect before rerunning');
if(__CLI__.args.key==='core'){for(const t of await eda.sch_PrimitiveText.getAll())await eda.sch_PrimitiveText.delete(t);}
const result=[];for(const c of await eda.sch_PrimitiveComponent.getAll()){
const ref=c.getState_Designator();if(!__CLI__.args.nets[ref])continue;
const edit=c.toAsync();edit.setState_AddIntoPcb(true);if(ref==='SW1')edit.setState_Rotation(90);if(ref==='U1'||ref==='U4')edit.setState_X(200);if(ref==='U2'||ref==='U5')edit.setState_X(550);if(ref==='U3'||ref==='U6')edit.setState_X(940);await edit.done();
const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
for(const p of pins){const n=p.getState_PinNumber();if(!(n in __CLI__.args.nets[ref]))throw new Error('No net assignment '+ref+'.'+n);const net=__CLI__.args.nets[ref][n];
if(net===null){const e=p.toAsync();e.setState_NoConnected(true);await e.done();result.push({ref,pin:n,net:null,nc:true});continue;}
const x=p.getState_X(),y=p.getState_Y(),r=p.getState_Rotation();const dx=r===0?30:r===180?-30:0;const dy=r===90?30:r===270?-30:0;if(!dx&&!dy)throw new Error('Unexpected pin angle');
const w=await eda.sch_PrimitiveWire.create([x,y,x+dx,y+dy],net);if(!w)throw new Error('Wire '+ref+'.'+n);
const label=await eda.sch_PrimitiveComponent.createNetPort('BI',net,x+dx,y+dy,r);if(!label)throw new Error('Port '+ref+'.'+n);
result.push({ref,pin:n,net,x,y,r,wire:w.getState_PrimitiveId(),label:label.getState_PrimitiveId()});}}
await eda.sch_PrimitiveText.create(65,780,__CLI__.args.title,0,null,null,13,true);
for(let i=0;i<__CLI__.args.notes.length;i++)await eda.sch_PrimitiveText.create(65,100-i*15,__CLI__.args.notes[i],0,null,null,8,false);
const saved=await eda.sch_Document.save();if(!saved)throw new Error('Save failed');return {saved,pins:result};"""
    title={'core':'01 - CORE / CONTROLS - ELECTRICAL DRAFT, NOT PRODUCTION RELEASE',
           'rc':'02 - FOUR SLIDERS / RC - J2 TO SEPARATE ELECTRODE COUPON',
           'support':'03 - POWER / HOST INTERFACE - LOGICAL SIGNALS, NOT NANO PIN NUMBERS'}[key]
    notes={
      'core':['All ICs at 3.3V. U3 unused inputs tied LOW; unused outputs explicitly NC.',
              '595 power-up outputs unknown: initialize and latch before enabling measurements.',
              'Switch 1/2 common and 3/4 common from library symbol; verify supplier drawing before PCB.'],
      'rc':['R21..32 = 1k per electrode. R1/R2 = 47k initial, subject to physical measurement.',
            'C16..21 = 10/47/100pF references. J2 carries 12 electrodes; no force measurement.',
            'ESD device and electrode footprint/overlay pending. Do not fabricate this draft.'],
      'support':['C1..6 = 100nF, each next to one IC; C7 = 1uF rail bulk.',
                 'J1 is a 12-way cable connector; exact Nano header assignment remains pending.',
                 'Reserve Nano onboard TF pins 80..85. Do not share TF clock with display/scan SPI.']}[key]
    value=invoke('wired-'+key,code,{'page':PAGES[key],'key':key,'nets':nets,'title':title,'notes':notes})
    print(key,'pins',len(value['pins']),'saved',value['saved'])

def export(key):
    out=PROJECT/'schematic-draft-exports';out.mkdir(exist_ok=True)
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);const image=await eda.sch_ManufactureData.getPngFile(__CLI__.args.key,{width:3000});if(!image)throw new Error('No PNG');const imageSaved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.dir,image,__CLI__.args.key+'.png');return {imageSaved};"""
    v=invoke('export-'+key,code,{'page':PAGES[key],'key':key,'dir':out.as_posix()+'/'})
    assert v['imageSaved']
    print(key,'image saved',v['imageSaved'])

if __name__=='__main__':
    import sys
    if sys.argv[1]=='header':add_electrode_header()
    elif sys.argv[1]=='wire':wire(sys.argv[2])
    elif sys.argv[1]=='export':export(sys.argv[2])
