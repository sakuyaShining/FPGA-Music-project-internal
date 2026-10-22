"""Export an actual native PCB and run local, bounded Java Freerouting trials.

Does not import a result or release manufacturing files. Each attempt keeps its
native DSN, sanitized DSN, exact arguments, stdout, and exit/result metadata.
The native exporter omits filled ground copper. Native DRC after import remains
the authority for connectivity and the current keepouts/ground geometry.
"""
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from native_review import ROOT, PROJECT, invoke
from sanitize_dsn import sanitize

DEST = Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
JAR = Path('D:/FPGA-Project/codex-tools/freerouting/freerouting-2.5.0.jar')
JAR_SHA = 'f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
POWER = {'5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3'}
ANALOG = {'DAC_CAPP','DAC_CAPM','DAC_VNEG','DAC_LDOO','DAC_XSMT','DAC_L_RAW','DAC_R_RAW','AUX_L','AUX_R'}

def run(stage, requested=None):
    assert hashlib.sha256(JAR.read_bytes()).hexdigest() == JAR_SHA
    design = json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
    nets = {n for p in design['parts'] for n in p['nets'].values() if n}
    mux = {n for n in nets if re.fullmatch(r'L[0-5]_M\d\d', n)}
    electrodes = {n for n in nets if re.fullmatch(r'L[0-5]_E\d\d', n)}
    timing = {f'RC{i}' for i in range(6)}
    selected = (set(requested) if requested is not None else mux if stage == 'mux' else ANALOG if stage == 'analog' else
                POWER if stage == 'power' else nets-POWER-ANALOG-mux-electrodes-timing-{'GND'}
                if stage == 'core' else nets if stage == 'all' else {stage})
    assert selected and selected <= nets
    name = stage+'-'+str(time.time_ns())
    out = DEST/'routing-work'/name
    out.mkdir(parents=True)
    export = PROJECT/'review-exports/v2'/('input-'+name+'.dsn')
    actual = invoke('offline-export-'+name, """
const f=await eda.pcb_ManufactureData.getDsnFile('routing-input');
if(!f)throw new Error('No DSN');if(!await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path,f,undefined,true))throw new Error('Export failed');
return {vias:(await eda.pcb_PrimitiveVia.getAll()).map(v=>({id:v.getState_PrimitiveId(),x:v.getState_X(),y:v.getState_Y()})),components:(await eda.pcb_PrimitiveComponent.getAll()).length};
""", {'path':export.as_posix()}, 180)
    assert actual['components'] == 230
    shutil.copy2(export, out/'native.dsn')
    source = export.read_text(encoding='utf-8')
    cleaned,sanitization = sanitize(source,actual['vias'],selected)
    (out/'input.dsn').write_text(cleaned, encoding='utf-8')
    args = ['java','-Xmx1g','-jar',str(JAR),'-de',str(out/'input.dsn'),'-do',str(out/'result.ses'),
            '--router.autorouter.max_passes=8','--router.fanout.enabled=false',
            '--router.optimizer.enabled=false','--router.job_timeout=00:08:00',
            '--router.autorouter.ignore_net_classes='+','.join(sorted(nets-selected)),
            '--router.result_json='+str(out/'result.json'),'-da','--gui.enabled=false',
            '--api_server.enabled=false','--logging.file.enabled=false',
            '--user_data_path=D:/FPGA-Project/codex-tools/freerouting/'+name]
    meta = {'stage':stage,'requested_nets':sorted(selected),'sanitization':sanitization,
            'preserves_real_native_vias':True,'components':actual['components'],'args':args,
            'native_ground_copper_exported':False,'native_import_performed':False,'fabrication_release':False}
    (out/'attempt.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print('ROUTING',len(selected),'nets in',out,flush=True)
    with (out/'run.log').open('w', encoding='utf-8') as log:
        r = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    meta['exit_code'] = r.returncode
    meta['ses_sha256'] = hashlib.sha256((out/'result.ses').read_bytes()).hexdigest() if (out/'result.ses').exists() else None
    (out/'attempt.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print({'stage':stage,'requested_nets':len(selected),'exit_code':r.returncode,'ses_saved':bool(meta['ses_sha256']),'out':str(out)},flush=True)
    return out

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv)>1 else 'mux')
