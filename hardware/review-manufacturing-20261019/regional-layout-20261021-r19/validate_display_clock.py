"""Independently assess only fresh DISP_SCK copper against actual unchanged regional layout."""
from pathlib import Path
import json,sys,math,re
from exchange import read,sha,OUT,ROOT
from ses import parse
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from four_layer_geometry import copper,connected
cp,pcb,s=read()
attempt=json.loads((OUT/'attempt.json').read_text(encoding='utf-8'))
assert attempt['state']=='terminal' and attempt['ses_exists'],attempt
result=parse((OUT/'result.ses').read_text(encoding='utf-8'),{'DISP_SCK'})
(OUT/'selected-copper.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
f,pads=copper(s,'DISP_SCK');foreign={l:unary_union(q) for l,q in f.items()};allforeign=unary_union(list(foreign.values()));padunion=unary_union(pads)
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
checks={};fail=[]
for i,p in enumerate(result['lines']):
    if p['layer'] not in [1,16]:fail.append(['forbidden-layer',i,p['layer']]);continue
    q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);radius=p['width']*.0254/2
    for label,gap,limit in [('track-copper',q.distance(foreign[p['layer']])-radius,.158),('track-mount',q.distance(mount)-radius,.15)]+([('track-quiet',q.distance(quiet)-radius,.158)] if p['layer']==16 else []):
        checks[label]=min(checks.get(label,math.inf),gap)
        if gap<limit-1e-7:fail.append([label,i,gap,limit])
    if p['width']<6-1e-7:fail.append(['track-width',i,p['width']])
    x0,y0,x1,y1=q.buffer(radius).bounds
    if min(x0,y0,140-x1,100-y1)<.5:fail.append(['board-margin',i,[x0,y0,x1,y1]])
for i,p in enumerate(result['vias']):
    q=Point(p['x']*.0254,p['y']*.0254);radius=p['diameter']*.0254/2;hole=p['hole']*.0254/2
    for label,gap,limit in [('via-copper',q.distance(allforeign)-radius,.158),('via-pad-hole',q.distance(padunion)-hole,.25),('via-quiet',q.distance(quiet)-radius,.158),('via-mount',q.distance(mount)-radius,.15)]:
        checks[label]=min(checks.get(label,math.inf),gap)
        if gap<limit-1e-7:fail.append([label,i,gap,limit])
    for other in s['vias']+result['vias'][:i]:
        gap=math.dist((p['x'],p['y']),(other['x'],other['y']))*.0254-(p['hole']+other['hole'])*.0254/2
        checks['drill-drill']=min(checks.get('drill-drill',math.inf),gap)
        if gap<.35-1e-7:fail.append(['drill-drill',i,gap,.35])
continuity=connected([p for p in s['pads'] if p['net']=='DISP_SCK'],result['lines'],result['vias'])
length=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in result['lines'])
quality=dict(maximum_new_via_goal=2,maximum_summed_length_goal_mm=100,within_goal=len(result['vias'])<=2 and length<=100,
             note='Engineering screening goals, not manufacturer design rules or SI signoff.')
report=dict(source_pcb_sha256=cp['pcb_sha256'],input_dsn_sha256=sha(OUT/'input.dsn'),result_ses_sha256=sha(OUT/'result.ses'),
            net='DISP_SCK',lines=len(result['lines']),new_vias=len(result['vias']),summed_length_mm=length,continuity=continuity,
            minimum_clearances_mm=checks,geometric_failures=fail,geometric_pass=not fail and continuity['complete'],quality=quality,
            native_imported=False,manufacturing_release=False,
            limitations=['No actual ground-pour rebuild, current-edge SI model, manufacturing approval or physical measurement.',
                         'Only selected DISP_SCK copper would be eligible for import; ignore all placement/unselected output.',
                         'Router completion/logged violation counts do not establish actual native-board validity.'])
(OUT/'independent-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
assert sha(pcb)==cp['pcb_sha256'];print(json.dumps(report,indent=2),flush=True)
