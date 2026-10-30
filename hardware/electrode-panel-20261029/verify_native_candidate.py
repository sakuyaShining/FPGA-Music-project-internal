"""Reparse saved PCB records; verify source geometry without claiming Gerber/DRC."""
from pathlib import Path
import collections, hashlib, json, math
from shapely.geometry import Point,Polygon,LineString,box
from shapely.affinity import scale,rotate,translate
from build_candidate import load_docs,write_json,ROOT

def main():
    file=ROOT/'candidate/ElectrodeCoupon-CANDIDATE/pcb/ElectrodeCoupon.epcb2'
    docs=load_docs(file);board=next(d for d in docs if d['head']['docType']=='PCB');libs={d['head']['uuid']:d for d in docs}
    attrs=collections.defaultdict(dict);padnets={};obs=[];fills={};terminals={}
    for h,v in board['records']:
        if h['type']=='ATTR':attrs[v['parentId']][v['key']]=v['value']
        if h['type']=='PAD_NET':
            _,cid,num,pid=json.loads(h['id']);padnets[cid,pid]=v['padNet'] or 'NC'+num
    for h,v in board['records']:
        t=h['type']
        if t=='FILL':
            a=v['path'];assert a[2]=='L' and v['width']==0
            xy=[a[:2]]+[a[i:i+2] for i in range(3,len(a),2)]
            g=Polygon([(x*.0254,y*.0254) for x,y in xy]);assert g.is_valid and not g.interiors
            fills[v['netName']]=g;obs.append((v['netName'],v['layerId'],g,'FILL'))
        elif t=='LINE':
            g=LineString([(v['startX']*.0254,v['startY']*.0254),(v['endX']*.0254,v['endY']*.0254)]).buffer(v['width']*.0254/2,quad_segs=128)
            obs.append((v['netName'],v['layerId'],g,'LINE'))
        elif t=='VIA':
            p=Point(v['centerX']*.0254,v['centerY']*.0254);g=p.buffer(v['viaDiameter']*.0254/2,quad_segs=128)
            terminals[v['netName']]=g
            assert v['viaDiameter']>v['holeDiameter']>0
            for layer in [1,2]:obs.append((v['netName'],layer,g,'VIA'))
        elif t=='COMPONENT':
            assert v['layerId']==1,'Verifier currently handles top side only'
            for ph,p in libs[attrs[h['id']]['Footprint']]['records']:
                if ph['type']!='PAD':continue
                d=p['defaultPad'];w=d['width']*.0254;ht=d['height']*.0254
                g=box(-w/2,-ht/2,w/2,ht/2) if d['padType']=='RECT' else scale(Point(0,0).buffer(1,quad_segs=256),w/2,ht/2)
                g=translate(rotate(g,p['padAngle'],origin=(0,0)),p['centerX']*.0254,p['centerY']*.0254)
                g=translate(rotate(g,v['angle'],origin=(0,0)),v['x']*.0254,v['y']*.0254)
                net=padnets[h['id'],ph['id']]
                for layer in [1,2]:obs.append((net,layer,g,'PAD'))
    assert set(fills)==set(terminals)=={'A','M','B'}
    assert len(padnets)==16 and len([n for n in padnets.values() if n.startswith('NC')])==11
    for net in fills:
        assert fills[net].buffer(1e-8).covers(terminals[net])
        bottom=[g for n,l,g,t in obs if n==net and l==2]
        # All three objects (pad, line, via) must belong to a single connected copper set.
        from shapely.ops import unary_union
        assert unary_union(bottom).geom_type=='Polygon',net
    assert unary_union([g for n,l,g,t in obs if n=='GND' and l==2]).geom_type=='Polygon'
    gaps=[(g.distance(g2),n,n2,l) for i,(n,l,g,t) in enumerate(obs) for n2,l2,g2,t2 in obs[i+1:] if n!=n2 and l==l2]
    gap=min(gaps);edge=min(g.distance(box(0,0,46,72).boundary) for n,l,g,t in obs)
    assert gap[0]>=.25 and edge>=.5
    layers=[json.loads(h['id'])[1] for h,v in board['records'] if h['type']=='LAYER' and v.get('use') and v['layerType'] in ['TOP','BOTTOM','SIGNAL','PLANE']]
    assert set(layers)=={1,2}
    # Area-overlap surrogate only: no electric field, body-ground, RC, overlay or noise model.
    curves=[]
    for diameter in [6,8,10]:
        for x in [21,23,25]:
            curve=[]
            for i in range(81):
                y=21+i*.5;finger=Point(x,y).buffer(diameter/2,quad_segs=128)
                a={k:g.intersection(finger).area for k,g in fills.items()};total=sum(a.values())
                assert total>0
                curve.append((a['M']+2*a['B'])/(2*total))
            curves.append({'diameter_mm':diameter,'x_mm':x,'largest_reverse_step':max([0]+[a-b for a,b in zip(curve,curve[1:])]),'range':[min(curve),max(curve)],'positions':curve})
    result={'status':'PASS_SAVED_NATIVE_SOURCE_GEOMETRY_ONLY','pcb_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'copper_layers':layers,'different_net_min_mm':gap[0],'different_net_min_pair':gap[1:],'edge_min_mm':edge,'three_signal_pad_trace_via_fill_connections':'PASS','ground_pins_15_16_connection':'PASS','unused_signal_pins':11,'surrogate_overlap_curves':curves,'native_DRC':'NOT_RUN','Gerber':'NOT_RUN','physical_validation':'NOT_RUN','release':False}
    write_json(ROOT/'candidate/saved-native-source-audit.json',result)
    # Render engineering geometry directly; this is a new diagram, not image editing.
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(460,720),'#eef2f6');dr=ImageDraw.Draw(im)
    for net,layer,g,typ in obs:
        if layer!=1:continue
        color={'A':'#3b82f6','M':'#f59e0b','B':'#ef4444','GND':'#64748b'}.get(net,'#94a3b8')
        dr.polygon([(round(x*10),round((72-y)*10)) for x,y in g.exterior.coords],fill=color)
    dr.text((15,10),'UNRELEASED 46 x 72 mm COUPON',fill='black')
    dr.text((15,690),'J1 top side; pin numbers authoritative',fill='black')
    im.save(ROOT/'candidate/coupon-source-preview.png')
    print(json.dumps({k:v for k,v in result.items() if k!='surrogate_overlap_curves'},ensure_ascii=True))
    return obs,result

if __name__=='__main__':main()
