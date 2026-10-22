"""Source-derived copper-centerline comparison of the actual saved construction states."""
from pathlib import Path
import sys,json
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from resume_offline import read_native
from physical_geometry import actual_pad
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Circle
read=lambda p:json.loads(p.read_text(encoding='utf8'))
oldcap=read(ROOT/'regional-layout-20261021-r19/native-stage2-capture.json');cap=read(ROOT/'regional-net-rebuild-20261021-r23/checkpoint-capture.json')
fig,axes=plt.subplots(1,2,figsize=(15,7))
colors={'3V3_IO':'#7b38b1','3V3_PERIPH':'#dc8126','DISP_MOSI':'#007c9b','TP_RESET_N':'#007c9b','VIS_CS_N':'#007c9b','VIS_BL_EN':'#007c9b'}
groundids=set(read(ROOT/'regional-net-rebuild-20261021-r23/native-ground-pad-repair.json')['createdL'])
for ax,(title,project,c) in zip(axes,[('R19 stage 2: 84 open objects',Path(info['source_project']),oldcap),('R21 after recovery: 65 open objects',PROJECT,cap)]):
    raw=read_native(project/'pcb/PCB1.epcb2')
    for (k,i),p in raw.items():
        if k!='LINE' or p.get('layerId') not in [1,16]:continue
        color='#24964b' if project==PROJECT and i in groundids else colors.get(p['netName'],'#aeb4b8')
        selected=color!='#aeb4b8'
        ax.plot([p['startX']*.0254,p['endX']*.0254],[p['startY']*.0254,p['endY']*.0254],color=color,lw=1.2 if selected else .35,alpha=1 if selected else .6,zorder=3 if selected else 1)
    for p in c['pads']:
        if p['layer'] not in [1,12]:continue
        q=actual_pad(p);ax.add_patch(Polygon(list(q.exterior.coords),facecolor='#dfc98c',edgecolor='#777',lw=.3,zorder=4))
    for (k,i),p in raw.items():
        if k=='VIA':ax.add_patch(Circle((p['centerX']*.0254,p['centerY']*.0254),p['viaDiameter']*.0254/2,facecolor='#2d9b60' if p['netName']=='GND' else '#5777a7',edgecolor='white',lw=.4,zorder=5))
    for ref in ['U8','U9','U15','C35','R30','R31','R63','R64']:
        ps=[p for p in c['pads'] if p['ref']==ref];x=sum(p['x'] for p in ps)/len(ps)*.0254;y=sum(p['y'] for p in ps)/len(ps)*.0254
        ax.text(x,y-1.2 if ref.startswith(('C','R')) else y,ref,ha='center',va='center',fontsize=9,fontweight='bold',bbox=dict(facecolor='white',edgecolor='none',alpha=.8,pad=.4),zorder=8)
    ax.set(xlim=(54,94),ylim=(57,35),aspect='equal',title=title,xlabel='x (mm)',ylabel='y (mm)');ax.grid(alpha=.15)
fig.suptitle('Control/display corridor: actual saved copper centerlines and pad geometry',fontsize=14)
fig.text(.5,.13,'Purple: 3V3_IO   Orange: 3V3_PERIPH   Blue: repaired signals   Green: ground vias / explicit ground-pad repair',ha='center',fontsize=10)
fig.text(.5,.075,'Final saved/reopened native DRC: 0 clearance errors, 0 physical errors, 65 open objects. WORK IN PROGRESS.',ha='center',fontsize=11,color='#a53432')
fig.text(.5,.035,'No placement, component type, board outline, layer or connector changes in this recovery. R15 remains the stable checkpoint. Not for fabrication.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.18,1,.94]);fig.savefig(BASE/'regional-recovery-before-after.png',dpi=170);plt.close(fig)
print(BASE/'regional-recovery-before-after.png')
