from common import *
import xml.etree.ElementTree as ET
data={}
for mode in ('reference','buffered'):
 D=R/('synthesis_reference_retry' if mode=='reference' else 'synthesis_buffered');d=json.loads((D/'run.json').read_text(encoding='utf-8'));assert d['status']=='PASS synthesis only'
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256'],(mode,name)
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
 data[mode]=d
a=data['reference'];b=data['buffered']
assert a['project_sha256']==b['project_sha256'] and set(a['inputs'])==set(b['inputs'])
changed=[p for p in a['inputs'] if a['inputs'][p]['sha256']!=b['inputs'][p]['sha256']]
assert changed==['storage_probe.v'],changed
# Compare against the actual stage78 metrics, rather than assuming identical
# mappings when an otherwise inert wrapper gains additional ports.
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'));old=json.loads((Path(up['root'])/'delivery.json').read_text(encoding='utf-8'))
root=ET.parse(R/'synthesis_buffered/impl/gwsynthesis/probe_syn_rsc.xml').getroot()
owners={v.get('name'):{k:v.get(k,'0') for k in ('T_Register','T_Lut','T_Bsram')} for v in root.iter() if v.get('name') in ('buffers','recording','playback')}
result=dict(status='PASS joint synthesis resource audit only',before=a['metrics'],after=b['metrics'],stage78=old['resource']['after'],delta={k:b['metrics'][k]-a['metrics'][k] for k in a['metrics']},logic_spare=20736-b['metrics']['Logic'],bsram_spare=46-b['metrics']['BSRAM'],owners=owners,changed=changed,full_pnr=False,media_backend=False,hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',R/'synthesize.py',R/'synthesis_reference_retry/run.json',R/'synthesis_buffered/run.json',R/'synthesis_buffered/impl/gwsynthesis/probe_syn_rsc.xml']})
(E/'resource.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
