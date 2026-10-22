import json
from phase import ROOT,REPO,invoke
catalog={p['mpn']:p for p in json.loads((REPO/'hardware/pitch-sliders/selection-20261015/catalog-checked.json').read_text(encoding='utf-8'))}
result=invoke('switch-symbols',"return {tact:await eda.lib_Symbol.getDocumentSource(__CLI__.args.tact,__CLI__.args.lib),encoder:await eda.lib_Symbol.getDocumentSource(__CLI__.args.enc,__CLI__.args.lib)};",{'tact':catalog['TS-1187A-B-A-B']['symbolUuid'],'enc':catalog['EC11E15244B2']['symbolUuid'],'lib':catalog['EC11E15244B2']['libraryUuid']})
print(result['tact'])
