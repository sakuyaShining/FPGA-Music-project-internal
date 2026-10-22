"""Draw measured native copper around a fine-pitch pin on both real layers."""
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from grid_route import capture,MM
from physical_geometry import actual_pad
from native_review import ROOT

net=sys.argv[1];source=capture();(ROOT/f'debug-source-{net}.json').write_text(json.dumps(source),encoding='utf-8')
pad=min((p for p in source['pads'] if p['net']==net),key=lambda p:min(p['shape'][1:3]))
cx,cy=pad['x']*MM,pad['y']*MM;bounds=(cx-4,cy-4,cx+4,cy+4)
S=180;offset=60;size=1560
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
def xy(x,y):return (offset+(x-bounds[0])*S,offset+(bounds[3]-y)*S)
def color(n):
    if n==net:return '#ee2222'
    if n=='GND':return '#777777'
    if n in ['3V3_IO','3V3_PERIPH','DAC_3V3','5V_PERIPH']:return '#d18a00'
    palette=['#2175a3','#189e9b','#7656a8','#32a748','#b4609b','#343dc1']
    return palette[int(hashlib.sha256(n.encode()).hexdigest()[:6],16)%len(palette)]
for layer in [1,2]:
    image=Image.new('RGB',(size,size),'white');draw=ImageDraw.Draw(image)
    draw.text((20,12),f'{net} / native layer {layer} / 1 mm grid / red=target, grey=GND, amber=power',fill='black',font=font)
    for i in range(9):
        x=bounds[0]+i;y=bounds[1]+i
        draw.line([xy(x,bounds[1]),xy(x,bounds[3])],fill='#e8e8e8')
        draw.line([xy(bounds[0],y),xy(bounds[2],y)],fill='#e8e8e8')
    for p in source['lines']:
        if p['layer']!=layer:continue
        a=(p['x1']*MM,p['y1']*MM);b=(p['x2']*MM,p['y2']*MM)
        if max(a[0],b[0])<bounds[0] or min(a[0],b[0])>bounds[2] or max(a[1],b[1])<bounds[1] or min(a[1],b[1])>bounds[3]:continue
        draw.line([xy(*a),xy(*b)],fill=color(p['net']),width=max(1,round(p['width']*MM*S)))
        if min(abs(a[0]-cx)+abs(a[1]-cy),abs(b[0]-cx)+abs(b[1]-cy))<3:
            x,y=xy((a[0]+b[0])/2,(a[1]+b[1])/2);draw.text((x,y),p['net'],fill=color(p['net']),font=font)
    for p in source['pads']:
        if p['layer'] not in [layer,12]:continue
        x,y=p['x']*MM,p['y']*MM
        if not(bounds[0]-1<x<bounds[2]+1 and bounds[1]-1<y<bounds[3]+1):continue
        shape=actual_pad(p)
        if shape.is_empty:continue
        draw.polygon([xy(a,b) for a,b in shape.exterior.coords],fill=color(p['net']),outline='black',width=2)
        draw.text((xy(x,y)[0]-40,xy(x,y)[1]),p['ref']+'.'+p['n']+' '+p['net'],fill='black',font=font)
    for p in source['vias']:
        x,y=p['x']*MM,p['y']*MM
        if not(bounds[0]-1<x<bounds[2]+1 and bounds[1]-1<y<bounds[3]+1):continue
        a,b=xy(x,y);r=p['diameter']*MM*S/2;draw.ellipse((a-r,b-r,a+r,b+r),fill=color(p['net']),outline='black',width=2)
        r=p['hole']*MM*S/2;draw.ellipse((a-r,b-r,a+r,b+r),fill='white')
    path=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')/f'debug-{net}-layer{layer}.png';image.save(path)
print('PIN',pad['ref'],pad['n'],cx,cy,flush=True)
