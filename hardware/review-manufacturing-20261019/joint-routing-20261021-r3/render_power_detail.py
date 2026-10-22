"""Render actual saved power-pin copper for geometric diagnosis, no PCB edits."""
import argparse,json,sys,math
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan')
parser.add_argument('--source',default=str(ROOT/'quality-r1-source-78.json'))
args=parser.parse_args()
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw,ImageFont
import shapely
from physical_geometry import actual_pad
data=json.loads(Path(args.source).read_text(encoding='utf-8'))
if args.plan:
    plan=json.loads(Path(args.plan).read_text(encoding='utf-8'))
    data['lines']=[p for p in data['lines'] if p['id'] not in plan['remove_line_ids']]+plan['additive_power_lines']+plan['bus_lines']+plan.get('ground_lines',[])
    data['vias']+=plan['additive_power_vias']+plan['bus_vias']+plan.get('ground_vias',[])
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',10)
for name,bounds,focus in [('U17',(18,43,33,54),('U17','6')),('U13',(108,56,122,65),('U13','1'))]:
    x0,y0,x1,y1=bounds;S=70;W=round((x1-x0)*S)+80;H=round((y1-y0)*S)+90
    img=Image.new('RGB',(W*2,H),'#f3f6f9');draw=ImageDraw.Draw(img)
    for col,layer in enumerate([1,2]):
        xy=lambda x,y:(col*W+40+(x-x0)*S,50+(y1-y)*S)
        label='OFFLINE CANDIDATE' if args.plan else 'ACTUAL SAVED COPPER'
        draw.text((col*W+20,12),f'{name}: {label} - layer {layer} - not released for manufacture',font=font,fill='#1b2a3b')
        color=lambda net:'#00a4b4' if net=='5V_PERIPH' else '#f29b38' if net=='5V_PROTECTED' else '#9098a2' if net=='GND' else '#a046b7' if net=='BUS_RETURN' else '#ba5261' if layer==1 else '#5c7bb6'
        for p in data['lines']:
            if p['layer']!=layer:continue
            if max(p['x1'],p['x2'])*.0254<x0 or min(p['x1'],p['x2'])*.0254>x1 or max(p['y1'],p['y2'])*.0254<y0 or min(p['y1'],p['y2'])*.0254>y1:continue
            draw.line([xy(p['x1']*.0254,p['y1']*.0254),xy(p['x2']*.0254,p['y2']*.0254)],fill=color(p['net']),width=max(1,round(p['width']*.0254*S)))
        for p in data['vias']:
            x=p['x']*.0254;y=p['y']*.0254
            if not(x0<x<x1 and y0<y<y1):continue
            cx,cy=xy(x,y);r=p['diameter']*.0254*S/2
            draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=color(p['net']),outline='#34465a')
            r=p['hole']*.0254*S/2;draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill='#f3f6f9')
        for p in data['pads']:
            if p['layer'] not in [layer,12]:continue
            x=p['x']*.0254;y=p['y']*.0254
            if not(x0<x<x1 and y0<y<y1):continue
            shape=actual_pad(p);draw.polygon([xy(a,b) for a,b in shape.exterior.coords],fill='#c8ad66',outline='#66572d')
            cx,cy=xy(x,y)
            draw.text((cx+5,cy+2),p['ref']+'.'+p['n'],font=small,fill='#1c2e43')
            draw.text((cx+5,cy+14),p['net'],font=small,fill='#1c2e43')
            if (p['ref'],p['n'])==focus:
                draw.ellipse((cx-12,cy-12,cx+12,cy+12),outline='#e60000',width=3)
        draw.rectangle((col*W+39,49,col*W+40+(x1-x0)*S,50+(y1-y0)*S),outline='#23374b')
    img.save(OUT/(name+('-candidate' if args.plan else '-current')+'-power-detail.png'))
print('Rendered U17/U13 detail; candidate flag',bool(args.plan),'cyan=5V_PERIPH orange=5V_PROTECTED grey=GND purple=BUS_RETURN')
