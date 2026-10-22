from common import *
import xml.etree.ElementTree as ET
data={}
for mode,folder in (('reference','synthesis_reference_final'),('buffered','synthesis_buffered_retry')):
 D=R/folder;d=json.loads((D/'run.json').read_text(encoding='utf-8'))
 assert d['status']=='PASS synthesis only' and d['returncode']==0
 assert not (D/'interruption.json').exists(),'manual termination cannot qualify a build'
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256'],(mode,name)
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
 data[mode]=d
a=data['reference'];b=data['buffered']
assert a['project_sha256']==b['project_sha256'] and set(a['inputs'])==set(b['inputs'])
changed=[p for p in a['inputs'] if a['inputs'][p]['sha256']!=b['inputs'][p]['sha256']]
assert changed==['sdram_stream_probe.v'],changed
root=ET.parse(R/'synthesis_buffered_retry/impl/gwsynthesis/probe_syn_rsc.xml').getroot()
hierarchy={v.get('name'):v.attrib for v in root.iter() if v.get('name') in ('transport','arbiter','buffers','sdram')}
assert all(k in hierarchy for k in ('transport','arbiter','buffers','sdram')),hierarchy
assert int(hierarchy['arbiter']['T_Register'].split('(')[0])>0
result=dict(status='PASS joint synthesis only; no joint pin/timing/board qualification',
 before=a['metrics'],after=b['metrics'],delta={k:b['metrics'][k]-a['metrics'][k] for k in a['metrics']},
 logic_spare=20736-b['metrics']['Logic'],bsram_spare=46-b['metrics']['BSRAM'],hierarchy=hierarchy,
 changed=changed,selected_builds=['synthesis_reference_final','synthesis_buffered_retry'],
 rejected_build='synthesis_buffered_final: manually terminated after reports; apparent return0 not accepted',
 full_pnr=False,hardware_tested=False,
 inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',R/'synthesize.py',R/'synthesis_reference_final/run.json',R/'synthesis_buffered_retry/run.json',R/'synthesis_buffered_retry/impl/gwsynthesis/probe_syn_rsc.xml',R/'synthesis_buffered_final/interruption.json']})
assert result['logic_spare']>=0 and result['bsram_spare']>=0,'does not fit selected device'
(E/'resource.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','hierarchy')}))
