"""Compare identical complete resource probes; synthesis is not timing sign-off."""
from common import *
import xml.etree.ElementTree as ET
data={};hierarchy={}
folders={'reference':'synthesis_reference_final','buffered':'synthesis_buffered_bank_v3'}
for mode,folder in folders.items():
    D=R/folder;d=json.loads((D/'run.json').read_text(encoding='utf-8'))
    assert d['status']=='PASS synthesis only' and d['returncode']==0
    for name,v in d['inputs'].items():
        assert sha(D/name)==sha(R/v['source'])==v['sha256'],(mode,name)
    assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
    data[mode]=d
    root=ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot()
    pitch=[x for x in root.iter() if x.get('name')=='u_pmod'];assert len(pitch)==1
    hierarchy[mode]=pitch[0].attrib
a,b=data['reference'],data['buffered']
assert a['project_sha256']==b['project_sha256'] and set(a['inputs'])==set(b['inputs'])
changed=[p for p in a['inputs'] if a['inputs'][p]['sha256']!=b['inputs'][p]['sha256']]
assert changed==['pitch_mod.v'],changed
assert int(hierarchy['buffered'].get('Ssram','0'))>0,'no distributed RAM inferred'
assert a['metrics']['Logic']>b['metrics']['Logic'] and a['metrics']['BSRAM']==b['metrics']['BSRAM']
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
preserved=[]
for rel,h in up['files'].items():
    if Path(rel).parts[0] in ('engine','rtl') and rel!='engine/src/pitch_mod.v':
        assert sha(R/rel)==h,rel;preserved.append(rel)
result=dict(status='PASS same-project full logical probe synthesis; no PnR or board qualification',
    before=a['metrics'],after=b['metrics'],delta={k:b['metrics'][k]-a['metrics'][k] for k in a['metrics']},
    logic_spare=20736-b['metrics']['Logic'],bsram_spare=46-b['metrics']['BSRAM'],pitch_hierarchy=hierarchy,
    changed=changed,preserved_upstream_files=preserved,selected_builds=folders,
    not_accepted={'synthesis_buffered_bank_v1':'pre-declaration repair candidate; not current input identity',
                  'synthesis_buffered_bank_v2':'system disk full; incomplete run record'},
    full_pnr=False,hardware_tested=False,
    inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',R/'synthesize.py',R/'upstream.json']+
        [R/folder/name for folder in folders.values() for name in ('run.json','impl/gwsynthesis/probe_syn_rsc.xml','impl/gwsynthesis/probe_syn.rpt.html')]})
assert result['logic_spare']>=0 and result['bsram_spare']>=0
(E/'resource.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','pitch_hierarchy','preserved_upstream_files')}))
