"""Validate two complete signal repairs and short original-width supply repairs."""
from pathlib import Path
import json,math,re
from exchange import read,OUT,sha
from ses import parse
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
cp,pcb,s=read()
signals={'VIS_CS_N','VIS_BL_EN'}
route=parse((OUT/'result.ses').read_text(),signals)
power=[]
for ref,pin,targetid in [('U15','17','7881ab55cd79fb3a'),('R30','1','723148871d7c2e07')]:
    p=next(p for p in s['pads'] if p['ref']==ref and p['n']==pin)
    target=next(p for p in s['lines'] if p['id']==targetid)
    q=LineString([(target['x1'],target['y1']),(target['x2'],target['y2'])]);end=q.interpolate(q.project(Point(p['x'],p['y'])))
    power.append(dict(net='3V3_IO',layer=1,x1=p['x'],y1=p['y'],x2=end.x,y2=end.y,width=target['width'],restored_pad=ref+'.'+pin))
route['lines']+=power
work={**s,'lines':s['lines']+route['lines'],'vias':s['vias']+route['vias']}
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
checks={};fail=[];nets=[]
for net in sorted(signals|{'3V3_IO'}):
    f,pads=copper(work,net);foreign={l:unary_union(q) for l,q in f.items()};allforeign=unary_union(list(foreign.values()));allpads=unary_union(pads)
    ls=[p for p in route['lines'] if p['net']==net];vs=[p for p in route['vias'] if p['net']==net]
    def check(kind,gap,minimum):
        checks[kind]=min(checks.get(kind,math.inf),gap)
        if gap<minimum-1e-7:fail.append(dict(net=net,criterion=kind,gap_mm=gap,minimum_mm=minimum))
    for p in ls:
        assert p['layer'] in [1,16] and p['width']>=6
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);radius=p['width']*.0254/2
        check('track_copper',q.distance(foreign[p['layer']])-radius,.158);check('track_mount',q.distance(mount)-radius,.15)
        if p['layer']==16:check('track_quiet',q.distance(quiet)-radius,.158)
    for v in vs:
        q=Point(v['x']*.0254,v['y']*.0254);check('via_copper',q.distance(allforeign)-.3048,.158);check('hole_pad',q.distance(allpads)-.1524,.25);check('via_quiet',q.distance(quiet)-.3048,.158)
        for other in work['vias']:
            if other is v:continue
            check('drill_drill',math.dist((v['x'],v['y']),(other['x'],other['y']))*.0254-(v['hole']+other['hole'])*.0254/2,.35)
    proof=connected([p for p in s['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net])
    before=connected([p for p in s['pads'] if p['net']==net],[p for p in s['lines'] if p['net']==net],[p for p in s['vias'] if p['net']==net])
    if net in signals and not proof['complete']:fail.append(dict(net=net,continuity=proof))
    if net=='3V3_IO':assert proof['pad_islands']<before['pad_islands']
    nets.append(dict(net=net,before=before,after=proof,new_lines=len(ls),new_vias=len(vs),length_mm=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in ls)))
audit=dict(source_pcb_sha256=cp['pcb_sha256'],signals_complete=sorted(signals),partial_power_pad_repairs=['U15.17','R30.1'],nets=nets,minimum_clearances_mm=checks,failures=fail,geometric_pass=not fail,manufacturing_release=False)
(OUT/'batch-validation.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
(OUT/'accepted-batch.json').write_text(json.dumps(route,indent=2),encoding='utf8')
assert sha(pcb)==cp['pcb_sha256']
print(json.dumps(audit,indent=2),flush=True)
