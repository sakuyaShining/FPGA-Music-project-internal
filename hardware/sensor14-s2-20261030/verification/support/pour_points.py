import math
def points(src):
    while isinstance(src[0], list):
        assert len(src) == 1
        src = src[0]
    x, y = src[:2]
    pts = [(x * 10, y * 10)]
    i = 2
    while i < len(src):
        if src[i] == 'L':
            i += 1
            continue
        if src[i] == 'ARC':
            deg, nx, ny = src[i + 1:i + 4]
            i += 4
            dx, dy = (nx - x, ny - y)
            theta = math.radians(deg)
            ll = math.hypot(dx, dy)
            if ll == 0:
                x, y = (nx, ny)
                continue
            hh = ll / (2 * math.tan(theta / 2))
            cx = (x + nx) / 2 - dy / ll * hh
            cy = (y + ny) / 2 + dx / ll * hh
            rad = math.hypot(x - cx, y - cy)
            phi = math.atan2(y - cy, x - cx)
            n = max(1, math.ceil(abs(deg) / 360 * 1024))
            pts.extend((((cx + rad * math.cos(phi + theta * j / n)) * 10, (cy + rad * math.sin(phi + theta * j / n)) * 10) for j in range(1, n + 1)))
            x, y = (nx, ny)
        else:
            x, y = src[i:i + 2]
            i += 2
            pts.append((x * 10, y * 10))
    return pts
