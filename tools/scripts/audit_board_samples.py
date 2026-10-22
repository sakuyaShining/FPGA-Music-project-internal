"""Audit captured FPGA samples; endpoint clipping is a separate hard failure."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
folder=ROOT/'sim_build/board_diag_20261009/hardware'
rows=[]
for path in sorted(folder.glob('*.npy')):
    values=np.load(path)
    assert values.dtype==np.int32 and values.ndim==1 and len(values)>0,path
    saturated=int(np.count_nonzero((values==8388607)|(values==-8388608)))
    rows.append(dict(file=path.name,samples=len(values),
                     peak=int(np.max(np.abs(values.astype(np.int64)))),
                     saturated=saturated,status='FAIL' if saturated else 'PASS'))
assert rows,'No FPGA sample captures found'
report=dict(criterion='24-bit endpoint saturation; silence allowed',cases=rows)
(folder/'sample-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
for row in rows:print(row['status'],row['file'],row['saturated'],'saturated /',row['samples'])
raise SystemExit(1 if any(row['status']=='FAIL' for row in rows) else 0)
