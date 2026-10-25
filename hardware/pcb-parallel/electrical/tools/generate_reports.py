#!/usr/bin/env python3
"""Generate E3 interface / mechanical / rail reports from derived design facts.

Reads derived/design-facts.json (produced by extract_design_facts.py) and writes:
  derived/interfaces.json, derived/mechanical.json, derived/rails.json
  INTERFACES.md, MECHANICAL.md

No design source is modified. Units are mm unless stated.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FACTS = ROOT / 'derived/design-facts.json'

CONNECTORS = ['J5', 'J6', 'J10', 'J11', 'J12', 'J13', 'J20', 'J21', 'J22', 'J23', 'J24', 'J25']
RAILS = ['5V_IN', '5V_FUSED', '5V_PROTECTED', '5V_PERIPH', '3V3_IO', '3V3_PERIPH', 'DAC_3V3']


def pad_sort_key(pad):
    digits = ''.join(ch for ch in pad if ch.isdigit())
    return (0, int(digits)) if digits.isdigit() else (1, pad)


def load():
    return json.loads(FACTS.read_text(encoding='utf-8'))


def net_endpoints(facts, net, exclude=None):
    out = []
    for item in facts['net_to_pads'].get(net, []):
        if exclude and item['designator'] == exclude:
            continue
        out.append(f"{item['designator']}.{item['pad']}")
    return out


def summarize_endpoints(facts, net, exclude=None):
    """Keep tables readable: collapse large/power nets."""
    out = net_endpoints(facts, net, exclude)
    if net == 'GND':
        return f'地网（本表外共 {len(out)} 端点）'
    if net in RAILS:
        return f'电源网（本表外共 {len(out)} 端点）'
    if len(out) > 10:
        return f'{len(out)} 端点：' + ', '.join(out[:6]) + ' …'
    return ', '.join(out) if out else '—'


def build_interfaces(facts):
    comps = {c['designator']: c for c in facts['components']}
    interfaces = []
    for des in CONNECTORS:
        comp = comps.get(des)
        if not comp:
            interfaces.append({'designator': des, 'present': False,
                               'note': '951 原生 PCB 中不存在该位号'})
            continue
        pins = []
        for pad in sorted(comp['pads'], key=pad_sort_key):
            net = comp['pads'][pad]['net']
            pins.append({
                'pin': pad,
                'net': net or None,
                'also_on': net_endpoints(facts, net, exclude=des) if net else [],
                'also_on_summary': summarize_endpoints(facts, net, exclude=des) if net else '—',
            })
        interfaces.append({
            'designator': des, 'present': True, 'device': comp['device'],
            'side': comp['layer'], 'x_mm': comp['x_mm'], 'y_mm': comp['y_mm'],
            'rotation_deg': comp['angle'], 'pin_count': len(pins),
            'pins': pins,
            'unconnected_pins': [p['pin'] for p in pins if not p['net']],
        })
    return interfaces


def build_mechanical(facts):
    comps = facts['components']
    holes = [p for p in facts['board_level_pads'] if p['num'].startswith('H')]
    tps = [p for p in facts['board_level_pads'] if p['num'].startswith('TP')]
    board = facts['board']
    edges = {
        'left_mm': 0.0, 'right_mm': board['width_mm'],
        'bottom_mm': 0.0, 'top_mm': board['height_mm'],
    }
    near_edge = []
    for c in comps:
        d = {
            'left': c['x_mm'], 'right': board['width_mm'] - c['x_mm'],
            'bottom': c['y_mm'], 'top': board['height_mm'] - c['y_mm'],
        }
        side = min(d, key=d.get)
        if d[side] <= 12.0:
            near_edge.append({'designator': c['designator'], 'device': c['device'],
                              'edge': side, 'distance_mm': round(d[side], 2),
                              'x_mm': c['x_mm'], 'y_mm': c['y_mm']})
    return {
        'board': {k: board[k] for k in ('width_mm', 'height_mm', 'area_mm2')},
        'edges': edges,
        'mounting_holes': [{'ref': p['num'], 'x_mm': p['x_mm'], 'y_mm': p['y_mm'],
                            'drill_mm': p['hole_mm']['width'], 'plated': p['plated']} for p in holes],
        'test_points': [{'ref': p['num'], 'net': p['net'], 'x_mm': p['x_mm'], 'y_mm': p['y_mm'],
                         'pad_dia_mm': p['size_mm']['width']} for p in tps],
        'keepouts': facts['keepouts'],
        'components_top': sum(1 for c in comps if c['layer'] == 'TOP'),
        'components_bottom': [c['designator'] for c in comps if c['layer'] == 'BOTTOM'],
        'near_edge_within_12mm': near_edge,
        'stackup': facts['board']['stackup'],
        'copper_track': facts['copper_track'],
        'pours': facts['pours'],
        'via_sizes': facts['via_sizes'],
    }


def build_rails(facts):
    comps = {c['designator']: c for c in facts['components']}
    rails = {}
    for rail in RAILS:
        entries = facts['net_to_pads'].get(rail, [])
        loads = []
        for item in entries:
            comp = comps.get(item['designator'])
            loads.append({
                'designator': item['designator'],
                'device': comp['device'] if comp else None,
                'pins': sorted({x['pad'] for x in entries if x['designator'] == item['designator']},
                               key=pad_sort_key),
            })
        deduped = {}
        for load in loads:
            deduped[load['designator']] = load
        rails[rail] = {'pad_count': len(entries), 'devices': list(deduped.values())}
    return rails


def render_interfaces(interfaces):
    lines = ['# 接口逐针表（951 原生网表派生）', '',
             '数据来源：`derived/design-facts.json`（由 `tools/extract_design_facts.py` 从',
             '`hardware/checkpoints/pcb-951ce88a-20261025/native/pcb/PCB1.epcb2` 派生，',
             'PCB SHA256 `951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d`）。',
             '', '本表只陈述原生焊盘→网络事实，不代表接法已被电气确认；判据见 `constraints.json`。', '']
    for iface in interfaces:
        if not iface['present']:
            lines += [f"## {iface['designator']}", '',
                      f"951 原生 PCB 中**不存在**该位号（{iface['note']}）。", '']
            continue
        lines += [f"## {iface['designator']} — {iface['device']}", '',
                  f"- 层：{iface['side']}；位置：({iface['x_mm']}, {iface['y_mm']}) mm；旋转 {iface['rotation_deg']}°",
                  f"- 引脚数：{iface['pin_count']}；未接（NC）：{', '.join(iface['unconnected_pins']) or '无'}",
                  '', '| 脚 | 网络 | 该网络的其它端点 |', '|---:|---|---|']
        for pin in iface['pins']:
            others = pin['also_on_summary']
            lines.append(f"| {pin['pin']} | {pin['net'] or '(NC)'} | {others} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def render_mechanical(mech):
    b = mech['board']
    lines = ['# 机械与装配事实（951 原生 PCB 派生）', '',
             f"- 板框：{b['width_mm']} × {b['height_mm']} mm（面积 {b['area_mm2']} mm²），矩形，原点在左下角",
             f"- 顶层器件 {mech['components_top']} 个；底层器件 {len(mech['components_bottom'])} 个"
             f"（{', '.join(mech['components_bottom'])}）→ **双面贴装**",
             '', '## 安装孔', '', '| 位号 | X (mm) | Y (mm) | 钻孔 (mm) | 镀通 |', '|---|---:|---:|---:|---|']
    for hole in mech['mounting_holes']:
        lines.append(f"| {hole['ref']} | {hole['x_mm']} | {hole['y_mm']} | {hole['drill_mm']} | "
                     f"{'是' if hole['plated'] else '否 (NPTH)'} |")
    lines += ['', '## 角部禁布区', '',
              '| 层 | 禁止对象 | X0 | Y0 | X1 | Y1 |', '|---|---|---:|---:|---:|---:|']
    for ko in mech['keepouts']:
        r = ko['rect_mm']
        if not r:
            continue
        lines.append(f"| {ko['layer_id']} | {', '.join(ko['prohibit'] or [])} | "
                     f"{r[0]} | {r[1]} | {r[2]} | {r[3]} |")
    lines += ['', '## 距板边 ≤12 mm 的器件（装配/外壳净空关注项）', '',
              '| 位号 | 器件 | 最近边 | 距边 (mm) | X | Y |', '|---|---|---|---:|---:|---:|']
    for item in sorted(mech['near_edge_within_12mm'], key=lambda x: x['distance_mm']):
        lines.append(f"| {item['designator']} | {item['device']} | {item['edge']} | "
                     f"{item['distance_mm']} | {item['x_mm']} | {item['y_mm']} |")
    lines += ['', '## 叠层（存储值 × 0.0254 = mm）', '',
              '| 层 | 类型 | 厚度 (mm) | 材料 | εr |', '|---|---|---:|---|---:|']
    for row in mech['stackup']:
        if row['thickness_mm'] in (0, None):
            continue
        lines.append(f"| {row['name']} | {'铜' if row['copper'] else '介质'} | "
                     f"{round(row['thickness_mm'] * 0.0254, 4)} | {row['material'] or '—'} | "
                     f"{row['permittivity'] or '—'} |")
    total = sum(row['thickness_mm'] * 0.0254 for row in mech['stackup'] if row['thickness_mm'])
    lines += ['', f"叠层合计（不含阻焊）：**{round(total, 3)} mm**，与 1.6 mm 常规四层板一致。", '',
              '## 过孔', '', '| 钻孔 (mm) | 外径 (mm) | 数量 |', '|---:|---:|---:|']
    for via in mech['via_sizes']:
        lines.append(f"| {via['hole_mm']} | {via['diameter_mm']} | {via['count']} |")
    lines += ['', '## 铜层走线长度', '', '| 层 | 段数 | 总长 (mm) |', '|---|---:|---:|']
    for layer, data in mech['copper_track'].items():
        lines.append(f"| {layer} | {data['segments']} | {data['length_mm']} |")
    lines += ['', '## 测试点', '', '| 位号 | 网络 | X | Y | 焊盘直径 (mm) |', '|---|---|---:|---:|---:|']
    for tp in mech['test_points']:
        lines.append(f"| {tp['ref']} | {tp['net']} | {tp['x_mm']} | {tp['y_mm']} | {tp['pad_dia_mm']} |")
    return '\n'.join(lines) + '\n'


def main():
    facts = load()
    interfaces = build_interfaces(facts)
    mech = build_mechanical(facts)
    rails = build_rails(facts)
    derived = ROOT / 'derived'
    derived.mkdir(exist_ok=True)
    (derived / 'interfaces.json').write_text(json.dumps(interfaces, ensure_ascii=False, indent=1), encoding='utf-8')
    (derived / 'mechanical.json').write_text(json.dumps(mech, ensure_ascii=False, indent=1), encoding='utf-8')
    (derived / 'rails.json').write_text(json.dumps(rails, ensure_ascii=False, indent=1), encoding='utf-8')
    (ROOT / 'INTERFACES.md').write_text(render_interfaces(interfaces), encoding='utf-8')
    (ROOT / 'MECHANICAL.md').write_text(render_mechanical(mech), encoding='utf-8')
    print(json.dumps({
        'status': 'OK',
        'interfaces': [i['designator'] for i in interfaces if i['present']],
        'missing': [i['designator'] for i in interfaces if not i['present']],
        'rails': {k: v['pad_count'] for k, v in rails.items()},
        'files': ['derived/interfaces.json', 'derived/mechanical.json', 'derived/rails.json',
                  'INTERFACES.md', 'MECHANICAL.md'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.exit(main())
