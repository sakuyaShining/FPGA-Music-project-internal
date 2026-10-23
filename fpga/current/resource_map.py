"""Separate engine cost from diagnostic wrapper cost using actual synthesis XML."""
from common import *
import xml.etree.ElementTree as ET
files=[Path(__file__).resolve(),R/'common.py',R/'build_nominal_v4/impl/gwsynthesis/board_syn_rsc.xml',R/'build_nominal_v4/impl/pnr/board.rpt.txt']
def value(node,key):return int(node.get(key,'0').split('(')[0])
def walk(node,path=''):
    path+=('/' if path else '')+node.get('name')
    # GW2AR RAM16 occupancy is counted as six Logic per SSRAM in this report.
    l,a,s=[value(node,'T_'+k) for k in ('Lut','Alu','Ssram')]
    row=dict(path=path,logic=l+a+6*s,lut=l,alu=a,ssram=s,register=value(node,'T_Register'),bsram=value(node,'T_Bsram'))
    yield row
    for child in node:yield from walk(child,path)
rows=list(walk(ET.parse(files[2]).getroot()))
assert rows[0]['logic']==20164 and rows[0]['register']==10760
focus=[v for v in rows if v['path'] in ('joint_timing_top','joint_timing_top/scan_storage','joint_timing_top/system') or v['path'].count('/')==2]
result=dict(status='PASS measured synthesis resource ledger; not a place/route qualification',summary=focus,
    largest_hierarchies=sorted(rows[1:],key=lambda v:v['logic'],reverse=True)[:30],
    caveat='Hierarchy totals overlap and must not be added; post-map Logic 20164 is not routed Logic 20478. Full route failed.',
    inputs={p.relative_to(R).as_posix():sha(p) for p in files})
(E/'resource-map.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for row in focus:print(json.dumps(row))
