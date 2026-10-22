"""Offline four-layer DSN calibration; no EDA/export APIs or PCB mutation."""
from pathlib import Path
import subprocess,hashlib,json,sys
OUT=Path(__file__).resolve().parent
jar=Path('D:/FPGA-Project/codex-tools/freerouting/freerouting-2.5.0.jar')
assert hashlib.sha256(jar.read_bytes()).hexdigest()=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
text='''(pcb "four-layer-calibration"
 (parser (string_quote ") (space_in_quoted_tokens on))
 (resolution mil 1000) (unit mil)
 (structure
  (layer TopLayer (type signal) (property (index 0)))
  (layer Inner15 (type signal) (property (index 1)))
  (layer Inner16 (type signal) (property (index 2)))
  (layer BottomLayer (type signal) (property (index 3)))
  (boundary (rect pcb 0 0 1000 1000))
  (via V24)
  (rule (width 6) (clearance 6.5))
 )
 (placement (component BOARD (place u1 0 0 front 0)))
 (library
  (image BOARD (pin PA A 200 300) (pin PB B 800 700))
  (padstack PA (shape (polygon TopLayer 0 -10 -20 10 -15 8 20 -10 10)) (attach off))
  (padstack PB (shape (rect Inner16 -30 -10 30 10)) (attach off))
  (padstack V24 (shape (circle TopLayer 24)) (shape (circle Inner15 24)) (shape (circle Inner16 24)) (shape (circle BottomLayer 24)) (attach off))
 )
 (network (net CAL (pins u1-A u1-B)) (class CAL CAL (circuit (use_via V24)) (rule (width 6) (clearance 6.5))))
 (wiring)
)'''
(OUT/'calibration.dsn').write_text(text,encoding='utf-8')
args=['java','-Xmx512m','-jar',str(jar),'-de',str(OUT/'calibration.dsn'),'-do',str(OUT/'calibration.ses'),
      '--router.autorouter.max_passes=4','--router.optimizer.enabled=false','--router.fanout.enabled=false',
      '--router.layers.routable=true,false,true,false','--router.job_timeout=00:00:30',
      '--router.automatic_neckdown=false','--router.strict_drc=true','-da','--gui.enabled=false',
      '--api_server.enabled=false','--logging.file.enabled=false',
      '--user_data_path='+str(OUT/'runtime-calibration')]
(OUT/'calibration-args.json').write_text(json.dumps(args,indent=2),encoding='utf-8')
with (OUT/'calibration.log').open('w',encoding='utf-8') as log:
    result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=60)
print('CALIBRATION',result.returncode,(OUT/'calibration.ses').exists(),flush=True)
print((OUT/'calibration.log').read_text(encoding='utf-8')[-9000:],flush=True)
