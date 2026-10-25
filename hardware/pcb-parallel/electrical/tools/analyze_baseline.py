#!/usr/bin/env python3
"""Structural diagnosis of the 951 baseline: density, layer use, power topology.

Read-only. Prints every number cited in BASELINE-STRUCTURE-20261025.md so the
claims can be re-derived instead of trusted. No geometry is modified.

Usage:
    python tools/analyze_baseline.py [--json]
"""
import argparse
import collections
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eda_log  # noqa: E402

PCB = (HERE / '../../../checkpoints/pcb-951ce88a-20261025/native/pcb/PCB1.epcb2').resolve()
LAYER = {1: 'TOP', 2: 'BOTTOM', 15: 'INNER1', 16: 'INNER2'}
MIL = eda_log.MIL_PER_MM

# A 0.152 mm trace with 0.152 mm clearance occupies 0.304 mm of pitch, so a
# square millimetre of a single layer holds about 1/0.304 = 3.29 mm of trace.
# This is an upper bound for a fully packed layer; real routers reach 60-80%.
TRACE_MM_PER_MM2 = 1.0 / 0.304


def mm(v):
    return v / MIL


def load_pcb():
    docs = eda_log.load_documents(PCB)
    return max(docs.values(), key=lambda d: len(d['records']))


def copper(pcb):
    length = collections.defaultdict(float)
    area = collections.defaultdict(float)
    segments = collections.Counter()
    for (kind, _), payload in pcb['records'].items():
        if kind != 'LINE' or not payload:
            continue
        layer = LAYER.get(payload['layerId'], str(payload['layerId']))
        seg = mm(math.hypot(payload['endX'] - payload['startX'],
                            payload['endY'] - payload['startY']))
        length[layer] += seg
        area[layer] += seg * mm(payload['width'])
        segments[layer] += 1
    return length, area, segments


def nets(pcb):
    length = collections.defaultdict(float)
    per_layer = collections.defaultdict(lambda: collections.defaultdict(float))
    segments = collections.Counter()
    widths = collections.defaultdict(set)
    vias = collections.Counter()
    for (kind, _), payload in pcb['records'].items():
        if not payload:
            continue
        if kind == 'LINE':
            name = payload.get('netName') or '(none)'
            layer = LAYER.get(payload['layerId'], str(payload['layerId']))
            seg = mm(math.hypot(payload['endX'] - payload['startX'],
                                payload['endY'] - payload['startY']))
            length[name] += seg
            per_layer[name][layer] += seg
            segments[name] += 1
            widths[name].add(round(mm(payload['width']), 3))
        elif kind == 'VIA':
            vias[payload.get('netName') or '(none)'] += 1
    return length, per_layer, segments, widths, vias


