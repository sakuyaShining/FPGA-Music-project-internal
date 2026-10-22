"""Draw actual native before/after geometry, clearly labelled as construction work."""
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
sourcecap=read(ROOT/info['source_capture']);cap=read(BASE/'native-stage2-capture.json')
fig,axes=plt.subplots(1,2,figsize=(15,8))
colors={'U15':'#bc3747','C35':'#df881d','R30':'#b35c26','R31':'#b35c26','R63':'#257b9e','R64':'#257b9e','TP13':'#257b9e','TP14':'#257b9e'}
for ax,(title,project,c) in zip(axes,[('Preserved source - before regional changes',Path(info['source_project']),sourcecap),('Working copy - after coordinated placement',PROJECT,cap)]):
    doc=read_native(project/'pcb/PCB1.epcb2')
    for (k,i),p in doc.items():
        if k!='LINE' or p.get('layerId') not in [1,16]:continue
        clock=p.get('netName')=='DISP_SCK'
        ax.plot([p['startX']*.0254,p['endX']*.0254],[p['startY']*.0254,p['endY']*.0254],color='#694cc8' if clock else '#c7c9c7',lw=1.3 if clock else .35,alpha=1 if clock else .6,zorder=3 if clock else 0)
    for p in c['pads']:
        if p['layer'] not in [1,12]:continue
        q=actual_pad(p);ax.add_patch(Polygon(list(q.exterior.coords),closed=True,facecolor=colors.get(p['ref'],'#d1c9a7'),edgecolor='#777',lw=.25,zorder=4))
    for ref in ['U7','U8','U9','U10','U11','U14','U15','C8','C9','C35','R30','R31','R63','R64','TP11','TP12','TP13','TP14']:
        ps=[p for p in c['pads'] if p['ref']==ref]
        if not ps:continue
        x=sum(p['x'] for p in ps)/len(ps)*.0254;y=sum(p['y'] for p in ps)/len(ps)*.0254
        dy=-1.4 if ref in ['C35','R30','R31','C8','C9','R63','R64'] else 0
        if ref in ['TP13','TP14']:dy=-1.3
        if ref in ['TP11','TP12']:dy=.8
        ax.text(x,y+dy,ref,ha='center',va='center',fontsize=8,color=colors.get(ref,'#353535'),fontweight='bold',bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=.2),zorder=10)
    ax.set(xlim=(43,96),ylim=(64,29),aspect='equal',title=title,xlabel='x (mm)',ylabel='y (mm)');ax.grid(alpha=.15)
    if project==PROJECT:
        # Intended bus directions, not a claim that these connections are complete.
        ax.annotate('bus inputs',xy=(81.1,44.6),xytext=(75.7,36.5),fontsize=9,color='#a12739',arrowprops=dict(arrowstyle='->',color='#a12739'))
        ax.annotate('display outputs',xy=(86.9,43.4),xytext=(88.2,36.5),fontsize=9,color='#a12739',arrowprops=dict(arrowstyle='->',color='#a12739'))
fig.suptitle('Control/display corridor: coordinated layout and local rerouting',fontsize=15)
fig.text(.5,.075,'Red: rotated U15. Orange: relocated decoupling/bias parts. Blue: bus pull-downs/test pads. Purple: connected display clock.',ha='center',fontsize=10)
fig.text(.5,.043,'WORK IN PROGRESS: native 0 clearance / 0 physical / 84 open objects. Other disturbed nets and power ports still require reconnection.',ha='center',fontsize=10,color='#ac2539')
fig.text(.5,.016,'Source-derived native geometry; PCB outline, layers, connectors, component types and product functions preserved. No manufacturing release.',ha='center',fontsize=9,color='#555')
fig.tight_layout(rect=[0,.12,1,.94]);fig.savefig(BASE/'regional-layout-stage2-before-after.png',dpi=170);plt.close(fig)
print(BASE/'regional-layout-stage2-before-after.png')
