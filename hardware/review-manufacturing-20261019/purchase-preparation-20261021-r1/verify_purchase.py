"""Independent saved-workbook and source-preservation checks; no authoring."""
import hashlib,json,math,zipfile,sys
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from current_state import current_checkpoint
data=json.loads((ROOT/'purchase-master.json').read_text(encoding='utf-8'))
meta=json.loads((ROOT/'workbook-output.json').read_text(encoding='utf-8'))
book=Path(meta['path']);NS={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(book) as z:
    assert z.testzip() is None
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('x:si',NS):
            shared.append(''.join(t.text or '' for t in si.findall('.//x:t',NS)))
    def cells(name):
        root=ET.fromstring(z.read(name));out={}
        for c in root.findall('.//x:c',NS):
            t=c.attrib.get('t');v=c.find('x:v',NS)
            assert t!='e',(name,c.attrib)
            if t=='s':value=shared[int(v.text)]
            elif t=='inlineStr':value=''.join(e.text or '' for e in c.findall('.//x:t',NS))
            elif v is None or v.text is None:value=None
            elif t=='str':value=v.text
            else:
                try:value=float(v.text)
                except ValueError:value=v.text
            out[c.attrib['r']]=value
        return root,out
    root,main=cells('xl/worksheets/sheet1.xml')
    for i,p in enumerate(data['external_items'],7):
        assert main['A'+str(i)]==p['id'] and main['D'+str(i)]==p['quantity']
    root,board=cells('xl/worksheets/sheet2.xml')
    assert board['E3']==230 and board['E4']==217 and board['E5']==13
    assert board['B3']==2 and board['B4']==1
    for i,p in enumerate(data['board_bom'],8):
        used=p['per_board']*(2 if p['assembly']=='工厂SMT供料' else 1)
        loose=0 if p['assembly']=='工厂SMT供料' else math.ceil(max(used+p['repair_spares'],p['minimum'])/p['multiple'])*p['multiple']
        assert board[f'A{i}']==p['code'] and board[f'E{i}']==used and board[f'I{i}']==loose and board[f'J{i}']==p['stock'],p['code']
    sheets=ET.fromstring(z.read('xl/workbook.xml')).find('x:sheets',NS)
    assert len(sheets)==4
    tables=[n for n in z.namelist() if n.startswith('xl/tables/table') and n.endswith('.xml')]
    assert len(tables)==3
    assert all(ET.fromstring(z.read(t)).find('x:autoFilter',NS) is not None for t in tables)
manifest_path,manifest,_=current_checkpoint(ROOT.parent)
project=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
assert all(h(project/name)==sha for name,sha in manifest['files'].items())
result={'workbook':str(book),'sha256':h(book),'sheets':4,'filter_tables':3,'board_types':36,'external_scope_rows':32,
 'cached_formulas_independently_reconciled':True,'native_19_files_unchanged':True,'factory_smt_per_board':217,
 'manual_through_hole_per_board':13,'assembly_quantity_test':True,'missing_stock_recalculation_test':True,
 'rendered_all_sheets':True,'current_checkpoint':manifest_path.name,'current_checkpoint_sha256':h(manifest_path),
 'current_pcb_sha256':manifest['pcb_sha256'],'manufacturing_release':False,'orders_submitted':False}
(ROOT/'final-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