def grid(pcb, size=10.0):
    """Component count and copper length per size x size mm cell."""
    comps = collections.Counter()
    for (kind, _), payload in pcb['records'].items():
        if kind == 'COMPONENT' and payload:
            comps[(int(mm(payload['x']) // size), int(mm(payload['y']) // size))] += 1
    trace = collections.Counter()
    for (kind, _), payload in pcb['records'].items():
        if kind == 'LINE' and payload:
            x1, y1 = mm(payload['startX']), mm(payload['startY'])
            x2, y2 = mm(payload['endX']), mm(payload['endY'])
            cell = (int(((x1 + x2) / 2) // size), int(((y1 + y2) / 2) // size))
            trace[cell] += math.hypot(x2 - x1, y2 - y1)
    return comps, trace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    pcb = load_pcb()
    facts = json.loads((HERE / '../derived/design-facts.json').read_text(encoding='utf-8'))
    board = facts['board']
    area_mm2 = board['area_mm2']
    width_mm, height_mm = board['width_mm'], board['height_mm']

    length, copper_area, segments = copper(pcb)
    net_len, net_layer, net_seg, net_width, net_via = nets(pcb)
    comps, trace = grid(pcb)

    pours = facts['pours']
    power_nets = sorted(
        (n for n in facts['net_to_pads']
         if any(k in n for k in ('3V3', '5V', 'VIN', 'VBUS')) and n != 'GND'),
        key=lambda n: -len(facts['net_to_pads'][n]))

    out = {
        'source_pcb_sha256': facts['source']['pcb_sha256'],
        'board': {'width_mm': width_mm, 'height_mm': height_mm, 'area_mm2': area_mm2,
                  'copper_layers': len(board['copper_layers']),
                  'last_edit_utc': _edit_time(pcb)},
        'counts': facts['counts'],
        'layer_use': {},
        'pours': [{'layer_id': p['layer_id'], 'net': p['net'], 'name': p['name']} for p in pours],
        'power_nets': [],
        'density': {},
        'fanout': {},
    }

    total_len = sum(length.values())
    total_area = sum(copper_area.values())
    for layer in ('TOP', 'BOTTOM', 'INNER1', 'INNER2'):
        out['layer_use'][layer] = {
            'segments': segments[layer],
            'length_mm': round(length[layer], 1),
            'copper_mm2': round(copper_area[layer], 1),
            'coverage_pct': round(100 * copper_area[layer] / area_mm2, 2),
            'routing_utilisation_pct': round(
                100 * (length[layer] / area_mm2) / TRACE_MM_PER_MM2, 1),
        }
    out['layer_use']['TOTAL'] = {
        'segments': sum(segments.values()),
        'length_mm': round(total_len, 1),
        'copper_mm2': round(total_area, 1),
        'coverage_pct': round(100 * total_area / area_mm2, 2),
    }

    for name in power_nets:
        out['power_nets'].append({
            'net': name,
            'pads': len(facts['net_to_pads'][name]),
            'length_mm': round(net_len[name], 1),
            'segments': net_seg[name],
            'vias': net_via[name],
            'widths_mm': sorted(net_width[name]),
            'per_layer_mm': {k: round(v, 1) for k, v in sorted(net_layer[name].items())},
        })

    cells = int(width_mm // 10) * int(height_mm // 10)
    out['density'] = {
        'cell_mm': 10,
        'cells_total': cells,
        'cells_occupied': len(comps),
        'components_per_cell_mean': round(sum(comps.values()) / cells, 2),
        'components_per_cell_max': max(comps.values()),
        'components_per_cell_max_at_mm': [k[0] * 10 for k in _argmax(comps)],
        'trace_mm_per_cell_max': round(max(trace.values()), 1),
        'trace_mm_per_cell_max_at_mm': [k[0] * 10 for k in _argmax(trace)],
        'trace_mm_per_mm2_mean': round(total_len / area_mm2, 2),
        'vias_per_mm2': round(facts['counts']['vias'] / area_mm2, 3),
    }

    pos = {c['designator']: (c['x_mm'], c['y_mm']) for c in facts['components']}
    mux = ['U8', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6']
    if all(m in pos for m in mux):
        span, edges = _mst(pos, mux)
        out['fanout'] = {
            'source': 'U8',
            'destinations': mux[1:],
            'component_centres_mm': {m: pos[m] for m in mux},
            'mst_mm': round(span, 1),
            'mst_edges': [{'a': a, 'b': b, 'mm': round(d, 1)} for a, b, d in edges],
            'shared_control_nets': ['ADDR0', 'ADDR1', 'MUX_DISABLE'],
            'three_nets_estimate_mm': round(span * 3, 0),
        }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print('源 PCB SHA256:', out['source_pcb_sha256'])
    print('板面 %sx%s mm = %.0f mm2, 声明 %d 铜层, 最后编辑 %s'
          % (width_mm, height_mm, area_mm2, out['board']['copper_layers'],
             out['board']['last_edit_utc']))
    print()
    print('=== 层使用率（这才是瓶颈，不是密度）===')
    print('%-8s %8s %9s %10s %9s %9s' % ('layer', '段数', '长度mm', '铜面积mm2', '覆盖率', '布线利用'))
    for layer in ('TOP', 'BOTTOM', 'INNER1', 'INNER2', 'TOTAL'):
        r = out['layer_use'][layer]
        util = '%8.1f%%' % r['routing_utilisation_pct'] if 'routing_utilisation_pct' in r else '       -'
        print('%-8s %8d %9.0f %10.0f %8.2f%% %s'
              % (layer, r['segments'], r['length_mm'], r['copper_mm2'],
                 r['coverage_pct'], util))
    print()
    print('=== 铺铜分配（全部 4 层）===')
    for p in out['pours']:
        print('  L%-3s %-6s %s' % (p['layer_id'], p['net'], p['name']))
    if all(p['net'] == 'GND' for p in pours):
        print('  -> 四层全部是 GND，没有任何电源层')
    print()
    print('=== 电源网络（全部靠走线）===')
    print('%-14s %5s %9s %7s %6s  %s' % ('net', '焊盘', '长度mm', '段数', '过孔', '线宽mm'))
    for r in out['power_nets']:
        ws = r['widths_mm']
        wstr = '%.3f..%.3f' % (ws[0], ws[-1]) if len(ws) > 1 else '%.3f' % ws[0]
        print('%-14s %5d %9.1f %7d %6d  %s'
              % (r['net'], r['pads'], r['length_mm'], r['segments'], r['vias'], wstr))
    print()
    print('=== 空间密度（10x10mm 网格）===')
    d = out['density']
    print('  元件：平均 %.2f 个/格，最密 %d 个/格 @ x=%smm'
          % (d['components_per_cell_mean'], d['components_per_cell_max'],
             d['components_per_cell_max_at_mm'][0]))
    print('  走线：平均 %.2f mm/mm2，最密 %.0f mm/格 @ x=%smm'
          % (d['trace_mm_per_mm2_mean'], d['trace_mm_per_cell_max'],
             d['trace_mm_per_cell_max_at_mm'][0]))
    print('  过孔：%.3f 个/mm2' % d['vias_per_mm2'])
    print()
    if out['fanout']:
        f = out['fanout']
        print('=== 共享控制网扇出（按元件中心，MST 下界）===')
        for e in sorted(f['mst_edges'], key=lambda e: -e['mm']):
            print('  %-4s -- %-4s %6.1f mm' % (e['a'], e['b'], e['mm']))
        print('  单网 %.1f mm；%d 条网合计约 %.0f mm'
              % (f['mst_mm'], len(f['shared_control_nets']), f['three_nets_estimate_mm']))


def _edit_time(pcb):
    import datetime
    ms = pcb['head'].get('updateTime')
    if not ms:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime(
        '%Y-%m-%d %H:%M:%S UTC')


def _argmax(counter):
    return [max(counter, key=lambda k: counter[k])]


def _mst(pos, names):
    pts = [(n,) + pos[n] for n in names if n in pos]
    used = {0}
    total = 0.0
    edges = []
    while len(used) < len(pts):
        best = None
        for i in used:
            for j in range(len(pts)):
                if j in used:
                    continue
                dist = math.hypot(pts[i][1] - pts[j][1], pts[i][2] - pts[j][2])
                if best is None or dist < best[0]:
                    best = (dist, i, j)
        dist, i, j = best
        used.add(j)
        total += dist
        edges.append((pts[i][0], pts[j][0], dist))
    return total, edges


if __name__ == '__main__':
    main()
