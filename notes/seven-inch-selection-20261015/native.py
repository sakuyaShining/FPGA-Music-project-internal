"""Owned hidden EasyEDA session for read-only sourcing; retain all requests."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
E.mkdir(exist_ok=True)
sys.path.insert(0,str(HERE.parent/'hardware-selection-resume-20261015'))
import cli_runner
cli_runner.ROOT=HERE
PROJECT=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')

def hashes():
    return {p.relative_to(PROJECT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in PROJECT.rglob('*') if p.is_file() and 'exports' not in p.parts}

mode=sys.argv[1]
if mode=='open':
    (E/'before.json').write_text(json.dumps(hashes(),indent=2),encoding='utf-8')
    print(json.dumps(cli_runner.call('sessions-before',['session','list']),ensure_ascii=True))
    print(json.dumps(cli_runner.call('open-owned',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],90),ensure_ascii=True))
else:
    session=json.loads((E/'open-owned.json').read_text(encoding='utf-8'))['value']['sessionId']
    if mode=='close':
        print(json.dumps(cli_runner.call('close-owned',['session','close','--session',session,'--destroy']),ensure_ascii=True))
        before=json.loads((E/'before.json').read_text(encoding='utf-8'));after=hashes()
        record=dict(changed=[n for n,h in before.items() if after.get(n)!=h],added=[n for n in after if n not in before])
        (E/'after.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(record))
    else:
        groups={
            'screens':['SN74LVC14ADR','7inch','7寸','7.0','AT070','RA8875','SSD1963'],
            'audio':['PCM5122','PCM5102','PT8211','PCM5102APWR','CS4344','TM8211','MS4344'],
            'display-extra':['LT7680','LT7680A-R','LT7683','7inch HDMI LCD (C)','MRB7966','ER-TFTM070','SN74LV595APWR','SN74LVC595APW'],
            'followup':['LT7686','LT7381','SSP0700A','MSP7001'],
        }
        code='const library=await eda.lib_LibrariesList.getSystemLibraryUuid();const out={library,queries:{}};for(const q of __CLI__.args.queries)out.queries[q]=await eda.lib_Device.search(q,library,undefined,undefined,20,1);return out;'
        data=cli_runner.call('native-'+mode,['invoke','--session',session,'--ext-uuid','eda','--code',code,
            '--args',json.dumps(dict(queries=groups[mode]),ensure_ascii=False),'--timeout','60000'],75)
        for q,items in data['queries'].items():
            print(json.dumps(dict(query=q,matches=[{k:x.get(k) for k in ('manufacturer','manufacturerId','supplierId','footprintName','uuid','libraryUuid')} for x in items]),ensure_ascii=True))
