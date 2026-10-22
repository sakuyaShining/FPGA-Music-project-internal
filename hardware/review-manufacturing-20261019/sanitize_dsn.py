"""Repair exchange-only DSN details; never mutate native PCB geometry."""
import json
import math
import re

def sanitize(source, vias, selected_nets=None, selected_width_mil=8, new_clearance_mil=8):
    pins=[m.groups() for m in re.finditer(r'^\s*\(pin\s+(\S+)\s+(\S+)\s+([\d.-]+)\s+([\d.-]+)\)',source,re.M)]
    proxy_ids=set()
    for v in vias:
        matches=[p for p in pins if p[1]==v['id'].replace('e','') and math.hypot(float(p[2])-v['x'],float(p[3])-v['y'])<.02]
        if len(matches)!=1:
            matches=[p for p in pins if math.hypot(float(p[2])-v['x'],float(p[3])-v['y'])<.02]
        if len(matches)!=1:raise RuntimeError('Ambiguous via proxy '+v['id'])
        proxy_ids.add(matches[0][1])
    assert len(proxy_ids)==len(vias)
    lines=[];classes=0;vertices=0;current_class=None
    selected=set(selected_nets) if selected_nets is not None else None
    for line in source.splitlines():
        pin=re.match(r'\s*\(pin\s+\S+\s+(\S+)\s+',line)
        if pin and pin[1] in proxy_ids:continue
        for pid in proxy_ids:line=re.sub(r'(?<!\S)u1-'+re.escape(pid)+r'(?=\s|\))','',line)
        m=re.match(r"(\s*\(class)\s+(\S+)\s+'([^']*)'\s*$",line)
        if m:
            # Specctra uses double quotes. Native export used apostrophes in
            # the net token; keep class name and exact net identity consistent.
            assert m[2]==m[3],('Unexpected class/net',m.groups())
            line=m[1]+' '+json.dumps(m[2])+' '+json.dumps(m[3]);classes+=1
            current_class=m[2]
        elif re.fullmatch(r"\s*\(class\s+''\s*",line):
            line='    (class "UNCONNECTED"'
        m=re.match(r'(\s*\(shape\(polygon\s+\S+\s+[\d.]+)\s+([\d.\s-]+)(\)\))\s*$',line)
        if m:
            values=m[2].split();assert len(values)%2==0
            pairs=list(zip(values[::2],values[1::2]));clean=[]
            for pair in pairs:
                if not clean or pair!=clean[-1]:clean.append(pair)
            if len(clean)>1 and clean[0]==clean[-1]:clean.pop()
            assert len(clean)>=3
            vertices+=len(pairs)-len(clean)
            line=m[1]+' '+' '.join(x for pair in clean for x in pair)+m[3]
        # Preserve the existing 6 mil routes. Give newly routed nets 8 mil
        # clearance so exchange quantization cannot breach native 6 mil DRC.
        line=re.sub(r'\(clear\s+[\d.]+', '(clear 6', line)
        gap=new_clearance_mil if selected is None or current_class in selected else 6
        line=re.sub(r'\(clearance\s+[\d.]+', '(clearance '+str(gap), line)
        if selected is not None and current_class in selected:
            width=(39.37 if current_class in ['5V_IN','5V_FUSED','5V_PERIPH'] else
                   31.50 if current_class=='5V_PROTECTED' else
                   15.75 if current_class in ['3V3_IO','3V3_PERIPH','DAC_3V3'] else selected_width_mil)
            line=re.sub(r'\(width\s+[\d.]+', '(width '+str(width), line)
        lines.append(line)
    return '\n'.join(lines)+'\n',{'via_proxies_removed':len(proxy_ids),'class_net_quotes_normalized':classes,
        'duplicate_polygon_vertices_removed':vertices,'new_routing_clearance_mil':new_clearance_mil,'existing_routing_clearance_mil':6,
        'changes_native_pcb':False,'native_drc_still_required':True}
