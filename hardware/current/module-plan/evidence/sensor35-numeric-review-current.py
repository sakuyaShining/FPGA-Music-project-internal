from pathlib import Path
import json, sys, hashlib, datetime, math
sys.path.insert(0, r'D:\FPGA-Project\codex-tools\shapely')
from shapely import from_wkb
from shapely.geometry import Point, LineString, Polygon, box
from shapely.affinity import rotate
E=Path(__file__).parent
def read(n): return json.loads((E/n).read_text(encoding='utf-8-sig'))
a=read('sensor-fourlayer-signal-repair-reopened-DRC-current.json')['value']
g=read('sensor-fourlayer-actual-ground-reference-current.json')
pads=read('sensor-fourlayer-exact-source-pads-current.json')['pads']
source=E/'sensor-fourlayer-native-current.epcb2'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
assert sha=='617f550eadc818ffab26a3992f2a86bb9f72ed027043c6e64a0c0428077ba643'
assert g['source_sha256']==sha
planes={k:from_wkb((E/f'sensor-fourlayer-real-ground-layer{k}-current.wkb').read_bytes()) for k in (15,16)}
terms=[]
for p in pads:
 if p['layer']!=12 or p['net']=='GND': continue
 s=p['shape']; w=s['width']*.0254; h=s['height']*.0254
 cu=Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=1024) if s['padType']=='ELLIPSE' else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
 terms.append(dict(id=p['ref']+'.'+p['pin'],net=p['net'],kind='PTH',xy=[p['hole_x_mm'],p['hole_y_mm']],copper=cu,diameter_mm=w,drill_mm=p['hole']['width']*.0254,annular_ring_nominal_mm=(w-p['hole']['width']*.0254)/2))
for v in a['vias']:
 if v['net']=='GND':continue
 pt=Point(v['x']*.0254,v['y']*.0254)
 terms.append(dict(id=v['primitiveId'],net=v['net'],kind='via',xy=[pt.x,pt.y],copper=pt.buffer(v['diameter']*.0254/2,quad_segs=1024),diameter_mm=v['diameter']*.0254,drill_mm=v['holeDiameter']*.0254,annular_ring_nominal_mm=(v['diameter']-v['holeDiameter'])*.0254/2))
groundvias=[v for v in a['vias'] if v['net']=='GND']
details={}
for layer,plane in planes.items():
 voids=[Polygon(r) for r in plane.interiors]
 for t in terms:
  pt=Point(t['xy']); holes=[q for q in voids if q.covers(pt)];assert len(holes)==1
  v=min(groundvias,key=lambda v:pt.distance(Point(v['x']*.0254,v['y']*.0254)))
  distance=pt.distance(Point(v['x']*.0254,v['y']*.0254))
  gap=t['copper'].distance(plane)
  # Also calculate hole-edge to Ground directly, rather than confusing it with copper clearance.
  holegap=pt.distance(plane)-t['drill_mm']/2
  d={k:x for k,x in t.items() if k!='copper'}
  d.update(reference_layer=layer,copper_to_GND_min_mm=gap,hole_to_GND_min_mm=holegap,paired_GND_via=v['primitiveId'],paired_GND_xy_mm=[v['x']*.0254,v['y']*.0254],return_centres_mm=distance,paired_hole_edges_mm=distance-(t['drill_mm']+v['holeDiameter']*.0254)/2)
  details[layer,t['id']]=(d,holes[0])
lines={l['primitiveId']:l for l in a['lines']};rows=[]
for i,f in enumerate(g['failed_reference_lines'],1):
 l=lines[f['id']];layer=f['reference_layer']
 line=LineString([(l['startX']*.0254,l['startY']*.0254),(l['endX']*.0254,l['endY']*.0254)]).buffer(l['lineWidth']*.0254/2,quad_segs=256)
 missing=line.difference(planes[layer]);related=[]
 for t in terms:
  if t['net']!=l['net']:continue
  d,void=details[layer,t['id']]
  if missing.intersection(void).area>1e-8:related.append(d)
 assert related,(i,f)
 rows.append(dict(number=i,line_id=f['id'],net=f['net'],layer=l['layer'],reference_layer=layer,missing_area_mm2=missing.area,terminals=related))
