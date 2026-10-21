"""One bounded mature-router comparison; never auto-import or restart."""
from pathlib import Path
import sys,json,subprocess,hashlib
OUT=Path(__file__).resolve().parent
data=json.loads((OUT/'exchange-audit.json').read_text(encoding='utf-8'))
assert json.loads((OUT/'calibration-result.json').read_text(encoding='utf-8'))['passed']
jar=Path('D:/FPGA-Project/codex-tools/freerouting/freerouting-2.5.0.jar')
assert hashlib.sha256(jar.read_bytes()).hexdigest()=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
assert hashlib.sha256((OUT/'input.dsn').read_bytes()).hexdigest()==data['dsn_sha256']
assert not (OUT/'result.ses').exists(), 'Do not restart a completed comparison'
args=['java','-Xmx1g','-jar',str(jar),'-de',str(OUT/'input.dsn'),'-do',str(OUT/'result.ses'),
      '--router.autorouter.max_passes=8','--router.optimizer.enabled=true','--router.max_threads=2',
      '--router.fanout.enabled=false','--router.layers.routable=true,false,true,false',
      '--router.automatic_neckdown=false','--router.strict_drc=true','--router.job_timeout=00:02:00',
      '--router.autorouter.ignore_net_classes='+','.join(n for n in data['allnets'] if n not in data['selected']),
      '--router.result_json='+str(OUT/'result.json'),'-da','--gui.enabled=false','--api_server.enabled=false',
      '--logging.file.enabled=false','--user_data_path='+str(OUT/'runtime-route')]
audit=dict(source_pcb_sha256=data['source_pcb_sha256'],dsn_sha256=data['dsn_sha256'],args=args,native_imported=False,state='starting')
(OUT/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
with (OUT/'run.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
    audit.update(pid=process.pid,state='running');(OUT/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('RUNNING PID',process.pid,flush=True)
    try:code=process.wait(timeout=170)
    except subprocess.TimeoutExpired:
        process.terminate();code=process.wait(timeout=15);audit['watchdog_terminated']=True
audit.update(exit_code=code,ses_exists=(OUT/'result.ses').exists(),state='terminal')
(OUT/'attempt.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('TERMINAL',code,audit['ses_exists'],flush=True)
