"""Check native PCB pad mapping independently against exported schematic and intent."""
import csv
import json
import math
from collections import Counter
from native_review import ROOT

def main():
    board=json.loads((ROOT/'pcb-pad-inventory.json').read_text(encoding='utf-8'))
    design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'expected-pin-nets.json').read_text())
    intended={p['ref']:p for p in design['parts']}
    placements={p['ref']:p for p in json.loads((ROOT/'pcb-placement-intent.json').read_text())['placements']}
    assert Counter(p['ref'] for p in board)==Counter(expected.keys()),'Missing/extra PCB component'
    rows=[];outside=[]
    for c in board:
        ref=c['ref'];p=intended[ref]
        assert c['code']==p['code'] and c['footprint']['name']==p['footprint'],('Wrong physical part',ref)
        assert Counter(q['n'] for q in c['pads'])==Counter(expected[ref].keys()),('Missing/extra pad',ref)
        for q in c['pads']:
            wanted=expected[ref][q['n']]
            assert (q['net'] or None)==wanted,('Wrong PCB net',ref,q['n'],wanted,q['net'])
            rows.append({'ref':ref,'pad':q['n'],'net':q['net'] or 'NC','x_mm':round(q['x']*.0254,5),'y_mm':round(q['y']*.0254,5)})
            w,h=q['shape'][1:3];a=math.radians(q['rotation'])
            dx=(abs(w*math.cos(a))+abs(h*math.sin(a)))*.0254/2
            dy=(abs(w*math.sin(a))+abs(h*math.cos(a)))*.0254/2
            if not (.3<=q['x']*.0254-dx and q['x']*.0254+dx<=139.7 and .3<=q['y']*.0254-dy and q['y']*.0254+dy<=99.7):outside.append((ref,q['n']))
        cx=(min(q['x'] for q in c['pads'])+max(q['x'] for q in c['pads']))/2*.0254
        cy=(min(q['y'] for q in c['pads'])+max(q['y'] for q in c['pads']))/2*.0254
        assert abs(cx-placements[ref]['x_mm'])<.005 and abs(cy-placements[ref]['y_mm'])<.005,('Placement did not persist',ref,cx,cy)
    assert not outside,('Pads outside board',outside)
    a=json.loads((ROOT/'v2-sch-netlist.json').read_text(encoding='utf-8'))['components']
    b=json.loads((ROOT/'v2-pcb-netlist.json').read_text(encoding='utf-8'))['components']
    assert set(a)==set(b),'Native association IDs do not match'
    for k,x in a.items():
        y=b[k]
        for field in ['Footprint','Device','Designator','Supplier Part']:
            assert x['props'][field]==y['props'][field],('Native physical identity',k,field)
        assert set(x['pinInfoMap'])==set(y['pinInfoMap'])
        for pin,p in x['pinInfoMap'].items():assert p['net']==y['pinInfoMap'][pin]['net'],('Native mismatch',k,pin)
    with (ROOT/'pcb-pad-net-audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'scope':'Native PCB physical device / pad identity and net mapping, plus provisional edge check; NOT routed-connectivity signoff',
        'components':len(board),'pads':len(rows),'connected_pads':sum(q['net']!='NC' for q in rows),
        'mapping_mismatches':0,'source_native_link_ids':len(a),'source_device_and_footprint_match':True,
        'provisional_size_mm':[140,100],'pad_edge_margin_mm':0.3,'pads_outside_margin':0,
        'routing_complete':False,'fabrication_release':False}
    (ROOT/'pcb-pad-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
