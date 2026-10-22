"""Read-only sourcing evidence; no engine, schematic, purchase or order edits."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EVIDENCE = ROOT / 'evidence'
EVIDENCE.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / 'notes/hardware-selection-resume-20261015'))
import cli_runner
cli_runner.ROOT = ROOT

def public_page(label, url):
    item = {'url': url, 'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            raw = response.read()
            item['http_status'] = response.status
        is_pdf = raw.startswith(b'%PDF-')
        (EVIDENCE / (label + ('.pdf' if is_pdf else '.html'))).write_bytes(raw)
        item['sha256'] = hashlib.sha256(raw).hexdigest()
        if is_pdf:
            item['status'] = 'pdf_downloaded_not_functionally_verified'
            return item
        html = raw.decode('utf-8')
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if match:
            data = json.loads(match[1])['props']['pageProps'].get('webData', {})
            product = data.get('productRecord', {})
            item.update(mpn=product.get('productModel'), lcsc=product.get('productCode'),
                        stock=product.get('stockNumber'), valid_stock=product.get('validStockNumber'),
                        minimum=product.get('minBuyNumber'), parameters=data.get('paramList'),
                        unit_price_cny=None, price_note='No verified unit/checkout price; package reference prices excluded.')
            (EVIDENCE / (label + '-public-data.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        item['status'] = 'public_page_read'
    except Exception as exc:
        item.update(status='not_verified', error=f'{type(exc).__name__}: {exc}')
    return item

def pages():
    targets = {
        'DFR0669-domestic': 'https://item.szlcsc.com/18770998.html',
        'LCKFB-2inch-domestic': 'https://item.szlcsc.com/56199684.html',
        'HS28B03A-international': 'https://www.lcsc.com/product-detail/C42432560.html',
        'DFR0669-manufacturer': 'https://wiki.dfrobot.com/dfr0669/',
        'HS28B03A-manual': 'https://atta.szlcsc.com/upload/public/pdf/source/20250102/A36DE46EC42CDC76F150F51E9212C5B9.pdf',
        'DFR0669-domestic-manufacturer': 'https://www.dfrobot.com.cn/goods-2877.html',
        'DFR0669-schematic': 'https://dfimg.dfrobot.com/wiki/21129/DFR0669_tft-touchscreen-display-module_schematics_v1.pdf',
        'GT911-module-datasheet': 'https://dfimg.dfrobot.com/wiki/21129/DFR0669_tft-touchscreen-display-module_datasheet_v1.pdf',
        'DFRobot-GDL-source': 'https://raw.githubusercontent.com/DFRobot/DFRobot_GDL/master/src/DFRobot_GDL.cpp',
        'DFRobot-GDL-header': 'https://raw.githubusercontent.com/DFRobot/DFRobot_GDL/master/src/DFRobot_GDL.h',
    }
    rows = []
    for label, url in targets.items():
        row = public_page(label, url)
        rows.append(dict(label=label, **row))
        (EVIDENCE / 'public-pages.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(rows[-1], ensure_ascii=True), flush=True)
        time.sleep(0.5)

def native_open():
    # Opening the existing owned prototype only for catalog reads. Never save/edit.
    project = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')
    hashes = {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in project.rglob('*') if p.is_file() and 'exports' not in p.parts}
    (EVIDENCE / 'project-before-readonly.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(json.dumps(cli_runner.call('sessions-before', ['session', 'list']), ensure_ascii=True))
    print(json.dumps(cli_runner.call('open-readonly', ['open', '--path', str(project/(project.name+'.eprj3')), '--headless', 'true'], 90), ensure_ascii=True))

def native_search():
    session = json.loads((EVIDENCE/'open-readonly.json').read_text(encoding='utf-8'))['value']['sessionId']
    code = """const result={project:await eda.dmt_Project.getCurrentProjectInfo(),library:await eda.lib_LibrariesList.getSystemLibraryUuid(),queries:{}};
for (const query of __CLI__.args.queries) {
 result.queries[query]=await eda.lib_Device.search(query,result.library,undefined,undefined,20,1);
}
return result;"""
    value=cli_runner.call('native-touch-system-library', ['invoke','--session',session,'--ext-uuid','eda','--code',code,
        '--args',json.dumps({'queries':['SN74LVC14ADR','DFR0669','HS28B03A','CTPH043','2.8inch Capacitive Touch LCD','LCKFB-st7789-2.0inch-screen','DFR1092']}), '--timeout','60000'],75)
    print(json.dumps(value, ensure_ascii=True))

def close():
    session = json.loads((EVIDENCE/'open-readonly.json').read_text(encoding='utf-8'))['value']['sessionId']
    print(json.dumps(cli_runner.call('close-owned', ['session','close','--session',session,'--destroy']), ensure_ascii=True))
    project = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')
    before=json.loads((EVIDENCE/'project-before-readonly.json').read_text(encoding='utf-8'))
    after={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in project.rglob('*') if p.is_file() and 'exports' not in p.parts}
    changed=[p for p in before if after.get(p)!=before[p]]
    result={'changed_files':changed,'added_files':[p for p in after if p not in before]}
    (EVIDENCE/'project-after-readonly.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    {'pages':pages,'open':native_open,'search':native_search,'close':close}[sys.argv[1]]()
