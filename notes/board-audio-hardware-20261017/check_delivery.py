"""Read-only current hardware handoff check; never contacts the board."""
from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/board_audio_20261017'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
d=read(N/'delivery.json');assert d['hardware_tested'] and d['fpga_programmed'] and d['programming_operation']==2 and not d['flash_read_or_written']
assert sha(R/'delivery.json')==d['preparation_delivery_sha256']
old=read(R/'delivery.json');count=0
for group in ('source_files','evidence'):
    for rel,digest in old[group].items():assert sha(R/rel)==digest,('preparation',rel);count+=1
for rel,digest in d['files'].items():assert sha(N/rel)==digest,('hardware',rel);count+=1
for rel,digest in d['current_document_hashes'].items():assert sha(P/rel)==digest,('current-doc',rel);count+=1
assert sha(P/d['preflight_script']['path'])==d['preflight_script']['sha256']
S=P/d['session'];pre=read(S/'preflight.json')
assert sha(S/'before-hardware.zip')==pre['backup_zip_sha256']
with zipfile.ZipFile(S/'before-hardware.zip') as z:
    assert z.testzip() is None
    for rel,digest in read(S/'backup-manifest.json').items():assert hashlib.sha256(z.read(rel)).hexdigest()==digest
package=read(N/'package/manifest.json');assert package['reset_button']=='S2 / FPGA pin87 / active high'
for rel,digest in package['files'].items():assert sha(N/'package'/rel)==digest
assert package['files']['board-audio-sram.fs']==sha(R/'package/board-audio-sram.fs')
assert package['files']['board_check.py']==sha(R/'package/board_check.py')
for i in range(1,7):
    c=read(S/('case'+str(i))/'result.json');assert c['status'].startswith('PASS')
    assert c['after']['active']==0 and not c['status_after']['armed'] and not c['status_after']['fault']
    assert len((S/('case'+str(i))/'capture-s24le.bin').read_bytes())==2048*3
reset=read(S/'physical-reset-s2/result.json');assert reset['status'].startswith('PASS') and reset['post_reset_audio']['peak']==0
assert read(S/'after-user-reset/result.json')['status']=='FAIL'
assert read(S/'post-reset-case1/result.json')['status'].startswith('PASS')
assert not d['final_status']['armed'] and not d['final_status']['running'] and not d['final_status']['bound'] and not d['final_status']['fault'] and d['final_snapshot']['active']==0
print(json.dumps(dict(status='PASS hardware handoff identity/evidence only',checked_files=count,cases=6,reset='S2/87',flash=False,source_unchanged=True)))