assert len(rows)==35
allterms=[v[0] for v in details.values()]
r=dict(at=datetime.datetime.now().astimezone().isoformat(),source_sha256=sha,units='mm',method='Native actual Ground polygon WKB including actual Ground tracks/pads/vias. Copper circle approximated at 4096 edges; current native Ground polygon resolution retained. Nominal CAD dimensions, not finished-board measurements. No acceptance criterion changed.',rows=rows,all_non_GND_PTH_and_via_terminals=allterms,summary=dict(min_copper_to_GND_mm=min(d['copper_to_GND_min_mm'] for d in allterms),min_inner_via_hole_to_GND_mm=min(d['hole_to_GND_min_mm'] for d in allterms if d['kind']=='via'),min_inner_PTH_hole_to_GND_mm=min(d['hole_to_GND_min_mm'] for d in allterms if d['kind']=='PTH'),min_return_centres_mm=min(d['return_centres_mm'] for d in allterms),max_return_centres_mm=max(d['return_centres_mm'] for d in allterms),min_paired_hole_edges_mm=min(d['paired_hole_edges_mm'] for d in allterms)),manufacturer_source='https://jlcpcb.com/capabilities/Capabilities',manufacturer_checked='2026-10-27',manufacturer_limits_mm=dict(multilayer_1oz_trace_space=.09,via_hole_min=.15,via_hole_preferred=.2,via_hole_to_copper_inner=.2,PTH_hole_to_copper_inner=.3,via_hole_to_hole=.2,pad_hole_to_hole=.45,multilayer_1oz_PTH_ring_absolute=.15,multilayer_1oz_PTH_ring_recommended=.2),acceptance_approved=False,physical_tests='UNMEASURED')
(E/'sensor35-numeric-review-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r['summary']))
for row in rows:
 print(str(row['number'])+' | '+row['net']+' | '+str(row['layer'])+' | '+'; '.join(d['id']+': Cu='+format(d['copper_to_GND_min_mm'],'.6f')+', holeCu='+format(d['hole_to_GND_min_mm'],'.6f')+', return='+format(d['return_centres_mm'],'.6f')+', holeGap='+format(d['paired_hole_edges_mm'],'.6f') for d in row['terminals']))
aliases={'L0_E13':'V_E13','RC_DRIVE':'V_DRIVE','SENSE_OUT':'V_SENSE','ADDR0':'V_A0','ADDR1':'V_A1','ADDR2':'V_A2','ADDR3':'V_A3','MUX_DISABLE':'V_EN'}
def label(d):return d['id'] if d['kind']=='PTH' else aliases[d['net']]
md=['# 35项参考连续性告警：实际间距逐项复核','',
'核对日期：2026-10-27。当前传感小板源 SHA256：`'+sha+'`。没有修改 PCB、旧门限或验收状态；本表是用户作决定前的数值证据。', '',
'这些是35段走线的旧参考连续性检查未通过项，并非35处短路或35个未连接网络。当前保存、关闭本板标签、重开后原生严格DRC为0，未连通为0；按旧参考检查仍不接受。', '',
'## 数值定义', '',
'“避空到铜皮”在这里按有加工意义的距离列出：信号铜环/焊盘外缘到实际GND铜边的最短距离。反焊盘边界本身就是这片地铜的边界，不另报一个虚构的边到边距离。另列钻孔边缘到GND铜，以及信号孔与最近配对地过孔的中心距、孔边距。', '',
'单位全部为mm。保留6位小数用于复核，不代表板厂具有微米级成品精度；这是CAD标称几何值，非实物测量。斜杠分隔的数据依次对应同一行的两个端点。Top参考Inner1，Bottom参考Inner2。每个信号孔都按实际独立地铜边界测量，没有用名义0.254mm替代。', '',
'## 逐项数据', '',
'|序号|网络|走线层|涉及孔|铜边→GND最小|孔边→GND最小|配对地孔中心距|配对孔边距|',
'|---:|---|---|---|---:|---:|---:|---:|']
for row in rows:
 ts=row['terminals']; vals=lambda k:' / '.join(f'{d[k]:.6f}' for d in ts)
 md.append('|'+str(row['number'])+'|'+row['net']+'|'+('Top' if row['layer']==1 else 'Bottom')+'|'+' / '.join(label(d) for d in ts)+'|'+vals('copper_to_GND_min_mm')+'|'+vals('hole_to_GND_min_mm')+'|'+vals('return_centres_mm')+'|'+vals('paired_hole_edges_mm')+'|')
md += ['', '完整走线对象ID、信号孔和配对地孔对象ID、坐标、未参考面积、逐层结果见同目录 [sensor35-numeric-review-current.json](sensor35-numeric-review-current.json)。', '', '## 孔尺寸及配对地孔身份', '',
'|信号孔|对象ID/焊盘号|孔中心x,y|钻孔直径|铜外径/最小宽度|标称单边铜环|配对地过孔ID|',
'|---|---|---|---:|---:|---:|---|']
seen=set()
for row in rows:
 for d in row['terminals']:
  if d['id'] in seen:continue
  seen.add(d['id']);md.append('|'+label(d)+'|'+d['id']+'|'+','.join(f'{x:.6f}' for x in d['xy'])+f"|{d['drill_mm']:.6f}|{d['diameter_mm']:.6f}|{d['annular_ring_nominal_mm']:.6f}|"+d['paired_GND_via']+'|')
md += ['', '配对地过孔均为钻孔0.360680mm、外径0.711200mm、单边铜环0.175260mm。排针焊盘钻孔1.020013mm、外径/方形边长1.599997mm，标称最小铜环0.289992mm（实际孔中心的小偏移见JSON）。', '',
'## 嘉立创公开能力对照', '',
'来源：[JLCPCB嘉立创国际官网加工能力](https://jlcpcb.com/capabilities/Capabilities)，2026-10-27读取，按普通多层FR-4、1oz条件比较；不将2oz或特殊工艺混入。', '',
'|项目|本次实际最小/配置|官网能力|判断|',
'|---|---:|---:|---|',
'|异网铜间距（这些孔的铜边到地铜）|0.213002|多层1oz线距0.09|有余量|',
'|内层过孔孔边到异网铜|0.464061|0.20|有余量|',
'|内层排针PTH孔边到异网铜|0.502917|0.30|有余量|',
'|配对信号/地孔的孔边距|0.639321|过孔0.20；焊盘孔0.45|高于两项|',
'|过孔钻孔/外径|0.360680 / 0.711200|最小0.15 / 0.25；优选孔0.20|常规机械通孔尺寸|',
'|排针PTH单边铜环|0.289992|多层1oz推荐0.20；极限0.15|高于推荐|',
'|过孔单边铜环|0.175260|官网过孔直径比孔径优选大0.15，即单边0.075|满足过孔规则；若套用PTH推荐0.20则未达到推荐值，不能把它写成0.20|', '',
'结论：这35项涉及的上述孔、间距在官网公开常规加工范围内，不需要HDI、盲埋孔或激光微孔。这里只确认这些尺寸的加工可行性；不等于整板Gerber已通过工厂DFM、PCBA报价已确认或传感性能已实测。', '',
'## 回流及验收状态', '',
'最近配对地孔中心距为1.000001mm，最远1.451260mm；没有改动原≤1.5mm要求。实际地铜连通、最小铜颈及配对地孔接铜另有审计。板厂的孔距能力不是信号回流质量标准，中心距达标不能替代串扰、校准稳定性和整机最坏延迟测试。', '',
'全部剩余参考缺口只位于本网孔的实际绝缘避空内，避空外没有剩余缺口。是否按这些真实边界单独验收，仍等待用户看完数值后的明确决定；没有自动视为同意，也没有授权投板或下单。整机和本板实物状态：UNMEASURED。']
(E/'sensor35-numeric-review-current.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
