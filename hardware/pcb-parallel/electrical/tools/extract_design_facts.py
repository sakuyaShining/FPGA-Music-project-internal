#!/usr/bin/env python3
"""Derive read-only design facts from the sealed 951 PCB checkpoint.

Writes derived/design-facts.json. Never modifies a design source.

Usage:
    python extract_design_facts.py [--checkpoint DIR] [--out FILE]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eda_log as E

COPPER_LAYERS = {1: 'TOP', 2: 'BOTTOM', 15: 'INNER1', 16: 'INNER2'}
LAYER_NAMES = {
    1: 'Top Layer', 2: 'Bottom Layer', 3: 'Top Silkscreen', 4: 'Bottom Silkscreen',
    5: 'Top Solder Mask', 6: 'Bottom Solder Mask', 7: 'Top Paste', 8: 'Bottom Paste',
    9: 'Top Assembly', 10: 'Bottom Assembly', 11: 'Board Outline', 12: 'Multi-Layer',
    13: 'Document', 14: 'Mechanical', 47: 'Hole', 48: 'Component Shape',
    49: 'Component Marking', 56: 'Drill Drawing',
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rect_from_path(path):
    """Return (x0, y0, x1, y1) in mil for an ['R', x, y_top, w, h, ...] path.

    Accepts both a flat path and a list of sub-paths ([[...], [...]]) as stored
    for REGION records.
    """
    if not path:
        return None
    if isinstance(path[0], list):
        boxes = [rect_from_path(sub) for sub in path]
        boxes = [b for b in boxes if b]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))
    if path[0] != 'R':
        return None
    x, y_top, w, h = path[1], path[2], path[3], path[4]
    return (x, y_top - h, x + w, y_top)


def bounds_from_poly_path(path):
    """Return (x0, y0, x1, y1) in mil for a [x, y, 'L', x1, y1, x2, y2, ...] poly path."""
    if not path:
        return None
    xs, ys = [], []
    index = 0
    while index < len(path):
        value = path[index]
        if isinstance(value, (int, float)) and index + 1 < len(path) and isinstance(path[index + 1], (int, float)):
            xs.append(value)
            ys.append(path[index + 1])
            index += 2
        else:
            index += 1
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', default=None)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    here = Path(__file__).resolve()
    repo = here.parents[4]
    checkpoint = Path(args.checkpoint) if args.checkpoint else repo / 'hardware/checkpoints/pcb-951ce88a-20261025'
    pcb_path = checkpoint / 'native/pcb/PCB1.epcb2'
    out_path = Path(args.out) if args.out else here.parents[1] / 'derived/design-facts.json'

    docs = E.load_documents(pcb_path)
    pcb_uuid, pcb = E.find_document(docs, 'PCB')

    # ---- board outline
    outline = None
    for _, poly in E.by_type(pcb, 'POLY'):
        if poly.get('layerId') == 11:
            outline = bounds_from_poly_path(poly.get('path'))
    board = {'outline_mil': outline}
    if outline:
        x0, y0, x1, y1 = outline
        board.update({
            'width_mm': E.mm(x1 - x0), 'height_mm': E.mm(y1 - y0),
            'origin_mil': [x0, y0], 'area_mm2': round(E.mm(x1 - x0) * E.mm(y1 - y0), 2),
        })

    # ---- stackup
    layers = {}
    for lid, payload in E.by_type(pcb, 'LAYER'):
        layers[payload.get('layerName')] = {'id': lid, 'type': payload.get('layerType'), 'use': payload.get('use')}
    stackup = []
    for lid, payload in E.by_type(pcb, 'LAYER_PHYS'):
        index = lid[1] if isinstance(lid, list) else lid
        stackup.append({
            'layer_id': index,
            'name': LAYER_NAMES.get(index, 'Dielectric' if index in (361, 362, 363) else str(index)),
            'copper': index in COPPER_LAYERS,
            'thickness_mm': payload.get('thickness'),
            'material': payload.get('material'),
            'permittivity': payload.get('permittivity'),
            'loss_tangent': payload.get('lossTangent'),
        })
    stackup.sort(key=lambda row: (row['layer_id'] if isinstance(row['layer_id'], int) else 999))
    board['stackup'] = stackup
    board['copper_layers'] = [{'layer_id': k, 'name': v} for k, v in COPPER_LAYERS.items()]
    board['enabled_inner_layers'] = [
        {'layer_id': lid[1], 'name': p.get('layerName')} for lid, p in E.by_type(pcb, 'LAYER')
        if p.get('layerType') == 'SIGNAL' and p.get('use')
    ]

    # ---- components + attributes
    components = {}
    for cid, payload in E.by_type(pcb, 'COMPONENT'):
        components[cid] = {
            'id': cid,
            'layer': 'TOP' if payload.get('layerId') == 1 else 'BOTTOM',
            'layer_id': payload.get('layerId'),
            'x_mil': payload.get('x'), 'y_mil': payload.get('y'),
            'x_mm': E.mm(payload.get('x') or 0), 'y_mm': E.mm(payload.get('y') or 0),
            'angle': payload.get('angle'),
            'locked': payload.get('locked'),
            'device': None, 'footprint': None, 'designator': None, 'pads': {},
        }
        raw_device = (payload.get('attrs') or {}).get('DeviceName')
        if raw_device:
            try:
                components[cid]['device'] = json.loads(raw_device).get('name')
            except json.JSONDecodeError:
                components[cid]['device'] = raw_device
    for _, attr in E.by_type(pcb, 'ATTR'):
        parent = attr.get('parentId')
        if parent not in components:
            continue
        key, value = attr.get('key'), attr.get('value')
        if key == 'Designator':
            components[parent]['designator'] = value
        elif key == 'Footprint':
            components[parent]['footprint'] = value
        elif key == 'Device':
            components[parent]['device_uuid'] = value

    # ---- pad -> net (PAD_NET id is ["PAD_NET", componentId, padNumber, padId])
    net_to_pads = {}
    for pid, payload in E.by_type(pcb, 'PAD_NET'):
        if not isinstance(pid, list) or len(pid) < 4:
            continue
        _, component_id, pad_number, pad_id = pid[0], pid[1], pid[2], pid[3]
        net = payload.get('padNet') or ''
        if component_id in components:
            components[component_id]['pads'][pad_number] = {'net': net, 'pad_id': pad_id}
        if net:
            net_to_pads.setdefault(net, []).append({
                'component': component_id,
                'designator': components.get(component_id, {}).get('designator'),
                'pad': pad_number,
            })

    # ---- board-level pads (test points, mounting holes)
    board_pads = []
    for pad_id, payload in E.by_type(pcb, 'PAD'):
        board_pads.append({
            'id': pad_id, 'num': payload.get('num'), 'net': payload.get('netName'),
            'layer_id': payload.get('layerId'),
            'x_mm': E.mm(payload.get('centerX') or 0), 'y_mm': E.mm(payload.get('centerY') or 0),
            'pad_type': payload.get('padType'), 'plated': payload.get('plated'),
            'hole_mm': None if not payload.get('hole') else {
                'type': payload['hole'].get('holeType'),
                'width': E.mm(payload['hole'].get('width') or 0),
                'height': E.mm(payload['hole'].get('height') or 0),
            },
            'size_mm': None if not payload.get('defaultPad') else {
                'type': payload['defaultPad'].get('padType'),
                'width': E.mm(payload['defaultPad'].get('width') or 0),
                'height': E.mm(payload['defaultPad'].get('height') or 0),
            },
        })

    # ---- vias / drills
    via_sizes = {}
    for _, payload in E.by_type(pcb, 'VIA'):
        key = (E.mm(payload.get('holeDiameter') or 0), E.mm(payload.get('viaDiameter') or 0))
        via_sizes.setdefault(str(key), {'hole_mm': key[0], 'diameter_mm': key[1], 'count': 0})
        via_sizes[str(key)]['count'] += 1

    # ---- keepouts
    keepouts = []
    for _, payload in E.by_type(pcb, 'REGION'):
        rect = rect_from_path(payload.get('path') or [])
        keepouts.append({
            'layer_id': payload.get('layerId'),
            'prohibit': payload.get('prohibitType'),
            'rect_mm': None if not rect else [E.mm(rect[0]), E.mm(rect[1]), E.mm(rect[2]), E.mm(rect[3])],
        })

    # ---- pours
    pours = []
    for _, payload in E.by_type(pcb, 'POUR'):
        pours.append({'net': payload.get('netName'), 'layer_id': payload.get('layerId'),
                      'name': payload.get('name'), 'fineness': (payload.get('pourType') or {}).get('fineness')})

    # ---- copper track length per layer
    track = {}
    for _, payload in E.by_type(pcb, 'LINE'):
        lid = payload.get('layerId')
        if lid not in COPPER_LAYERS:
            continue
        dx = (payload.get('endX') or 0) - (payload.get('startX') or 0)
        dy = (payload.get('endY') or 0) - (payload.get('startY') or 0)
        length = (dx * dx + dy * dy) ** 0.5
        entry = track.setdefault(COPPER_LAYERS[lid], {'segments': 0, 'length_mm': 0.0})
        entry['segments'] += 1
        entry['length_mm'] = round(entry['length_mm'] + E.mm(length), 2)

    # ---- rules
    rules = []
    for rid, payload in E.by_type(pcb, 'RULE'):
        if not isinstance(rid, list) or len(rid) < 3:
            continue
        rules.append({'kind': rid[1], 'name': rid[2], 'state': payload.get('ruleState')})

    components_out = sorted(
        (c for c in components.values() if c.get('designator')),
        key=lambda c: (''.join(ch for ch in c['designator'] if ch.isalpha()),
                       int(''.join(ch for ch in c['designator'] if ch.isdigit()) or 0)),
    )

    facts = {
        'schema': 1,
        'source': {
            'checkpoint': 'hardware/checkpoints/pcb-951ce88a-20261025',
            'pcb_path': 'native/pcb/PCB1.epcb2',
            'pcb_sha256': sha256(pcb_path),
            'pcb_doc_uuid': pcb_uuid,
            'units': {'coordinate': 'mil (0.001 in) converted to mm in *_mm fields',
                      'thickness': 'mm as stored'},
        },
        'board': board,
        'counts': {
            'components_with_designator': len(components_out),
            'components_total': len(components),
            'pads_with_net': sum(len(v) for v in net_to_pads.values()),
            'nets': len(net_to_pads),
            'board_level_pads': len(board_pads),
            'vias': sum(v['count'] for v in via_sizes.values()),
        },
        'net_to_pads': net_to_pads,
        'components': components_out,
        'board_level_pads': board_pads,
        'via_sizes': sorted(via_sizes.values(), key=lambda v: -v['count']),
        'keepouts': keepouts,
        'pours': pours,
        'copper_track': track,
        'rules': rules,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({
        'status': 'OK', 'out': str(out_path.relative_to(repo)) if str(out_path).startswith(str(repo)) else str(out_path),
        'pcb_sha256': facts['source']['pcb_sha256'],
        'board_mm': [board.get('width_mm'), board.get('height_mm')],
        'counts': facts['counts'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
