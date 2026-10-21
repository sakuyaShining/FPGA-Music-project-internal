"""Inspect saved native drill geometry independently of the pad-hole API getter."""
import csv
import hashlib
import json
from collections import Counter
from native_review import ROOT,PROJECT

path=PROJECT/'pcb/PCB1.epcb2';raw=path.read_bytes();docs={};current=None
for line in raw.decode('utf-8').splitlines():
    if '||' not in line:continue
    a,b=line.split('||',1);header=json.loads(a);value=b.rstrip('|');body=json.loads(value) if value else None
    if header['type']=='DOCHEAD':
        current=body['uuid'];docs.setdefault(current,{'meta':body,'records':{}})
    if current is None:continue
    ident=(header['type'],header.get('id',''))
    old=docs[current]['records'].get(ident)
    if not old or header.get('ticket',0)>=old[0].get('ticket',0):docs[current]['records'][ident]=(header,body)
board=next(v for v in docs.values() if v['meta']['docType']=='PCB')
inventory=json.loads((ROOT/'pcb-pad-inventory.json').read_text(encoding='utf-8'))
rows=[];getter_differences=[]
for component in inventory:
    footprint=docs[component['footprint']['uuid']]
    pads={v['num']:v for h,v in footprint['records'].values() if h['type']=='PAD' and v}
    for pin in component['pads']:
        p=pads[pin['n']];hole=p.get('hole')
        if not hole or hole['width']<=0 or hole['height']<=0:continue
        width=hole['width']*.0254;height=hole['height']*.0254
        annulus=min(p['defaultPad']['width']-hole['width'],p['defaultPad']['height']-hole['height'])*.0254/2
        rows.append({'ref':component['ref'],'pad':pin['n'],'kind':'PTH' if p['plated'] else 'NPTH',
                     'width_mm':round(width,6),'height_mm':round(height,6),'min_axis_annulus_mm':round(annulus,6)})
        api=pin.get('hole')
        if api and abs(api[1]*.0254-width)>.005:getter_differences.append({'ref':component['ref'],'pad':pin['n'],
                    'native_hole_mm':round(width,6),'api_getter_hole_mm':round(api[1]*.0254,6)})
vias=[]
for h,p in board['records'].values():
    if not p:continue
    if h['type']=='VIA':
        vias.append({'id':h['id'],'drill_mm':p['holeDiameter']*.0254,
                     'annulus_mm':(p['viaDiameter']-p['holeDiameter'])*.0254/2})
    if h['type']=='PAD' and p.get('hole'):
        rows.append({'ref':'BOARD','pad':p['num'],'kind':'PTH' if p['plated'] else 'NPTH',
                     'width_mm':round(p['hole']['width']*.0254,6),'height_mm':round(p['hole']['height']*.0254,6),
                     'min_axis_annulus_mm':None})
report={'source_file':str(path),'source_sha256':hashlib.sha256(raw).hexdigest(),'actual_native_drilled_pads':rows,
        'via_count':len(vias),'min_via_drill_mm':min(v['drill_mm'] for v in vias),
        'min_via_annulus_mm':min(v['annulus_mm'] for v in vias),
        'api_getter_discrepancies':getter_differences,
        'note':'Pad-hole getter differs from saved native geometry; use native source and exported drill for dimensional signoff. Not a complete DFM release.'}
(ROOT/'native-drill-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PLACED PAD DRILLS',Counter((r['kind'],r['width_mm'],r['height_mm']) for r in rows),flush=True)
print('VIAS',len(vias),'minimum drill',report['min_via_drill_mm'],'minimum annulus',report['min_via_annulus_mm'],flush=True)
print('PAD HOLE GETTER DISCREPANCIES',len(getter_differences),flush=True)
