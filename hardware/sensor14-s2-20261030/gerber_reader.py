from pathlib import Path
import hashlib,json,math,re
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union

def gerber(file):
    text = file.read_text()
    assert ('%FSLAX35Y35*%' in text or '%FSLAX45Y45*%' in text) and '%MOMM*%' in text
    assert '%LP' not in text, 'Polarity changes require an explicit parser extension'
    aps = {int(a): (s, list(map(float, d.split('X')))) for a, s, d in re.findall('%ADD(\\d+)(C|R|O|RoundRect),([-0-9.X]+)', text)}
    if any((s == 'RoundRect' for s, d in aps.values())):
        macro = '%AMRoundRect*1,1,$1,$2,$3*1,1,$1,$4,$5*1,1,$1,0-$2,0-$3*1,1,$1,0-$4,0-$5*20,1,$1,$2,$3,$4,$5,0*20,1,$1,$4,$5,0-$2,0-$3,0*20,1,$1,0-$2,0-$3,0-$4,0-$5,0*20,1,$1,0-$4,0-$5,$2,$3,0*4,1,4,$2,$3,$4,$5,0-$2,0-$3,0-$4,0-$5,$2,$3,0*%'
        assert macro in text, 'Unknown rounded rectangle aperture macro'
    shapes = []
    paths = []
    path = []
    active = False
    x = y = 0.0
    ap = None
    mode = 1
    for token in text.split('*'):
        t = token.strip()
        if t == 'G36':
            active = True
            paths = []
            path = []
            continue
        if t == 'G37':
            if path:
                paths.append(path)
            g = None
            for pp in paths:
                if len(pp) < 3:
                    continue
                pg = Polygon(pp)
                assert pg.is_valid
                g = pg if g is None else g.symmetric_difference(pg)
            if g is not None:
                shapes.append(g)
            active = False
            continue
        dm = re.fullmatch('(?:G54)?D(\\d+)', t)
        if dm:
            ap = int(dm[1])
            continue
        m = re.fullmatch('(?:G0([123]))?(?:X(-?\\d+))?(?:Y(-?\\d+))?(?:I(-?\\d+))?(?:J(-?\\d+))?D0([123])', t)
        if not m:
            assert not re.match('^(?:G0[123])?[XY].*D0[123]', t), 'Unparsed coordinate command ' + t
            continue
        if m[1]:
            mode = int(m[1])
        nx = float(m[2]) / 100000.0 if m[2] else x
        ny = float(m[3]) / 100000.0 if m[3] else y
        code = m[6]
        vertices = [(nx, ny)]
        if code == '1' and mode in [2, 3]:
            cx = x + (float(m[4]) / 100000.0 if m[4] else 0)
            cy = y + (float(m[5]) / 100000.0 if m[5] else 0)
            start = math.atan2(y - cy, x - cx)
            end = math.atan2(ny - cy, nx - cx)
            sweep = (end - start) % (2 * math.pi)
            if mode == 2:
                sweep = -((start - end) % (2 * math.pi))
            if abs(sweep) < 1e-12:
                sweep = 2 * math.pi * (1 if mode == 3 else -1)
            radius = math.hypot(x - cx, y - cy)
            n = max(4, math.ceil(abs(sweep) / (2 * math.pi) * 4096))
            vertices = [(cx + radius * math.cos(start + sweep * i / n), cy + radius * math.sin(start + sweep * i / n)) for i in range(1, n + 1)]
            vertices[-1] = (nx, ny)
        if active:
            if code == '2':
                if path:
                    paths.append(path)
                path = [(nx, ny)]
            elif code == '1':
                path.extend(vertices)
            else:
                raise ValueError('Flash within region')
        elif code == '1':
            shape, d = aps[ap]
            assert shape == 'C'
            shapes.append(LineString([(x, y)] + vertices).buffer(d[0] / 2, quad_segs=512))
        elif code == '3':
            shape, d = aps[ap]
            if shape == 'C':
                g = Point(nx, ny).buffer(d[0] / 2, quad_segs=512)
            elif shape == 'R':
                g = box(nx - d[0] / 2, ny - d[1] / 2, nx + d[0] / 2, ny + d[1] / 2)
            elif shape == 'RoundRect':
                assert len(d) == 5
                g = Polygon([(nx + d[1], ny + d[2]), (nx + d[3], ny + d[4]), (nx - d[1], ny - d[2]), (nx - d[3], ny - d[4])]).buffer(d[0] / 2, quad_segs=512)
            else:
                w, h = d[:2]
                g = LineString([(nx - max(0, w - h) / 2, ny - max(0, h - w) / 2), (nx + max(0, w - h) / 2, ny + max(0, h - w) / 2)]).buffer(min(w, h) / 2, quad_segs=512)
            shapes.append(g)
        x, y = (nx, ny)
    assert shapes and (not active)
    return unary_union(shapes)
