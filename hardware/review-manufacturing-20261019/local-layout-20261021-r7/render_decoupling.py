"""Compare actual native r5/r7 local copper and real pads."""
import sys,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from resume_offline import read_native
from physical_geometry import actual_pad
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon,Circle
old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');new=read_native(PROJECT/'pcb/PCB1.epcb2');before=json.loads(Path(info['source_capture']).read_text(encoding='utf-8'));after=json.loads((BASE/'native-verified-capture.json').read_text(encoding='utf-8'));review=json.loads((BASE/'final-layout-review.json').read_text(encoding='utf-8'));assert hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest()==review['pcb_sha256']
fig,axes=plt.subplots(1,2,figsize=(14,6.5),facecolor='#101f29')
for ax,raw,capture,title in [(axes[0],old,before,'R5 preserved baseline: C35 VCC spur 10.11 mm'),(axes[1],new,after,'R7 verified: C35 VCC spur 2.38 mm, GND stub 0.90 mm')]:
 ax.set_facecolor('#101f29')
 for net,color,alpha in [(None,'#9db8c8',.32),('3V3_PERIPH','#ffcf69',1),('GND','#70dba5',.8)]:
  ls=[[(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)] for (k,i),p in raw.items() if k=='LINE' and p.get('layerId')==1 and (p['netName']==net if net else p['netName'] not in ['3V3_PERIPH','GND'])];ax.add_collection(LineCollection(ls,colors=color,linewidths=1.6 if net else .65,alpha=alpha))
 for p in capture['pads']:
  q=actual_pad(p)
  if q.bounds[2]<72 or q.bounds[0]>91 or q.bounds[3]<36 or q.bounds[1]>53:continue
  ax.add_patch(Polygon(list(q.exterior.coords),facecolor='#dbc37a' if p['ref'] in ['C35','U15'] else '#768f9d',edgecolor='none',zorder=4))
 for (k,i),p in raw.items():
  if k=='VIA' and 72<p['centerX']*.0254<91 and 36<p['centerY']*.0254<53:
   ax.add_patch(Circle((p['centerX']*.0254,p['centerY']*.0254),p['viaDiameter']*.0254/2,edgecolor='#70dba5' if p['netName']=='GND' else '#839ba8',facecolor='#101f29',linewidth=.8,zorder=5))
 ps=[p for p in capture['pads'] if p['ref']=='C35'];x=sum(p['x'] for p in ps)*.0254/2;y=sum(p['y'] for p in ps)*.0254/2
 ax.annotate('C35',xy=(x,y),xytext=(x-1.5,y+2.0),color='white',fontsize=11,arrowprops={'arrowstyle':'->','color':'white'},zorder=8)
 ax.text(83,43.1,'U15\nSN74LVC244A',ha='center',color='white',fontsize=10)
 ax.annotate('20: VCC',xy=(80.073,45.872),xytext=(80.2,49.7),color='#ffcf69',fontsize=9,arrowprops={'arrowstyle':'->','color':'#ffcf69'},zorder=8)
 ax.set_xlim(72,91);ax.set_ylim(36,53);ax.set_aspect('equal');ax.set_title(title,color='white',fontsize=10);ax.tick_params(colors='#b3c4cc',labelsize=8);ax.set_xlabel('mm',color='#b3c4cc');ax.set_ylabel('mm',color='#b3c4cc')
fig.suptitle('ACTUAL NATIVE COPPER | same 230 parts / same rules | only C35 moved\nR7 reopened full DRC: 0 clearance / 0 physics / 62 connection objects | power transient and fabrication NOT qualified',color='white',fontsize=11)
fig.tight_layout(rect=[0,0,1,.91]);fig.savefig(BASE/'C35-native-before-after.png',dpi=170);plt.close(fig);print('Actual layout comparison rendered',flush=True)
