"""Plan additive ground links from reported islands to native-connected anchors.

Native DRC provides representatives of disconnected islands, rather than all
their members. Unreported anchors are only candidates; an optional plane-based
anchor list narrows them. Every proposal requires a new native DRC.
"""
import hashlib
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, 'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad, connected_subset
from native_review import ROOT, PROJECT
from resume_offline import read_native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',default='resume-ground-source.json')
parser.add_argument('--drc',default='drc-stage-resume-audio-reopened.json')
parser.add_argument('--output',default='resume-ground-additive-plan.json')
parser.add_argument('--anchors')
options=parser.parse_args()
source_path = ROOT/options.source
source = json.loads(source_path.read_text(encoding='utf-8'))
native_path = PROJECT/'pcb/PCB1.epcb2'
pcb_sha = hashlib.sha256(native_path.read_bytes()).hexdigest()
# Include short segments omitted by the native getAll API in collision checks.
ids = {p['id'] for p in source['lines']}
extra = []
for (kind, identity), p in read_native(native_path).items():
    if kind == 'LINE' and p.get('layerId') in [1,2] and identity not in ids:
        extra.append({'id':identity, 'net':p['netName'], 'layer':p['layerId'],
                      'x1':p['startX'], 'y1':p['startY'], 'x2':p['endX'],
                      'y2':p['endY'], 'width':p['width']})
working = {**source, 'lines':source['lines'] + extra, 'vias':list(source['vias'])}
drc = json.loads((ROOT/options.drc).read_text(encoding='utf-8'))
errors = next(n['list'] for c in drc if c['name']=='Connection Error' for n in c['list'] if n['name']=='GND')
bad = {e['objs'][0] for e in errors}

def via_anchor(v):
    return {'id':v['id'], 'ref':'VIA', 'n':v['id'], 'net':'GND', 'layer':12,
            'x':v['x'], 'y':v['y'], 'rotation':0,
            'shape':['ELLIPSE',v['diameter'],v['diameter']]}

targets = [p for p in source['pads'] if p['id'] in bad]
targets += [via_anchor(v) for v in source['vias'] if v['id'] in bad]
anchors = [p for p in source['pads'] if p['net']=='GND' and p['layer']==12 and p['id'] not in bad]
anchors += [via_anchor(v) for v in source['vias'] if v['net']=='GND' and v['id'] not in bad]
if options.anchors:
    allowed={a['id'] for a in json.loads((ROOT/options.anchors).read_text())['anchors']}
    anchors=[a for a in anchors if a['id'] in allowed]
assert len(targets)==len(errors) and anchors
grid.pad_shape = actual_pad
grid.GRID = .05
grid.WIDTH = .2032
grid.GAP = .17
original_raster = grid.raster
grid.raster = lambda geoms,bounds,inflate,shape: original_raster(geoms,bounds,inflate+grid.GRID/math.sqrt(2),shape)
routes, failed = [], []
output = ROOT/options.output

def save():
    data={'net':'GND', 'additive':True, 'source_file':str(source_path),
          'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
          'native_pcb_sha256':pcb_sha, 'native_short_line_obstacles':len(extra),
          'routes':routes, 'failed_planning':failed,
          'lines':[p for r in routes for p in r['lines']],
          'vias':[p for r in routes for p in r['vias']],
          'native_imported':False, 'requires_native_drc':True, 'manufacturing_release':False}
    output.write_text(json.dumps(data,indent=2),encoding='utf-8')

for target in sorted(targets,key=lambda p:(p['ref'],p['n'])):
    nearest=sorted(anchors,key=lambda a:math.hypot(a['x']-target['x'],a['y']-target['y']))[:3]
    route=None
    for anchor in nearest:
        for margin in [4,10]:
            try: route=grid.search(working,'GND',target,anchor,margin)
            except grid.SealedEscape: route=None;break
            if route:break
        if route:break
    if not route:
        failed.append({'id':target['id'],'ref':target['ref'],'pad':target['n']});save();continue
    # Independent geometry and hole checks against the complete physical source.
    foreign,pads,keepouts=grid.geometries(working,'GND')
    unions={layer:unary_union(foreign[layer]) for layer in [1,2]}
    both,ko=unary_union(foreign[1]+foreign[2]),unary_union(keepouts)
    violations=[]
    for line in route['lines']:
        center=LineString([(line['x1']*grid.MM,line['y1']*grid.MM),(line['x2']*grid.MM,line['y2']*grid.MM)])
        if center.distance(unions[line['layer']])-line['width']*grid.MM/2<.158:violations.append('line_clearance')
        if center.distance(ko)<line['width']*grid.MM/2+.15:violations.append('mount_keepout')
    for i,via in enumerate(route['vias']):
        center=Point(via['x']*grid.MM,via['y']*grid.MM)
        if center.distance(both)-via['diameter']*grid.MM/2<.158:violations.append('via_clearance')
        for previous in working['vias']+route['vias'][:i]:
            distance=math.hypot(via['x']-previous['x'],via['y']-previous['y'])*grid.MM
            if distance-(via['hole']+previous['hole'])*grid.MM/2<.3499:violations.append('drill_spacing')
    connection=connected_subset([target,anchor],route['lines'],route['vias'])
    assert connection['complete'], 'Real endpoint continuity failed'
    if violations:
        failed.append({'id':target['id'],'ref':target['ref'],'pad':target['n'],'violations':violations});save();continue
    route.update({'target':target,'anchor':anchor,'independent_geometry_pass':True})
    routes.append(route)
    working['lines']+=route['lines'];working['vias']+=route['vias']
    # A connected target becomes an additional valid anchor, reducing later
    # parallel paths without moving existing copper or assuming pour continuity.
    if target['layer']==12 and not options.anchors:anchors.append(target)
    print('GROUND LINK',target['ref'],target['n'],'to',anchor['ref'],len(route['lines']),len(route['vias']),flush=True)
    save()
assert hashlib.sha256(native_path.read_bytes()).hexdigest()==pcb_sha
print('GROUND PLAN',len(routes),'links;',len(failed),'pending',flush=True)
