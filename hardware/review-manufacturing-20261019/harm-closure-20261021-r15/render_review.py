"""Source-derived drawing, deliberately labelled as geometry rather than EDA screenshot."""
from pathlib import Path
import sys,json,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch,Circle
from matplotlib.path import Path as MPath
from matplotlib.lines import Line2D
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
cap=read(BASE/'native-verified-capture.json');review=read(BASE/'actual-layout-review.json')
pcb=PROJECT/'pcb/PCB1.epcb2'
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==review['pcb_sha256']
native=read_native(pcb);planes=poured_planes(native)
def fill(ax,geom,**kw):
    polys=[geom] if geom.geom_type=='Polygon' else list(geom.geoms)
    for p in polys:
        if p.geom_type!='Polygon':continue
        rings=[p.exterior,*p.interiors];verts=[];codes=[]
        for ring in rings:
            xy=list(ring.coords);verts.extend(xy);codes.extend([MPath.MOVETO]+[MPath.LINETO]*(len(xy)-2)+[MPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MPath(verts,codes),**kw))
fig,axes=plt.subplots(1,2,figsize=(15,7.5))
colors={1:'#d1384e',16:'#7659cd'}
for ax,(ref,title) in zip(axes,[(15,'Top signals / actual inner-1 ground'),(2,'Inner-2 signals / actual bottom ground')]):
    fill(ax,planes[ref],facecolor='#bfdbc9',edgecolor='none',alpha=.75,zorder=0)
    for (kind,i),p in native.items():
        if kind!='LINE' or p.get('layerId') not in [1,16]:continue
        lay=p['layerId'];selected=p.get('netName')=='HARM_CS_N'
        if not selected and lay!=(1 if ref==15 else 16):continue
        ax.plot([p['startX']*.0254,p['endX']*.0254],[p['startY']*.0254,p['endY']*.0254],color=colors[lay] if selected else '#b5b4b0',lw=1.7 if selected else .45,alpha=1 if selected else .6,zorder=4 if selected else 1)
    for p in cap['pads']:
        if p['layer'] not in [1,12]:continue
        fill(ax,actual_pad(p),facecolor='#e7b44c' if p['net']=='HARM_CS_N' else '#c1bda9',edgecolor='#8a8169',linewidth=.25,zorder=2)
    for v in cap['vias']:
        if v['net']!='HARM_CS_N':continue
        xy=(v['x']*.0254,v['y']*.0254)
        ax.add_patch(Circle(xy,v['diameter']*.0254/2,facecolor='#fff',edgecolor='#663ab1',lw=1,zorder=5))
        ax.add_patch(Circle(xy,v['hole']*.0254/2,facecolor='#555',zorder=6))
    for j,v in enumerate(review['actual_ground_stitch_contacts'],1):
        ax.add_patch(Circle(v['xy_mm'],.3048,facecolor='#fff',edgecolor='#007a5e',lw=1.5,zorder=7))
        ax.add_patch(Circle(v['xy_mm'],.1524,facecolor='#007a5e',zorder=8))
        ax.annotate('G'+str(j),v['xy_mm'],xytext=(5,6),textcoords='offset points',fontsize=7,color='#006149',zorder=9)
    for refname,dx,dy in [('J6',-5,-3),('U11',-2,2),('U15',-2,2),('R30',1,-2)]:
        ps=[p for p in cap['pads'] if p['ref']==refname and p['net']=='HARM_CS_N']
        if not ps:continue
        xy=(sum(p['x'] for p in ps)/len(ps)*.0254,sum(p['y'] for p in ps)/len(ps)*.0254)
        ax.annotate(refname,xy,xytext=(xy[0]+dx,xy[1]+dy),fontsize=9,fontweight='bold',arrowprops=dict(arrowstyle='-',lw=.7),zorder=10)
    ax.plot(77.0001,39.00043,'x',color='#626262',ms=8,zorder=10)
    ax.annotate('R30 previous', (77.0001,39.00043),xytext=(78,37),fontsize=8,color='#626262')
    ax.set(xlim=(46,94),ylim=(73,34),xlabel='x (mm)',ylabel='y (mm)',title=title,aspect='equal')
    ax.grid(alpha=.15);ax.tick_params(labelsize=8)
fig.suptitle('R15 HARM_CS_N closure - source-derived native geometry',fontsize=15)
fig.legend(handles=[Line2D([0],[0],color=colors[1],lw=2,label='HARM top'),Line2D([0],[0],color=colors[16],lw=2,label='HARM inner-2'),Line2D([0],[0],color='#007a5e',marker='o',lw=0,label='5 added GND stitches')],loc='lower center',ncol=3,bbox_to_anchor=(.5,.075),frameon=False)
fig.text(.5,.045,'Native DRC: 0 clearance / 0 physical / 58 connection errors. HARM connected: 72.27 mm, 5 signal vias.',ha='center',fontsize=10)
fig.text(.5,.018,'Green = actual filled GND with holes preserved. Local view; no SI, mechanical or fabrication release.',ha='center',fontsize=9,color='#555')
fig.tight_layout(rect=[0,.12,1,.95]);fig.savefig(BASE/'harm-native-review.png',dpi=170);plt.close(fig)
print(BASE/'harm-native-review.png')
