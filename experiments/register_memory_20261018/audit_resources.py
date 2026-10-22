from common import *
import xml.etree.ElementTree as ET
records={};owners={}
for label,folder in [('before','synthesis_reference'),('after','synthesis_compact_v1')]:
 D=R/folder;d=json.loads((D/'run.json').read_text(encoding='utf-8'));assert d['status']=='PASS synthesis only'
 for name,item in d['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],(label,name)
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
 records[label]=d
 xml=D/'impl/gwsynthesis/probe_syn_rsc.xml';root=ET.parse(xml).getroot()
 bank=next(v for v in root.iter() if v.get('name')=='u_reg')
 owners[label]={key:int(bank.get(key,'0').split('(')[0]) for key in ('T_Register','T_Lut','T_Bsram')}
assert records['before']['project_sha256']==records['after']['project_sha256']
assert set(records['before']['inputs'])==set(records['after']['inputs'])
different=[k for k,v in records['before']['inputs'].items() if v['sha256']!=records['after']['inputs'][k]['sha256']]
assert different==['tdm_top_owned.v'],different
before=records['before']['metrics'];after=records['after']['metrics']
assert before==dict(Logic=20635,BSRAM=28,Register=11592)
assert after==dict(Logic=19765,BSRAM=29,Register=10844)
record=dict(status='PASS same full joint project synthesis; not full-system PnR',before=before,after=after,
 logic_saved=before['Logic']-after['Logic'],registers_saved=before['Register']-after['Register'],
 extra_bsram=after['BSRAM']-before['BSRAM'],logic_spare=20736-after['Logic'],bsram_spare=46-after['BSRAM'],
 register_bank_owners=owners,differing_inputs=different,hardware_tested=False,
 inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',R/'run_synthesis.py',R/'synthesis_reference/run.json',R/'synthesis_compact_v1/run.json',R/'synthesis_reference/impl/gwsynthesis/probe_syn_rsc.xml',R/'synthesis_compact_v1/impl/gwsynthesis/probe_syn_rsc.xml']})
(E/'register-resources.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='inputs'}))
