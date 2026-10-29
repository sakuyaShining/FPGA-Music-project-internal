"""Conservative Gerber copper-component audit, independent of native DRC."""
from pathlib import Path
import hashlib,json,math,re
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union
from verify_native_candidate import main as native_audit
from build_candidate import ROOT,write_json

def gerber(file):
    text=file.read_text();assert '%FSLAX35Y35*%' in text and '%MOMM*%' in text
    assert '%LP' not in text,'Polarity changes require an explicit parser extension'
    aps={int(a):(s,list(map(float,d.split('X')))) for a,s,d in re.findall(r'%ADD(\d+)(C|R|O|RoundRect),([-0-9.X]+)',text)}
    if any(s=='RoundRect' for s,d in aps.values()):
        macro='%AMRoundRect*1,1,$1,$2,$3*1,1,$1,$4,$5*1,1,$1,0-$2,0-$3*1,1,$1,0-$4,0-$5*20,1,$1,$2,$3,$4,$5,0*20,1,$1,$4,$5,0-$2,0-$3,0*20,1,$1,0-$2,0-$3,0-$4,0-$5,0*20,1,$1,0-$4,0-$5,$2,$3,0*4,1,4,$2,$3,$4,$5,0-$2,0-$3,0-$4,0-$5,$2,$3,0*%'
        assert macro in text,'Unknown rounded rectangle aperture macro'
    shapes=[];paths=[];path=[];active=False;x=y=0.;ap=None;mode=1
    for token in text.split('*'):
        t=token.strip()
        if t=='G36':active=True;paths=[];path=[];continue
        if t=='G37':
            if path:paths.append(path)
            g=None
            for pp in paths:
                if len(pp)<3:continue
                pg=Polygon(pp);assert pg.is_valid
                g=pg if g is None else g.symmetric_difference(pg)
            if g is not None:shapes.append(g)
            active=False;continue
        dm=re.fullmatch(r'(?:G54)?D(\d+)',t)
        if dm:ap=int(dm[1]);continue
        m=re.fullmatch(r'(?:G0([123]))?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0([123])',t)
        if not m:
            assert not re.match(r'^(?:G0[123])?[XY].*D0[123]',t),'Unparsed coordinate command '+t
            continue
        if m[1]:mode=int(m[1])
        nx=float(m[2])/1e5 if m[2] else x;ny=float(m[3])/1e5 if m[3] else y;code=m[6];vertices=[(nx,ny)]
        if code=='1' and mode in [2,3]:
            cx=x+(float(m[4])/1e5 if m[4] else 0);cy=y+(float(m[5])/1e5 if m[5] else 0)
            start=math.atan2(y-cy,x-cx);end=math.atan2(ny-cy,nx-cx);sweep=(end-start)%(2*math.pi)
            if mode==2:sweep=-((start-end)%(2*math.pi))
            if abs(sweep)<1e-12:sweep=2*math.pi*(1 if mode==3 else -1)
            radius=math.hypot(x-cx,y-cy);n=max(4,math.ceil(abs(sweep)/(2*math.pi)*4096))
            vertices=[(cx+radius*math.cos(start+sweep*i/n),cy+radius*math.sin(start+sweep*i/n)) for i in range(1,n+1)];vertices[-1]=(nx,ny)
        if active:
            if code=='2':
                if path:paths.append(path)
                path=[(nx,ny)]
            elif code=='1':path.extend(vertices)
            else:raise ValueError('Flash within region')
        elif code=='1':
            shape,d=aps[ap];assert shape=='C'
            shapes.append(LineString([(x,y)]+vertices).buffer(d[0]/2,quad_segs=512))
        elif code=='3':
            shape,d=aps[ap]
            if shape=='C':g=Point(nx,ny).buffer(d[0]/2,quad_segs=512)
            elif shape=='R':g=box(nx-d[0]/2,ny-d[1]/2,nx+d[0]/2,ny+d[1]/2)
            elif shape=='RoundRect':
                assert len(d)==5
                g=Polygon([(nx+d[1],ny+d[2]),(nx+d[3],ny+d[4]),(nx-d[1],ny-d[2]),(nx-d[3],ny-d[4])]).buffer(d[0]/2,quad_segs=512)
            else:
                w,h=d[:2];g=LineString([(nx-max(0,w-h)/2,ny-max(0,h-w)/2),(nx+max(0,w-h)/2,ny+max(0,h-w)/2)]).buffer(min(w,h)/2,quad_segs=512)
            shapes.append(g)
        x,y=nx,ny
    assert shapes and not active
    return unary_union(shapes)

