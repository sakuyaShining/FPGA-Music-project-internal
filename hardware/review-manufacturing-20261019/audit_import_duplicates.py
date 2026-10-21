"""Find redundant pre-import copper only when imported geometry covers it.

Read-only analysis. Run using the bundled Python 3.12 and isolated Shapely.
Coordinates are native mil; tolerance 0.05 mil = 1.27 micrometers.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,'D:/FPGA-Project/codex-tools/shapely')
from shapely.geometry import LineString
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent
old=json.loads((ROOT/'pcb-copper-before-offline-import.json').read_text())
allc=json.loads((ROOT/'pcb-copper-after-offline-import.json').read_text())
oldids={p['id'] for ps in old.values() for p in ps}
newlines=[p for p in allc['lines'] if p['id'] not in oldids]
newvias=[p for p in allc['vias'] if p['id'] not in oldids]
bykey=defaultdict(list)
for p in newlines:bykey[p['net'],p['layer']].append(p)
cache={};covered=[];uncovered=[]
for p in old['lines']:
    key=(p['net'],p['layer'],round(p['width'],2))
    if key not in cache:
        candidates=[LineString([(q['x1'],q['y1']),(q['x2'],q['y2'])])
                    for q in bykey[p['net'],p['layer']] if q['width']>=p['width']-.05]
        cache[key]=unary_union(candidates).buffer(.05)
    line=LineString([(p['x1'],p['y1']),(p['x2'],p['y2'])])
    (covered if line.difference(cache[key]).length<.01 else uncovered).append(p['id'])
vias=[];missing=[]
for p in old['vias']:
    exact=[q for q in newvias if q['net']==p['net'] and math.hypot(q['x']-p['x'],q['y']-p['y'])<.05
           and abs(q['diameter']-p['diameter'])<.05 and abs(q['hole']-p['hole'])<.05]
    (vias if exact else missing).append(p['id'])
result={'tolerance_mil':.05,'original_lines':len(old['lines']),'original_vias':len(old['vias']),
        'covered_original_line_ids':covered,'uncovered_original_line_ids':uncovered,
        'duplicated_original_via_ids':vias,'unmatched_original_via_ids':missing,
        'mutation_performed':False,'fabrication_release':False}
(ROOT/'copper-duplicate-coverage-audit.json').write_text(json.dumps(result,indent=2))
print({k:len(v) if isinstance(v,list) else v for k,v in result.items()})
