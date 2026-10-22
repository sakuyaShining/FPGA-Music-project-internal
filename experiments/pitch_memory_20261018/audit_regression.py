"""Re-read functional evidence and bound its current source and complete traces."""
from common import *
evidence={};inputs=[]
for name in ('pitch-memory','engine-compatibility','enabled-compatibility','config-music','envelope-reference','phase-wrap'):
    p=E/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'))
    assert d['status'].startswith('PASS'),name
    for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
    evidence[name]=d['status'];inputs.append(p)
legacy=json.loads((E/'engine-compatibility.json').read_text(encoding='utf-8'))
enabled=json.loads((E/'enabled-compatibility.json').read_text(encoding='utf-8'))
counts={}
for prefix,record in (('',legacy),('enabled-',enabled)):
    for name,item in record['results'].items():
        trace=E/(('enabled-'+name) if prefix else (name+'-compat'));trace=trace.with_suffix('.tsv')
        assert sha(trace)==item['trace_sha256']==item['reference_sha256'],(prefix,name)
        # Disk-full writes once produced malformed lines despite passing in-memory assertions.
        with trace.open(encoding='utf-8') as f:
            i=0
            for i,line in enumerate(f,1):assert int(line.split()[0])==i,(trace.name,i)
        counts[trace.name]=i;inputs.append(trace)
for stem,record_name in (('config-music','config-music'),('envelope','envelope-reference')):
    p=E/(stem+'.tsv');d=json.loads((E/(record_name+'.json')).read_text(encoding='utf-8'))
    assert sha(p)==d['trace_sha256'];inputs.append(p)
result=dict(status='PASS scoped regression identities and complete historical PCM/I2S traces',
    checks=evidence,legacy_trace_cycles=counts,pitch_cycles=960000,
    faults=['lost-command-priority','leaked-reset-data'],pnr_tested=False,hardware_tested=False,
    inputs={p.relative_to(R).as_posix():sha(p) for p in inputs+[Path(__file__).resolve(),R/'common.py']})
(E/'regression-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
