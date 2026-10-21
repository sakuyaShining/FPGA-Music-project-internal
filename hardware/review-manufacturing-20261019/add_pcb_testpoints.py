"""Add real, named copper test pads; no extra BOM devices or FPGA pins."""
import csv
import json
from native_review import ROOT,invoke
from pcb_candidate import PCB

points=[('GND',8,33),('5V_IN',12,33),('5V_FUSED',16,33),('5V_PROTECTED',20,33),
 ('5V_PERIPH',24,33),('3V3_IO',28,33),('3V3_PERIPH',32,33),('PWR_FAULT_N',36,33),
 ('DAC_3V3',117,67),('GND',121,67),('I2C_SDA',73,49),('I2C_SCL',73,52),
 ('BUS_SCK',73,45),('BUS_MOSI',75.5,42),('BUS_RETURN',73,39),
 ('RC0',20,29),('RC1',65,29),('RC2',116,29),('RC3',20,71),('RC4',65,71),('RC5',116,71)]
rows=[dict(name=f'TP{i+1}',net=n,x_mm=x,y_mm=y,pad_diameter_mm=.8128,
           purpose='RC timing node: pad/probe adds capacitance, compare unprobed readings' if n.startswith('RC') else 'power/bus bring-up') for i,(n,x,y) in enumerate(points)]
value=invoke('v2-add-native-testpoints',"""await eda.dmt_EditorControl.openDocument(__CLI__.args.pcb);const old=await eda.pcb_PrimitivePad.getAll();const r=[];
const names=new Set(__CLI__.args.points.map(p=>p.name));const labels=(await eda.pcb_PrimitiveString.getAll()).filter(p=>names.has(p.getState_Text()));if(labels.length)await eda.pcb_PrimitiveString.delete(labels.map(p=>p.getState_PrimitiveId()));
for(const p of __CLI__.args.points){let pad=old.find(q=>q.getState_PadNumber()===p.name);if(!pad){pad=await eda.pcb_PrimitivePad.create(1,p.name,p.x_mm/0.0254,p.y_mm/0.0254,0,['ELLIPSE',32,32],p.net,null,0,0,0,false,1);if(!pad)throw new Error('Create '+p.name);}else{pad=await eda.pcb_PrimitivePad.modify(pad,{x:p.x_mm/0.0254,y:p.y_mm/0.0254});}
await eda.pcb_PrimitiveString.create(3,p.x_mm/0.0254,(p.y_mm+1.3)/0.0254,p.name,'default',40,6,5,0,false,0,false,false);
r.push({name:p.name,id:pad.getState_PrimitiveId(),net:pad.getState_Net(),x:pad.getState_X(),y:pad.getState_Y()});}await eda.pcb_Document.save();return r;""",{'pcb':PCB,'points':rows},150)
assert len(value)==len(rows)
for a,b in zip(rows,value):
    assert a['net']==b['net'] and abs(a['x_mm']-b['x']*.0254)<.005 and abs(a['y_mm']-b['y']*.0254)<.005
with (ROOT/'pcb-testpoints.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(ROOT/'pcb-testpoints-native.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print('native test pads added and read back:',len(value),flush=True)
