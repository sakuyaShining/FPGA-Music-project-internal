"""Compare reopened native geometry with the last committed local route plan."""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from native_review import ROOT,PROJECT

load=lambda p:json.loads(p.read_text(encoding='utf-8'))
source=load(ROOT/'grid-source-core-fresh.json');plan=load(ROOT/'grid-plan-core-batch1.json')
current=load(ROOT/'core-native-after-reopen-source.json');nets=set(plan['nets'])
expected={key:[p for p in source[key] if p['net'] not in nets]+plan[key] for key in ['lines','vias']}
def copper_key(p,kind):
    if kind=='lines':
        a=tuple(round(p[k],4) for k in ['x1','y1']);b=tuple(round(p[k],4) for k in ['x2','y2'])
        return p['net'],p['layer'],min(a,b),max(a,b),round(p['width'],4)
    return p['net'],*(round(p[k],4) for k in ['x','y','diameter','hole'])
checks={kind:Counter(copper_key(p,kind) for p in expected[kind])==Counter(copper_key(p,kind) for p in current[kind]) for kind in ['lines','vias']}
sys.path.insert(0,'D:/FPGA-Project/codex-tools/shapely')
from shapely.geometry import LineString
from shapely.ops import unary_union
differences=[]
maximum_distance=0.
for net,layer,width in {(p['net'],p['layer'],round(p['width'],4)) for p in expected['lines']+current['lines']}:
    geometries=[]
    for dataset in [expected,current]:
        geometries.append(unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in dataset['lines'] if p['net']==net and p['layer']==layer and abs(p['width']-width)<1e-8]))
    distance=geometries[0].hausdorff_distance(geometries[1])
    maximum_distance=max(maximum_distance,distance)
    # Native coordinates round to 0.0001 mil: allow at most 0.000005 mm.
    if distance>5e-6:differences.append({'net':net,'layer':layer,'hausdorff_mm':distance})
checks['line_geometry_equivalent_with_native_junction_splits']=not differences
original_rules=load(PROJECT/'review-exports/v2/native-finish-core-1792484883356682500-rules-before.json')
reopened_rules=load(ROOT/'core-native-after-reopen-rules.json')
result={'native_trial':'Request timeout; temporary router primitives did not survive a save/close/reopen. No routing success claimed.',
        'source_matches_committed_batch1':checks,'rules_equal_structurally_after_reopen':original_rules==reopened_rules,
        'counts':{k:len(v) for k,v in current.items()},'connection_errors':119,'stale_pour_clearance_errors':389,
        'requires_ground_rebuild':True,'manufacturing_release':False}
result['native_junction_normalization']='I2C_MOD_SCL intersections split two planned lines into four native segments; compare physical geometry as well as segment counts.'
result['line_geometry_differences']=differences
result['maximum_centerline_difference_mm']=maximum_distance
result['native_coordinate_comparison_tolerance_mm']=5e-6
assert checks['vias'] and checks['line_geometry_equivalent_with_native_junction_splits'] and result['rules_equal_structurally_after_reopen']
path=ROOT/'native-timeout-recovery-audit.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
shutil.copy2(path,Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')/path.name)
print(json.dumps(result,indent=2))
