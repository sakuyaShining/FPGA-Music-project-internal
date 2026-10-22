"""One bounded negotiated route with neighbouring signal copper unlocked.

The current native PCB remains untouched. A complete recovered net set and
independent physical checks are mandatory before considering native import.
"""
from pathlib import Path
import sys,json,copy,hashlib,subprocess,importlib.util
B=Path(__file__).resolve().parent;R=B.parent;O=B/'global-bus-router';O.mkdir(exist_ok=True)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=read(R/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(cp['project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==cp['pcb_sha256']=='8b9b68a5f42a446b2c716e41d6693f480fb9c8048e6c1c7080b151244978aa19'
assert not (O/'attempt.json').exists(),'Read existing run; never duplicate it'
s=read(Path(cp['source_capture']));selected={'BUS_MOSI','BUS_SCK','TP_RESET_N','VIS_CS_N'}
work=copy.deepcopy(s);removed={k:[p for p in work[k] if p['net'] in selected] for k in ['lines','vias']}
for k in removed:work[k]=[p for p in work[k] if p['net'] not in selected]
(O/'working-capture.json').write_text(json.dumps(work),encoding='utf8');(O/'removed-copper.json').write_text(json.dumps(removed),encoding='utf8')
(O/'regional-edit-plan.json').write_text(json.dumps(dict(routing_nets=sorted(selected))),encoding='utf8')
spec=importlib.util.spec_from_file_location('bus_exchange',B/'exchange.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e);e.OUT=O;e.read=lambda:(cp,pcb,work);e.build()
data=read(O/'exchange-audit.json');jar=Path('D:/FPGA-Project/codex-tools/freerouting/freerouting-2.5.0.jar');assert sha(jar)=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
args=['java','-Xmx1500m','-jar',str(jar),'-de',str(O/'input.dsn'),'-do',str(O/'result.ses'),
 '--router.autorouter.max_passes=10','--router.optimizer.enabled=true','--router.max_threads=2',
 '--router.fanout.enabled=true','--router.layers.routable=true,false,true,false',
 '--router.automatic_neckdown=false','--router.strict_drc=true','--router.job_timeout=00:08:00',
 '--router.autorouter.ignore_net_classes='+','.join(n for n in data['allnets'] if n not in selected),
 '--router.result_json='+str(O/'result.json'),'-da','--gui.enabled=false','--api_server.enabled=false',
 '--logging.file.enabled=false','--user_data_path='+str(O/'runtime-route')]
audit=dict(source_pcb_sha256=cp['pcb_sha256'],dsn_sha256=sha(O/'input.dsn'),selected=sorted(selected),args=args,state='starting',native_imported=False)
with (O/'run.log').open('w',encoding='utf8') as f:
 p=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT);audit.update(pid=p.pid,state='running');(O/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf8');print('RUNNING',p.pid,flush=True)
 try:code=p.wait(timeout=520)
 except subprocess.TimeoutExpired:p.terminate();code=p.wait(timeout=20);audit['watchdog_terminated']=True
audit.update(state='terminal',exit_code=code,ses_exists=(O/'result.ses').exists(),source_unchanged=sha(pcb)==cp['pcb_sha256']);(O/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf8');print('TERMINAL',code,audit['ses_exists'],flush=True)
