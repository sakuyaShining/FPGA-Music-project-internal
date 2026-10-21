"""Find complete native-pad networks in a partial local SES, without importing."""
import json
import sys
from pathlib import Path
from grid_route import capture
from physical_geometry import connected_subset
from native_review import ROOT
from ses_selected_copper import parse

label=sys.argv[1]
directory=Path(json.loads((ROOT/f'virtual-{label}-latest.json').read_text())['directory'])
nets=json.loads((directory/'attempt.json').read_text())['selected']
candidate=parse((directory/'result.ses').read_text(encoding='utf-8'),set(nets));source=capture()
report={};complete=[];lines=[];vias=[]
for net in nets:
    result=connected_subset([p for p in source['pads'] if p['net']==net],
                            [p for p in candidate['lines'] if p['net']==net],[p for p in candidate['vias'] if p['net']==net])
    report[net]={k:v for k,v in result.items() if k not in ['lines','vias']}
    if result['complete']:
        complete.append(net);lines+=result['lines'];vias+=result['vias']
pending={x['name'] for c in json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8')) if c['name']=='Connection Error' for x in c['list']}
summary={'label':label,'complete_nets':complete,'complete_currently_pending_nets':sorted(set(complete)&pending),'classification':report,
         'native_imported':False,'topology_tolerance_mm':.003,'native_drc_required':True}
(ROOT/f'ses-{label}-connectivity-classification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(directory/'complete-copper.json').write_text(json.dumps({'nets':complete,'lines':lines,'vias':vias},indent=2),encoding='utf-8')
print('COMPLETE',len(complete),'of',len(nets),'CURRENTLY PENDING',summary['complete_currently_pending_nets'],flush=True)
print('INCOMPLETE',[n for n in nets if n not in complete],flush=True)
