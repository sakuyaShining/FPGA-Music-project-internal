"""Dimension review of the recorded panel proposal, not a mechanical redesign."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle
from matplotlib.font_manager import FontProperties

OUT=Path(__file__).resolve().parent
FONT=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['svg.fonttype']='path'
BG='#f7f8fa';INK='#20394b';TEAL='#32766f';ORANGE='#a45823'
fig=plt.figure(figsize=(16,10),facecolor=BG)
ax=fig.add_axes([.055,.25,.9,.61],facecolor=BG)
ax.set_xlim(-24,480);ax.set_ylim(242,-17);ax.set_aspect('equal');ax.axis('off')
def text(x,y,t,size=10,color=INK,ha='center',va='center'):
    ax.text(x,y,t,fontproperties=FONT,fontsize=size,color=color,ha=ha,va=va)
def box(x,y,w,h,fill,edge=INK,lw=1):
    ax.add_patch(Rectangle((x,y),w,h,facecolor=fill,edgecolor=edge,lw=lw))
def dim(a,b,label,vertical=False):
    ax.annotate('',xy=a,xytext=b,arrowprops={'arrowstyle':'|-|','color':INK,'lw':1.3})
    if vertical:
        ax.text(a[0]-5,(a[1]+b[1])/2,label,rotation=90,fontproperties=FONT,fontsize=12,ha='center',va='center',color=INK)
    else:text((a[0]+b[0])/2,a[1]+7,label,12)

box(0,0,470,220,'#e8ebed')
dim((0,230),(470,230),'470 mm（整机宽度提案）')
dim((-12,0),(-12,220),'220 mm（整机深度提案）',True)
box(15,10,84,57,'#b9cbd2')
box(22,16,64,45,'#183440')
text(54,32,'独立可视化屏',11,'white')
text(54,46,'小屏外形 / 开孔待核',8,'white')
for i in range(4):
    box(111+i*26,17,21,22,'#f5e6ad');text(121.5+i*26,28,str(i+1),13)
box(218,17,26,22,'#efd4c6');text(231,28,'编辑',11)
ax.add_patch(Circle((272,28),11,facecolor='#dfba9c',edgecolor=ORANGE))
text(272,48,'按压旋钮',9)
text(365,27,'AUX / 电源 / USB / TF',11)
text(365,42,'背缘接口与下层板卡留位',9)
box(111,52,138,11,'#c89772',edge='#a47c62')
text(180,57.5,'八度选择条：只选档，不测力',9)
box(15,70,234,121,'#f2faf8',edge='#99ada8')
for row in range(2):
    for col in range(13):
        box(18+col*18,76+row*60,12,48,'#78a9a0' if col%2 else '#416e69',edge='#e4f0ed',lw=.3)
text(132,199,'两排逐音滑条：每排 13 格仅为空间示意',10)
text(132,211,'单条 12×48 mm、中心距 18 mm 均为实验初值',9)
box(267,76,185,108,'#b9cbd2',edge='#7d969e')
box(282.5,87,154,86,'#15313d')
for col in range(8):
    x=286+col*18.25
    box(x,98,14.5,61,'#20434e',edge='#62848a',lw=.5)
    h=[19,36,46,30,55,42,25,37][col]
    box(x,159-h,14.5,h,'#70b8a6',edge='#70b8a6',lw=.3)
text(359.5,81,'7 英寸触摸推子屏',11)
text(359.5,191,'预留包络 185×108 mm；有效区约 154×86 mm',9)
text(359.5,202,'包络沿用旧提案，不是最终屏幕开孔尺寸',9,ORANGE)

fig.text(.055,.95,'整机尺寸核对草案 · 2026-10-21',fontproperties=FONT,fontsize=23,color=INK)
fig.text(.055,.91,'沿用 2026-10-15 的 470×220 mm 空间提案，更新说明；未形成最终机械施工图',fontproperties=FONT,fontsize=12,color=ORANGE)
fig.text(.065,.19,'当前电气载板：暂定 140×100 mm，另层安装；本图没有替它指定安装位置。',fontproperties=FONT,fontsize=12,color=INK)
fig.text(.065,.145,'未冻结：整机厚度、屏幕玻璃与支架、开孔、支撑柱、按钮/旋钮配准、线束弯曲和插拔空间。',fontproperties=FONT,fontsize=11,color=INK)
fig.text(.065,.10,'小屏为待购候选；13 格/排和右屏 8 组仅示意，不冻结音高映射、分组或电极几何。',fontproperties=FONT,fontsize=11,color=INK)
fig.text(.065,.055,'未注尺寸的位置仅示意。不可据此切面板、打孔、制作电极或下单生产；图中尺寸单位均为 mm。',fontproperties=FONT,fontsize=11,color=ORANGE)
fig.savefig(OUT/'panel-dimensions-review.png',dpi=150,facecolor=BG)
fig.savefig(OUT/'panel-dimensions-review.svg',facecolor=BG)
plt.close(fig)
legacy=Path('C:/Users/Sakuya/FPGA-Music-project/hardware/seven-inch-selection-20261015/layout.png')
doc=Path('C:/Users/Sakuya/FPGA-Music-project/docs/02-技术方案/62-七英寸右手触屏选型与整机布局评估-2026-10-15.md')
pcb=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(legacy)=='400713e410b64195df21054c1e4fcdd2dd6b4077374399aa895ca29498c2ab5e'
assert h(pcb)=='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e'
provenance={'date':'2026-10-21','role':'Re-present recorded panel space proposal with current status labels; no hardware edits',
 'source_files':{str(legacy):h(legacy),str(doc):h(doc)},'current_pcb_sha256':h(pcb),
 'panel_mm':[470,220],'panel_dimension_status':'2026-10-15 proposal; not frozen',
 'carrier_mm':[140,100],'carrier_dimension_status':'provisional current PCB outline',
 'screen_envelope_mm':[185,108],'screen_envelope_status':'legacy planning allowance; not selected module dimensions',
 'slider_mm':[12,48],'slider_pitch_mm':18,'slider_status':'experimental initial geometry, not qualified',
 'no_final_cutout_hole_or_height_design':True,'manufacturing_release':False,
 'outputs':{p.name:h(p) for p in [OUT/'panel-dimensions-review.png',OUT/'panel-dimensions-review.svg']}}
(OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
print('Created PNG/SVG dimension review; source and current PCB hashes verified; no manufacturing release.')
