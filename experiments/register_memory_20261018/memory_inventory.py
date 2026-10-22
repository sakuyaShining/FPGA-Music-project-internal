"""Extract actual BSRAM ownership; proposed reservations are not implementation."""
from common import *
import xml.etree.ElementTree as ET,csv
def inventory(path):
 root=ET.parse(path).getroot();items=[]
 def visit(node,prefix=''):
    name=prefix+'/'+node.get('name','?')
    own=int(node.get('Bsram','0'))
    if own:items.append(dict(path=name,blocks=own,physical_bits=own*18432))
    for child in node:visit(child,name)
 visit(root)
 total=int(root.get('T_Bsram').split('(')[0]);assert sum(x['blocks'] for x in items)==total
 return dict(total=total,free=46-total,owners=items)
before=R/'reference/before-resources.xml';after=R/'synthesis_single_read/impl/gwsynthesis/probe_syn_rsc.xml'
a=inventory(before);b=inventory(after)
fx=lambda d:next(x['blocks'] for x in d['owners'] if x['path'].endswith('/u_fx'))
assert a['total']==46 and fx(a)==20
data=dict(status='measured memory inventory; future backend proposals not implemented',before=a,after=b,fx_before=fx(a),fx_after=fx(b),freed_blocks=a['total']-b['total'],physical_bits_per_block=18432,source_xml={p.relative_to(R).as_posix():sha(p) for p in (before,after)},
 backends=dict(configuration=dict(candidate='external 24LC256, previously planned; not confirmed present',persistent=True,implemented=False),audio_files=dict(candidate='board TF socket + qualified card',card_present_confirmed=False,filesystem_implemented=False),large_buffers=dict(candidate='in-package 8MiB SDRAM',persistent=False,controller_integrated=False)),
 proposed_budget_only=[dict(use='playback FIFO',blocks=1,capacity_bytes_at_16bit=2048),dict(use='record FIFO',blocks=1,capacity_bytes_at_16bit=2048),dict(use='event/score staging',blocks=2,capacity_bytes_at_16bit=4096),dict(use='SD block/metadata staging',blocks=1,capacity_bytes_at_16bit=2048)],
 caveat='FIFO reservation is only an example, not verified real-time/storage capacity; large rings still require SDRAM; card worst busy not measured')
(E/'memory-inventory.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
with (E/'memory-owners.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['version','path','blocks','physical_bits']);w.writeheader()
 for version,d in [('before',a),('after',b)]:
    for row in d['owners']:w.writerow(dict(version=version,**row))
print(json.dumps({k:data[k] for k in ('fx_before','fx_after','freed_blocks')}));print('Measured total',a['total'],'->',b['total'],'free',b['free'])
