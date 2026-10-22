"""Fresh read-only R7 geometry exchange; not a native manufacturing export."""
from pathlib import Path
import sys,json,hashlib,math,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString,Polygon,box
from shapely.affinity import translate,scale
sys.path.insert(0,str(ROOT))
from physical_geometry import actual_pad
from resume_offline import read_native
LAYERS={1:'TopLayer',15:'Inner15',16:'Inner16',2:'BottomLayer'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def atom(s):return json.dumps(str(s))
def num(v):return f'{v:.6f}'
def polygon(layer,q):
    assert q.geom_type=='Polygon' and not q.interiors
    return '(polygon '+layer+' 0 '+' '.join(num(v) for xy in list(q.exterior.coords)[:-1] for v in xy)+')'
def read_original_active():
    cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
    pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==cp['pcb_sha256']
    s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));raw=read_native(pcb)
    s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in LAYERS]
    s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
    return cp,pcb,s
def read():
    cp=json.loads((OUT/'source-meta.json').read_text(encoding='utf8'))
    pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==cp['pcb_sha256']
    s=json.loads((OUT/'source-capture.json').read_text(encoding='utf8'));raw=read_native(pcb)
    s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in LAYERS]
    s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
    return cp,pcb,s

def build():
    cp,pcb,s=read();selected=set(json.loads((OUT/'regional-edit-plan.json').read_text(encoding='utf8'))['routing_nets'])
    pads=s['pads'];stacks={};pinlines=[];pins={};max_pad_error=0.
    for i,p in enumerate(pads):
        shape=actual_pad(p)
        local=scale(translate(shape,xoff=-p['x']*.0254,yoff=-p['y']*.0254),xfact=1/.0254,yfact=1/.0254,origin=(0,0))
        coordinates=[(round(x,6),round(y,6)) for x,y in list(local.exterior.coords)[:-1]]
        reconstructed=translate(scale(Polygon(coordinates),xfact=.0254,yfact=.0254,origin=(0,0)),xoff=p['x']*.0254,yoff=p['y']*.0254)
        error=shape.hausdorff_distance(reconstructed);max_pad_error=max(max_pad_error,error);assert error<.000001
        layers=list(LAYERS) if p['layer']==12 else [p['layer']]
        key=(tuple(layers),tuple(coordinates))
        if key not in stacks:
            name='PAD'+str(len(stacks));shapes=' '.join('(shape '+polygon(LAYERS[l],Polygon(coordinates))+')' for l in layers)
            stacks[key]=(name,'(padstack '+name+' '+shapes+' (attach off))')
        name=stacks[key][0];pin='P'+str(i);pinlines.append(f'(pin {name} {pin} {num(p["x"])} {num(p["y"])})')
        if p['net']:pins.setdefault(p['net'],[]).append('u1-'+pin)
    allnets=sorted({p['net'] for key in ['pads','lines','vias'] for p in s[key] if p['net']})
    viastacks={}
    for v in s['vias']+[dict(diameter=24,hole=12)]:
        key=(v['diameter'],v['hole']);name='V'+str(len(viastacks)) if key not in viastacks else viastacks[key][0]
        viastacks[key]=(name,'(padstack '+name+' '+' '.join('(shape (circle '+l+' '+num(v['diameter'])+'))' for l in LAYERS.values())+' (attach off))')
    routevia=viastacks[(24,12)][0]
    structure=[f'(layer {l} (type signal) (property (index {i})))' for i,l in enumerate(LAYERS.values())]
    structure+=['(boundary (rect pcb 0 0 '+num(140/.0254)+' '+num(100/.0254)+'))','(via '+routevia+')','(rule (width 6) (clearance 6))']
    guard_count=0
    for p in s['lines']:
        if p['layer']!=2 or not (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net'])):continue
        extra=.6 if p['net'].startswith('I2S_') else .5
        q=LineString([(p['x1'],p['y1']),(p['x2'],p['y2'])]).buffer(p['width']/2+extra/.0254,quad_segs=16)
        structure.append('(keepout '+atom('quiet'+str(guard_count))+' '+polygon('Inner16',q)+')');guard_count+=1
    for i,p in enumerate(pads):
        if p['net'] in selected:
            q=scale(actual_pad(p),xfact=1/.0254,yfact=1/.0254,origin=(0,0))
            structure.append('(via_keepout '+atom('pad-hole-'+str(i))+' '+polygon('TopLayer',q)+')')
    for i,(x,y) in enumerate([(3,18),(137,16.5),(3,82),(137,88)]):
        for layer in LAYERS.values():structure.append('(keepout '+atom('mount'+str(i)+layer)+' '+polygon(layer,box((x-1.75)/.0254,(y-1.75)/.0254,(x+1.75)/.0254,(y+1.75)/.0254))+')')
    network=[]
    for n in allnets:
        network.append('(net '+atom(n)+' (pins '+' '.join(pins.get(n,[]))+'))')
        network.append('(class '+atom(n)+' '+atom(n)+' (circuit (use_via '+routevia+')) (rule (width '+('15.74' if n in ['3V3_IO','3V3_PERIPH'] else '6')+') (clearance '+('6.5' if n in selected else '6')+')))')
    wiring=[]
    for p in s['lines']:wiring.append('(wire (path '+LAYERS[p['layer']]+' '+num(p['width'])+' '+' '.join(num(p[k]) for k in ['x1','y1','x2','y2'])+') (net '+atom(p['net'])+') (type protect))')
    for p in s['vias']:wiring.append('(via '+viastacks[(p['diameter'],p['hole'])][0]+' '+num(p['x'])+' '+num(p['y'])+' (net '+atom(p['net'])+') (type protect))')
    text='(pcb "Regional-signal-only-second-pass" (parser (string_quote ") (space_in_quoted_tokens on)) (resolution mil 1000) (unit mil)\n'
    text+='(structure '+'\n'.join(structure)+')\n(placement (component BOARD (place u1 0 0 front 0)))\n'
    text+='(library (image BOARD '+' '.join(pinlines)+')\n'+'\n'.join(v[1] for v in stacks.values())+'\n'+'\n'.join(v[1] for v in viastacks.values())+')\n'
    text+='(network '+'\n'.join(network)+')\n(wiring '+'\n'.join(wiring)+')\n)\n'
    (OUT/'input.dsn').write_text(text,encoding='utf-8')
    report=dict(source_pcb_sha256=cp['pcb_sha256'],offline_derived_exchange=True,native_export=False,native_mutated=False,manufacturing_release=False,
                pads=len(pads),padstack_count=len(stacks),fixed_lines=len(s['lines']),fixed_vias=len(s['vias']),quiet_segment_keepouts=guard_count,
                max_pad_roundtrip_hausdorff_mm=max_pad_error,routable_layers=[1,16],allnets=allnets,selected=sorted(selected),dsn_sha256=sha(OUT/'input.dsn'),
                limitations=['Per-segment convex keepouts preserve holes between segments; no flattened union interiors.',
                             'Actual ground pours are excluded and need native rebuild; old fixed copper may intersect newly protected quiet projections.',
                             'No placement import; independently validate all new SES copper before native changes.'])
    (OUT/'exchange-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');assert sha(pcb)==cp['pcb_sha256']
    print(json.dumps({k:v for k,v in report.items() if k not in ['allnets','limitations']},indent=2),flush=True)
if __name__=='__main__':build()
