import json
from native_review import ROOT, invoke

code="""const n=await eda.sch_ManufactureData.getNetlistFile('dual-screen-review','Protel2');if(!n)throw new Error('No netlist');
const b=await eda.sch_ManufactureData.getBomFile('dual-screen-review','csv');if(!b)throw new Error('No BOM');
return {netlist:await n.text(),bomBytes:Array.from(new Uint8Array(await b.arrayBuffer())),drc:await eda.sch_Drc.check(true,false,true)};"""
v=invoke('native-text-exports',code,timeout=120)
(ROOT/'native-protel.net').write_text(v['netlist'],encoding='utf-8')
raw=bytes(v['bomBytes']);(ROOT/'native-bom.raw').write_bytes(raw)
encoding='utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig'
(ROOT/'native-bom.tsv').write_text(raw.decode(encoding),encoding='utf-8')
(ROOT/'native-drc.json').write_text(json.dumps(v['drc'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('netlist',len(v['netlist']),'BOM',len(raw),encoding,'DRC',v['drc'])
