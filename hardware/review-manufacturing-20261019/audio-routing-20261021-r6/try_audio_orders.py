import subprocess,sys,json
from pathlib import Path
b=Path(__file__).resolve().parent
orders=['BCK,DIN,LRCK','DIN,BCK,LRCK','BCK,LRCK,DIN','DIN,LRCK,BCK','LRCK,BCK,DIN']
for i,order in enumerate(orders,1):
 out='order-'+str(i)+'-'+order.lower().replace(',','-')
 print('TRY_ORDER',order,flush=True)
 subprocess.run([sys.executable,'-u',str(b/'plan_audio_order.py'),'--order',order,'--output',out],check=True)
 p=json.loads((b/out/'plan.json').read_text())
 if len(p['routes'])==3 and p['batch_final_geometry_pass']:
  (b/'SELECTED-OFFLINE-AUDIO-PLAN.json').write_text(json.dumps(dict(plan_file=str((b/out/'plan.json').resolve()),order=order,source_pcb_sha256=p['native_pcb_sha256'],requires_native_reference_and_full_drc=True),indent=2));print('SELECTED',out,flush=True);break
