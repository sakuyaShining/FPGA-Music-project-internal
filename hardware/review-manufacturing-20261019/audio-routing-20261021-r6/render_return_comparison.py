"""Plot actual native reference geometry, explicitly mark rejected r6."""
import sys,json
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from native_plane_geometry import poured_planes
from resume_offline import read_native
from shapely.geometry.polygon import orient
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch,Circle
from matplotlib.collections import LineCollection
old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');new=read_native(PROJECT/'pcb/PCB1.epcb2');op=poured_planes(old);np=poured_planes(new)
def polys(g):
 if g.geom_type=='Polygon':yield g
 elif hasattr(g,'geoms'):
  for q in g.geoms:yield from polys(q)
def plane(ax,g):
 for p in polys(g):
  p=orient(p,1);vertices=[];codes=[]
  for ring in [p.exterior,*p.interiors]:
   xy=list(ring.coords);vertices+=xy;codes +=[MPath.MOVETO]+[MPath.LINETO]*(len(xy)-2)+[MPath.CLOSEPOLY]
  ax.add_patch(PathPatch(MPath(vertices,codes),facecolor='#365b52',edgecolor='none'))
colors={'I2S_BCK':'#ffcc66','I2S_DIN':'#ff7ca8','I2S_LRCK':'#66c9ff'}
fig,axes=plt.subplots(2,2,figsize=(15,10),facecolor='#101f29')
for ax,raw,planes,signal,reference,nets,title in [
 (axes[0,0],old,op,2,16,list(colors),'ACTIVE R5: bottom audio over inner16 GND'),
 (axes[0,1],new,np,16,2,['I2S_BCK'],'REJECTED R6: BCK inner16 over bottom GND'),
 (axes[1,0],new,np,16,2,['I2S_DIN','I2S_LRCK'],'REJECTED R6: DIN/LRCK inner16 over bottom GND'),
 (axes[1,1],new,np,2,16,['I2S_LRCK'],'REJECTED R6: LRCK bottom over inner16 GND')]:
 plane(ax,planes[reference])
 for net in nets:
  segments=[[(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)] for (k,i),p in raw.items() if k=='LINE' and p.get('layerId')==signal and p['netName']==net]
  ax.add_collection(LineCollection(segments,colors=colors[net],linewidths=1.5,label=net,zorder=4))
  for (k,i),p in raw.items():
   if k=='VIA' and p['netName']==net:ax.add_patch(Circle((p['centerX']*.0254,p['centerY']*.0254),.4,facecolor='none',edgecolor=colors[net],linewidth=1,zorder=5))
 ax.set_facecolor('#101f29');ax.set_xlim(24,105);ax.set_ylim(24,76);ax.set_aspect('equal');ax.set_title(title,color='white',fontsize=10);ax.tick_params(colors='#b3c4cc',labelsize=8);ax.set_xlabel('mm',color='#b3c4cc');ax.set_ylabel('mm',color='#b3c4cc');ax.legend(loc='lower left',fontsize=7)
fig.suptitle('ACTUAL SAVED NATIVE COPPER | green = nearest reference GND | dark = no local reference GND\nR6: 27 -> 10 signal vias, but reference coverage insufficient; ACTIVE R5 PRESERVED | not SI signoff / not for fabrication',color='white',fontsize=12)
fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(BASE/'actual-return/audio-reference-comparison.png',dpi=170);plt.close(fig)
print('Actual native reference comparison rendered',flush=True)
