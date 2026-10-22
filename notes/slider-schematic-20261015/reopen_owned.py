import json
from phase import ROOT,PROJECT,call
sid=json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
print(call('closed-hung-owned',['session','close','--session',sid,'--destroy']))
print(call('open',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],90))
