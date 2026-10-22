"""Read only selected-net copper from a Specctra SES; no placement import."""
import json
import re

def parse(source, selected):
    tokens=re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+',source)
    stack=[];root=None
    for token in tokens:
        if token=='(':
            node=[]
            if stack:stack[-1].append(node)
            elif root is not None:raise ValueError('Multiple roots')
            else:root=node
            stack.append(node)
            if len(stack)>100:raise ValueError('Excess nesting')
        elif token==')':
            if not stack:raise ValueError('Unbalanced SES')
            stack.pop()
        else:
            if not stack:raise ValueError('Atom outside SES')
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if stack or not root or root[0]!='session':raise ValueError('Invalid SES')
    child=lambda n,k:next(x for x in n if isinstance(x,list) and x and x[0]==k)
    routes=child(root,'routes');res=child(routes,'resolution')
    if res[1]!='mil':raise ValueError('Unsupported routing unit')
    scale=float(res[2]);assert scale>0
    diameters={}
    for p in child(routes,'library_out')[1:]:
        if not isinstance(p,list) or p[0]!='padstack':continue
        circles=[shape[1] for shape in p[2:] if isinstance(shape,list) and shape[0]=='shape' and shape[1][0]=='circle']
        diameters[p[1]]=max(float(c[2])/scale for c in circles)
    lines=[];vias=[]
    for n in child(routes,'network_out')[1:]:
        if not isinstance(n,list) or n[0]!='net' or n[1] not in selected:continue
        for item in n[2:]:
            if item[0]=='wire':
                path=child(item,'path');layer={'TopLayer':1,'Inner15':15,'Inner16':16,'BottomLayer':2}[path[1]]
                width=float(path[2])/scale;values=[float(x)/scale for x in path[3:]]
                if len(values)<4 or len(values)%2:raise ValueError('Bad route path')
                points=list(zip(values[::2],values[1::2]))
                for a,b in zip(points,points[1:]):
                    if a!=b:lines.append(dict(net=n[1],layer=layer,x1=a[0],y1=a[1],x2=b[0],y2=b[1],width=width))
            elif item[0]=='via':
                d=diameters[item[1]]
                if abs(d-24)>.1:raise ValueError('Review unfamiliar via diameter')
                vias.append(dict(net=n[1],x=float(item[2])/scale,y=float(item[3])/scale,diameter=d,hole=12))
    for p in lines:
        assert 0<p['width']<100
        for x,y in [(p['x1'],p['y1']),(p['x2'],p['y2'])]:assert -.1<=x<=5512 and -.1<=y<=3938
    return {'lines':lines,'vias':vias,'units':'mil','source_resolution_per_mil':scale}