def main():
    obs,source=native_audit();out=ROOT/'candidate';directory=out/'gerber-candidate';results={}
    for layer,suffix,count in [(1,'TopLayer.GTL',19),(2,'BottomLayer.GBL',15)]:
        p=directory/('Gerber_'+suffix);actual=gerber(p)
        expected=unary_union([g for n,l,g,t in obs if l==layer])
        assert expected.difference(actual.buffer(.005)).is_empty
        assert actual.difference(expected.buffer(.005)).is_empty
        pieces=list(actual.geoms) if hasattr(actual,'geoms') else [actual]
        assert len(pieces)==count,(layer,len(pieces))
        labelled=[]
        for g in pieces:
            nets={n for n,l,s,t in obs if l==layer and g.intersection(s).area>1e-5}
            assert len(nets)==1,('actual copper joins multiple source nets',nets)
            labelled.append((next(iter(nets)),g))
        gaps=[(g.distance(g2),n,n2) for i,(n,g) in enumerate(labelled) for n2,g2 in labelled[i+1:] if n!=n2]
        minimum=min(gaps);assert minimum[0]>=.25,minimum
        edge=min(g.distance(box(0,0,46,72).boundary) for n,g in labelled);assert edge>=.5
        for net in ['A','M','B']:
            assert len([g for n,g in labelled if n==net])==(2 if layer==1 else 1)
        results[str(layer)]={'gerber_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'copper_components':len(pieces),'min_different_net_gap_mm':minimum[0],'min_pair':minimum[1:],'min_edge_mm':edge,'source_export_hausdorff_mm':actual.hausdorff_distance(expected)}
    active=unary_union([g for n,l,g,t in obs if t=='FILL'])
    masks={}
    for suffix in ['TopSolderMaskLayer.GTS','BottomSolderMaskLayer.GBS']:
        mask=gerber(directory/('Gerber_'+suffix));pieces=list(mask.geoms)
        assert len(pieces)==16
        assert mask.intersection(active).is_empty,'Active electrode aperture must not be exposed'
        assert all(mask.buffer(.0001).covers(g) for n,l,g,t in obs if t=='PAD' and l==1)
        masks[suffix]={'apertures':len(pieces),'active_electrode_openings':0,'header_pad_apertures_cover_copper':True}
    drill_text=(directory/'Drill_PTH_Through.DRL').read_text()
    assert 'METRIC,LZ,000.00000' in drill_text
    tools={int(i):float(d) for i,d in re.findall(r'^T(\d+)C([.\d]+)$',drill_text,re.M)}
    holes=[];tool=None
    for line in drill_text.splitlines():
        if re.fullmatch(r'T\d+',line):tool=int(line[1:])
        m=re.fullmatch(r'X(-?[.\d]+)Y(-?[.\d]+)',line)
        if m:holes.append((float(m[1]),float(m[2]),tools[tool]))
    assert len(holes)==19 and len(set(holes))==19
    expectations=[(g.centroid.x,g.centroid.y, .4 if t=='VIA' else 1.0200132) for n,l,g,t in obs if l==1 and t in ['PAD','VIA']]
    remaining=holes.copy()
    for x,y,d in expectations:
        h=min(remaining,key=lambda q:math.hypot(x-q[0],y-q[1]))
        assert math.hypot(x-h[0],y-h[1])<.001 and abs(d-h[2])<.00002
        remaining.remove(h)
    assert not remaining
    via_text=(directory/'Drill_PTH_Through_Via.DRL').read_text()
    via_xy={(float(x),float(y)) for x,y in re.findall(r'^X(-?[.\d]+)Y(-?[.\d]+)$',via_text,re.M)}
    assert via_xy=={(x,y) for x,y,d in holes if abs(d-.4)<1e-6},'Separate via drill file must be the same subset, not additional holes'
    outline=(directory/'Gerber_BoardOutlineLayer.GKO').read_text()
    contour=[(int(x)/1e5,int(y)/1e5) for x,y in re.findall(r'G01X(-?\d+)Y(-?\d+)D0[12]',outline)]
    assert contour==[(0,0),(0,72),(46,72),(46,0),(0,0)]
    report={'status':'PASS_CANDIDATE_COPPER_MASK_DRILL_OUTLINE_GEOMETRY','source_sha256':source['pcb_sha256'],'Gerber_zip_sha256':hashlib.sha256((out/'ElectrodeCoupon-native-Gerber-CANDIDATE.zip').read_bytes()).hexdigest(),'layers':results,'different_net_gate_mm':.25,'source_equivalence_tolerance_mm':.005,'equivalence_tolerance_does_not_relax_clearance_gate':True,'mask':masks,'plated_drill_holes':19,'drill_coordinate_match_tolerance_mm':.001,'outline_mm':[46,72],'physical_validation':'PENDING','manufacturing_release':False}
    write_json(out/'Gerber-copper-audit.json',report);print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':main()
