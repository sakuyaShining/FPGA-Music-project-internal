"""Read-only EasyEDA exact-part lookup with a separate evidence directory."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'notes/hardware-selection-resume-20261015'))
import cli_runner
cli_runner.ROOT=ROOT

if sys.argv[1]=='open':
    path='C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015/FPGA-Music-Slider-Prototype-20261015.eprj3'
    print(json.dumps(cli_runner.call('open',['open','--path',path,'--headless','true'],90)))
else:
    session=json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
    if sys.argv[1]=='close':
        print(json.dumps(cli_runner.call('close',['session','close','--session',session,'--destroy'])))
    else:
        code="""const library=await eda.lib_LibrariesList.getSystemLibraryUuid();const out={library,queries:{}};
for(const q of __CLI__.args.queries)out.queries[q]=await eda.lib_Device.search(q,library,undefined,undefined,12,1);
return out;"""
        result=cli_runner.call('protection-and-module-library',['invoke','--session',session,'--ext-uuid','eda','--code',code,
            '--args',json.dumps({'queries':['TPD1E01B04DPYR-TP','TPD1E01B04DPYR','TPD1E05U06DYA','PESD3V3U1UL,315(ES)','3.5inch RPi LCD (F)']}),'--timeout','60000'],75)
        for q,items in result['queries'].items():
            print(json.dumps({'query':q,'matches':[{k:x.get(k) for k in ('manufacturer','manufacturerId','supplierId','footprintName','uuid','libraryUuid')} for x in items]},ensure_ascii=True))
