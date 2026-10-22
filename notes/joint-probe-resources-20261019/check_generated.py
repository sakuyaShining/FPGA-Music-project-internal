from pathlib import Path
import hashlib,json,subprocess,sys
P=Path(__file__).resolve().parents[2];R=P/'experiments/joint_probe_resources_20261019'
names=['rtl/joint_timing_top.v','constraints/sdram_board.cst','constraints/sdram_board.sdc','reference/stress.sdc','project/scan-map.json']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={n:sha(R/n) for n in names}
out=subprocess.run([sys.executable,str(R/'prepare_probe.py')],capture_output=True,text=True,encoding='utf-8')
assert out.returncode==0,out.stdout+out.stderr
assert before=={n:sha(R/n) for n in names},'generated output drift'
files=[Path(__file__).resolve(),R/'prepare_probe.py',R/'common.py',R/'upstream.json',R/'reference/clock-wrapper.v',R/'rtl/sdram_stream_probe.v']
(R/'evidence/generated-identity.json').write_text(json.dumps(dict(status='PASS unchanged generated outputs',outputs=before,inputs={str(p.relative_to(P)):sha(p) for p in files}),indent=2),encoding='utf-8')
print(out.stdout.strip());print('PASS generated output identities unchanged')
