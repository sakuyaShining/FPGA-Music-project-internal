"""Build an explicitly unreleased passive electrode coupon and compact layout studies.

Requires shapely >=2. Source template is read-only; no board manufacturing export
or native DRC result is synthesized by this script.
"""
from pathlib import Path
import argparse, collections, copy, csv, hashlib, json, math
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent

def load_docs(p):
    out=[]
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip(): continue
        a,b=line.split('||',1); h=json.loads(a); b=b[:-1] if b.endswith('|') else b
        if not b.strip(): continue
        v=json.loads(b)
        if h['type']=='DOCHEAD': out.append({'head':v,'records':[]})
        out[-1]['records'].append((h,v))
    return out

def write_json(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def write_docs(p,docs):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(''.join(json.dumps(h,ensure_ascii=False,separators=(',',':'))+'||'+json.dumps(v,ensure_ascii=False,separators=(',',':'))+'|\n' for d in docs for h,v in d['records']),encoding='utf-8')

def path(g):
    points=list(g.exterior.coords)
    return [points[0][0]/.0254,points[0][1]/.0254,'L']+[n/.0254 for pt in points[1:] for n in pt]

def electrodes(length=48,width=12,gap=.8):
    # Repeating tapered boundaries spread overlap in the longitudinal direction.
    # This is a candidate, not a field/capacitance or RC timing simulation.
    span=(length-8)/2
    xs=[i*width/4 for i in range(5)]
    wave=[4+(span if i%2 else 0) for i in range(5)]
    f=list(zip(xs,wave)); upper=[(x,y+span) for x,y in f]
    raw=[Polygon([(0,0),(width,0)]+list(reversed(f))),
         Polygon(f+list(reversed(upper))),
         Polygon(upper+[(width,length),(0,length)])]
    out=[]
    for poly in raw:
        g=poly.buffer(-gap/2,join_style='round').buffer(-1,join_style='round').buffer(1,quad_segs=16,join_style='round')
        assert g.geom_type=='Polygon' and g.is_valid and not g.is_empty
        from shapely.affinity import translate
        out.append(translate(g,17,17))
    return dict(zip(['A','M','B'],out))

def build(args):
    intent=json.loads((ROOT/'design-intent.json').read_text(encoding='utf-8'))
    source=args.sensor_project/'pcb/PCB2.epcb2'
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='2184d027643f52ff50a7bca4bf9c717ae805a099043d300855f3348be5b5b7e3', 'Unexpected frozen sensor template'
    docs=load_docs(source); original=next(d for d in docs if d['head']['docType']=='PCB')
    attributes=collections.defaultdict(dict)
    for h,v in original['records']:
        if h['type']=='ATTR': attributes[v['parentId']][v['key']]=v['value']
    cid=next(k for k,v in attributes.items() if v.get('Designator')=='J1')
    a=attributes[cid];foot=next(d for d in docs if d['head']['uuid']==a['Footprint'])
    device=next(d for d in docs if d['head']['uuid']==a['Device'])
    meta=next(v for h,v in device['records'] if h['type']=='META')
    symbol=next(d for d in docs if d['head']['uuid']==meta['attributes']['Symbol'])
    libs=copy.deepcopy([symbol,foot,device])
    out=ROOT/'generated'; out.mkdir(exist_ok=True)
    native=out/'ElectrodeCoupon-CANDIDATE'; name=native.name
    board_id='ec29000000000001'; pcb_id='ec29000000000002'
    records=[]; ticket=0
    def add(t,i,v):
        nonlocal ticket
        ticket+=1;records.append(({'type':t,'id':i,'ticket':ticket},v))
    head=copy.deepcopy(original['head']);head['uuid']=pcb_id
    add('DOCHEAD',None,head)
    add('META','META',{'title':'ElectrodeCoupon','board':board_id,'source':'','parent':'','zIndex':None})
    keep={'PRIMITIVE','CANVAS','LAYER','LAYER_PHYS','ACTIVE_LAYER','RULE_TEMPLATE','RULE','SILK_OPTS','D3_ATTRIBUTE','PREFERENCE'}
    for h,v in original['records']:
        if h['type'] not in keep: continue
        v=copy.deepcopy(v)
        if h['type']=='LAYER':
            lid=json.loads(h['id'])[1]
            if lid in [15,16,362,363]: v.update(use=False,show=False)
        if h['type']=='LAYER_PHYS':
            lid=json.loads(h['id'])[1]
            if lid in [15,16,362,363]: continue
            if lid==361: v.update(material='FR-4 nominal; factory stack-up pending',thickness=(1.6-.07)/.0254,permittivity=4.4,zIndex=1001)
        if h['type']=='CANVAS': v.update(unit='mm',originX=0,originY=0,gridXSize=10,gridYSize=10)
        add(h['type'],h.get('id'),v)
    nets=['A','M','B','GND','']
    for net in nets:
        add('NET',json.dumps(['NET',net],separators=(',',':')),{'netType':None,'specialColor':None,'retLine':True,'differentialName':None,'isPositiveNet':False,'equalLengthGroupName':None})
    comp=copy.deepcopy(next(v for h,v in original['records'] if h['type']=='COMPONENT' and h['id']==cid))
    comp.update(x=21/.0254,y=5/.0254,angle=180,attrs={'Unique ID':'ElectrodeCouponJ1'},pinSwapInfo={})
    compid='ec29000000000003'; add('COMPONENT',compid,comp)
    for i,(key,value) in enumerate([('Designator','J1'),('Footprint',a['Footprint']),('Device',a['Device'])]):
        template=copy.deepcopy(next(v for h,v in original['records'] if h['type']=='ATTR' and v['parentId']==cid and v['key']==key))
        template.update(parentId=compid,value=value)
        if key=='Designator':template.update(x=2/.0254,y=10/.0254,angle=0)
        add('ATTR','attr'+str(i),template)
    padmap={}; pads={}
    for h,p in foot['records']:
        if h['type']!='PAD': continue
        net={8:'A',7:'M',6:'B',15:'GND',16:'GND'}.get(int(p['num']),'')
        add('PAD_NET',json.dumps(['PAD_NET',compid,p['num'],h['id']],separators=(',',':')),{'partitionId':'','padNet':net,'padLen':None,'propagationDelay':None,'attrsMap':{}})
        xy=(21-p['centerX']*.0254,5-p['centerY']*.0254)
        pads[int(p['num'])]=(xy,p)
        if net: padmap[int(p['num'])]=net
    pstyle={'partitionId':'','groupId':0,'locked':False,'zIndex':-1}
    def line(i,net,layer,x1,y1,x2,y2,w=.3):
        add('LINE',i,{**pstyle,'netName':net,'layerId':layer,'startX':x1/.0254,'startY':y1/.0254,'endX':x2/.0254,'endY':y2/.0254,'width':w/.0254})
    add('POLY','outline',{**pstyle,'netName':'','layerId':11,'width':4,'path':[0,0,'L',46/.0254,0,46/.0254,72/.0254,0,72/.0254,0,0],'polyType':'NORMAL'})
    for i,(text,x,y) in enumerate([('A',13,20),('M',13,41),('B',13,63),('1',40,8),('COUPON',2,69)]):
        add('STRING','text'+str(i),{**pstyle,'layerId':3,'x':x/.0254,'y':y/.0254,'text':text,'fontFamily':'default','fontSize':45,'strokeWidth':6,'bold':0,'italic':0,'origin':'LEFT_BOTTOM','angle':0,'reverse':False,'expansion':0,'mirror':False,'specialColor':'#000000'})
    geoms=electrodes(); vias={}; traces={}; obs=[]
    for k,g in geoms.items():
        add('FILL','electrode'+k,{**pstyle,'netName':k,'layerId':1,'width':0,'fillStyle':'SOLID','path':path(g),'isBridgingCopper':False,'networkList':[],'refs':[]})
        pin={'A':8,'M':7,'B':6}[k]; x=pads[pin][0][0]
        section=g.buffer(-.65).intersection(LineString([(x,0),(x,72)]))
        pieces=list(section.geoms) if hasattr(section,'geoms') else [section]
        segment=max(pieces,key=lambda z:z.length); pt=segment.interpolate(.5,normalized=True); y=pt.y
        assert g.covers(Point(x,y).buffer(.5,quad_segs=32))
        vias[k]=[x,y]
        add('VIA','via'+k,{**pstyle,'netName':k,'ruleName':'','centerX':x/.0254,'centerY':y/.0254,'holeDiameter':.4/.0254,'viaDiameter':1/.0254,'viaType':'NORMAL','topSolderExpansion':None,'bottomSolderExpansion':None,'unusedInnerLayers':[],'propagationDelay':0})
        line('trace'+k,k,2,x,5,x,y)
        traces[k]=LineString([(x,5),(x,y)]).buffer(.15,quad_segs=32)
        obs.extend([(k,1,g),(k,1,Point(x,y).buffer(.5,quad_segs=64)),(k,2,Point(x,y).buffer(.5,quad_segs=64)),(k,2,traces[k])])
    p15,p16=pads[15][0],pads[16][0]
    line('ground_header','GND',2,*p15,*p16)
    obs.append(('GND',2,LineString([p15,p16]).buffer(.15)))
    for pin,(xy,p) in pads.items():
        net=padmap.get(pin,'NC'+str(pin))
        shape=p['defaultPad'];r=shape['width']*.0254/2
        g=Point(*xy).buffer(r,quad_segs=128) if shape['padType']=='ELLIPSE' else box(xy[0]-r,xy[1]-r,xy[0]+r,xy[1]+r)
        for layer in [1,2]:obs.append((net,layer,g))
    gaps=[]
    for i,(net,layer,g) in enumerate(obs):
        for n2,l2,g2 in obs[i+1:]:
            if layer==l2 and net!=n2:gaps.append({'a':net,'b':n2,'layer':layer,'distance_mm':g.distance(g2)})
    smallest=min(gaps,key=lambda z:z['distance_mm']); edge=min(g.distance(box(0,0,46,72).boundary) for n,l,g in obs)
    assert smallest['distance_mm']>=.25,smallest
    assert edge>=.5,edge
    board={'head':head,'records':records}
    pcb=native/'pcb/ElectrodeCoupon.epcb2';write_docs(pcb,libs+[board])
    profile=json.loads((args.sensor_project/'Sensor14Bank-FINAL-REVIEW.eprj3').read_text(encoding='utf-8'))
    profile.update(name=name,content='UNRELEASED compact three-electrode validation coupon. Not the complete panel.',default_sheet=pcb_id)
    profile['profile'].update(boards={board_id:{'uuid':board_id,'title':'ElectrodeCoupon','zIndex':1}},schematics={},sheets={},pcbs={pcb_id:{'uuid':pcb_id,'title':'ElectrodeCoupon','board':board_id,'parent_uuid':'','source':'','version':'1','updateTime':1793284800000}},panels={})
    profile['config']['defaultSheet']=pcb_id
    write_json(native/(name+'.eprj3'),profile)
    # Independent output is deliberately named source-geometry, not DRC/fab PASS.
    write_json(out/'source-geometry.json',{'status':'SOURCE_GEOMETRY_ONLY_NOT_MANUFACTURING_RELEASE','pcb_sha256':hashlib.sha256(pcb.read_bytes()).hexdigest(),'board_mm':[46,72],'minimum_different_net_gap':smallest,'minimum_copper_to_edge_mm':edge,'electrode_areas_mm2':{k:g.area for k,g in geoms.items()},'via_centers_mm':vias,'native_DRC':'NOT_RUN','native_export':'NOT_RUN','physical_validation':'NOT_RUN'})
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="460" height="720" viewBox="0 0 46 72">','<rect width="46" height="72" fill="#eef2f6"/>','<g transform="translate(0 72) scale(1 -1)">']
    for (net,layer,g) in obs:
        if layer!=1:continue
        color={'A':'#3b82f6','M':'#f59e0b','B':'#ef4444','GND':'#64748b'}.get(net,'#94a3b8')
        svg.append('<polygon points="'+' '.join(f'{x:.4f},{y:.4f}' for x,y in g.exterior.coords)+f'" fill="{color}"/>')
    svg+=['</g>','<text x="2" y="3" font-size="1.8">UNRELEASED COUPON 46 x 72 mm</text>','<text x="8" y="70" font-size="1.8">J1 top-side / pin numbers authoritative</text>','</svg>']
    (out/'coupon-source-preview.svg').write_text('\n'.join(svg),encoding='utf-8')
    mapping=list(csv.DictReader(args.harness.open(encoding='utf-8-sig',newline='')))
    assert len(mapping)==84 and {int(r['raw_index']) for r in mapping}==set(range(84))
    assert collections.Counter(r['kind'] for r in mapping)=={'pitch':75,'octave':5,'spare':4}
    assert all(int(r['raw_index'])==int(r['channel'])*6+int(r['bank']) for r in mapping)
    c5=[r for r in mapping if r['pitch']=='C5'];assert sorted(int(r['bank']) for r in c5)==[0,1,2] and all(r['channel']=='12' for r in c5)
    (ROOT/'ELECTRODE-HARNESS-84-VERIFIED.csv').write_bytes(args.harness.read_bytes())
    write_json(out/'interface-audit.json',{'status':'PASS_EXACT_84_MAPPING_NOT_COMPLETE_PANEL_GEOMETRY','csv_sha256':hashlib.sha256(args.harness.read_bytes()).hexdigest(),'unique_channels':84,'kind_counts':dict(collections.Counter(r['kind'] for r in mapping)),'C5_banks':[0,1,2],'J1_pin_by_channel':{r['channel']:int(r['pin']) for r in mapping if r['bank']=='0'}})
    choices=[]
    for pitch in intent['compact_candidate_parameters_mm']['note_pitch']:
        for length in intent['compact_candidate_parameters_mm']['slider_length']:
            choices.append({'pitch_mm':pitch,'slider_length_mm':length,'playing_panel_envelope_mm':[12*pitch+12+8,2*(length+18)+24],'status':'SPACE_STUDY_ONLY_EXCLUDES_SCREEN_AND_FINAL_MOUNTING'})
    write_json(out/'compact-space-studies.json',choices)
    print(json.dumps({'native_source':str(pcb),'minimum_gap_mm':smallest['distance_mm'],'edge_mm':edge,'interface_rows':84,'status':'CANDIDATE_ONLY'},ensure_ascii=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sensor-project',type=Path,required=True);p.add_argument('--harness',type=Path,required=True);build(p.parse_args())
