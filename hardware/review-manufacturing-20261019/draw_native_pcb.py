"""Review visualization of real native pad coordinates (no invented component bodies)."""
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A3,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from native_review import ROOT
from physical_geometry import actual_pad

OUT=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2');OUT.mkdir(parents=True,exist_ok=True)
data=json.loads((ROOT/'pcb-pad-inventory.json').read_text(encoding='utf-8'))
copper=json.loads((ROOT/'pcb-current-copper.json').read_text(encoding='utf-8'))
drill_rows=json.loads((ROOT/'native-drill-audit.json').read_text(encoding='utf-8'))['actual_native_drilled_pads']
drills={(p['ref'],p['pad']):p for p in drill_rows}
checkpoint=json.loads((ROOT/'route-checkpoint-0clear-149open.json').read_text(encoding='utf-8'))
assert len(copper['lines'])==checkpoint['lines'] and len(copper['vias'])==checkpoint['vias']
count=len(data);pad_count=sum(len(c['pads']) for c in data)
S=20;L=90;T=100;W=2980;H=2220
im=Image.new('RGB',(W,H),'#f3f6fa');d=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
head=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',28)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
def xy(x,y):return L+x*S,T+(100-y)*S
d.text((L,18),'DUAL SCREEN CARRIER V2 / ACTUAL PADS AND COPPER',font=head,fill='#12243b')
d.text((L,57),f'Provisional 140 x 100 mm | {count} components / {pad_count} pads | ROUTING INCOMPLETE / NOT FOR ORDER',font=font,fill='#9b2c20')
d.rectangle([xy(0,100),xy(140,0)],fill='#e9f3ed',outline='#216044',width=3)
for x in range(0,141,10):
    d.line([xy(x,0),xy(x,100)],fill='#dce7df',width=1)
    d.text((xy(x,0)[0]-7,T+2008),str(x),fill='#53616e',font=small)
for y in range(0,101,10):
    d.line([xy(0,y),xy(140,y)],fill='#dce7df',width=1)
    d.text((L-35,xy(0,y)[1]-7),str(y),fill='#53616e',font=small)
for layer,color in [(2,'#5575ba'),(1,'#b46b54')]:
    for line in copper['lines']:
        if line['layer']!=layer:continue
        d.line([xy(line['x1']*.0254,line['y1']*.0254),xy(line['x2']*.0254,line['y2']*.0254)],fill=color,width=max(1,round(line['width']*.0254*S)))
for via in copper['vias']:
    cx,cy=xy(via['x']*.0254,via['y']*.0254);r=via['diameter']*.0254*S/2
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill='#c4a05b',outline='#364456')
    r=via['hole']*.0254*S/2;d.ellipse((cx-r,cy-r,cx+r,cy+r),fill='#e9f3ed')
for c in data:
    ref=c['ref'];pads=c['pads']
    color='#71419b' if any(p['net'].startswith(('L0_','L1_','L2_','L3_','L4_','L5_')) for p in pads) else '#276088'
    if ref in ['F1','Q1','J13','U17','U18','U13']:color='#b0681e'
    for p in pads:
        x=p['x']*.0254;y=p['y']*.0254;w=p['shape'][1]*.0254;h=p['shape'][2]*.0254
        a=math.radians(p['rotation']);cx,cy=xy(x,y)
        if p['shape'][0]=='ELLIPSE' and abs(w-h)<.01:
            d.ellipse((cx-w*S/2,cy-h*S/2,cx+w*S/2,cy+h*S/2),fill='#c7a95f',outline='#775e27',width=1)
        else:
            pts=[]
            for xx,yy in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]:
                pts.append((cx+(xx*math.cos(a)-yy*math.sin(a))*S,cy-(xx*math.sin(a)+yy*math.cos(a))*S))
            d.polygon(pts,fill='#c7a95f',outline='#775e27')
        hole=drills.get((ref,p['n']))
        if hole:
            shape=['OVAL' if abs(hole['width_mm']-hole['height_mm'])>.01 else 'ELLIPSE',hole['width_mm']/.0254,hole['height_mm']/.0254,0]
            g=actual_pad({**p,'shape':shape})
            d.polygon([xy(a,b) for a,b in g.exterior.coords],fill='#f3f6fa',outline='#53616e')
    xs=[p['x']*.0254 for p in pads];ys=[p['y']*.0254 for p in pads]
    x=(min(xs)+max(xs))/2;y=(min(ys)+max(ys))/2
    # Box denotes pad extents, not an inferred body/courtyard.
    bx0,by0=xy(min(xs)-.8,max(ys)+.8);bx1,by1=xy(max(xs)+.8,min(ys)-.8)
    d.rectangle((bx0,by0,bx1,by1),outline=color,width=1)
    labelx,labely=xy(x,y)
    d.text((labelx,labely),ref,font=font,fill=color,anchor='mm',stroke_width=1,stroke_fill='#f4f8f4')
component_pad_ids={p['id'] for c in data for p in c['pads']}
for p in copper.get('pads',[]):
    if p['id'] in component_pad_ids:continue
    cx,cy=xy(p['x']*.0254,p['y']*.0254);r=p['shape'][1]*.0254*S/2
    hole=drills.get(('BOARD',p['n']))
    fill='#f3f6fa' if hole else '#c7a95f'
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill,outline='#53616e',width=2)
    d.text((cx+10,cy-14),p['n'],fill='#364456',font=small)
d.text((L,2148),'Copper: top red / bottom blue. Boxes denote pad extents, not component bodies or courtyards. Ground pours not shown.',font=font,fill='#34495d')
d.text((L,2178),f"Snapshot: {len(copper['lines'])} tracks / {len(copper['vias'])} vias; native DRC 0 clearance / 0 physical / 149 open. NOT FOR ORDER.",font=font,fill='#34495d')
im.save(OUT/'pcb-native-pad-placement.png')
im.crop((L,T+(100-74)*S,L+140*S,T+(100-27)*S)).save(OUT/'pcb-core-pad-detail.png')
pdfmetrics.registerFont(TTFont('ReviewArial','C:/Windows/Fonts/arial.ttf'))
pdf=canvas.Canvas(str(OUT/'pcb-pad-placement-review.pdf'),pagesize=landscape(A3))
pw,ph=landscape(A3)
for path,title in [(OUT/'pcb-native-pad-placement.png','Native PCB pad placement - provisional / not for fabrication'),(OUT/'pcb-core-pad-detail.png','Core pad detail - actual pads, not component bodies')]:
    img=Image.open(path);iw,ih=img.size;scale=min((pw-50)/iw,(ph-80)/ih)
    pdf.setFont('ReviewArial',12);pdf.drawString(25,ph-25,title)
    pdf.drawImage(ImageReader(img),25+(pw-50-iw*scale)/2,35+(ph-80-ih*scale)/2,width=iw*scale,height=ih*scale)
    pdf.setFont('ReviewArial',9);pdf.drawString(25,16,f'{count} components / {pad_count} pads. Native copper shown; routing and manufacturing release are incomplete.')
    pdf.showPage()
pdf.save()
print('Created actual pad placement PNG and 2-page review PDF',flush=True)
