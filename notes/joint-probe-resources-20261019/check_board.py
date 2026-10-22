from pathlib import Path
import json,subprocess,sys,hashlib,datetime
P=Path(__file__).resolve().parents[2];R=P/'experiments/joint_probe_resources_20261019';E=R/'evidence'
script=P/'experiments/board_audio_20261017/board_check.py'
cmd=[sys.executable,str(script),'--port','COM6']
p=subprocess.run(cmd,cwd=P,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
log=p.stdout+p.stderr;(E/'board-status.log').write_text(log,encoding='utf-8')
d=dict(status='PASS read-only existing firmware status' if p.returncode==0 else 'NOT VERIFIED: read-only status failed',returncode=p.returncode,command=cmd,checked_at=datetime.datetime.now().astimezone().isoformat(),hardware_programmed=False,audio_triggered=False,flash_accessed=False,tf_accessed=False,inputs={str(script.relative_to(P)):hashlib.sha256(script.read_bytes()).hexdigest()})
if p.returncode==0:
    d['response']=json.loads(p.stdout)
    assert d['response']['status']['case']==76,d
(E/'board-status.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
print(json.dumps(d,ensure_ascii=True))
