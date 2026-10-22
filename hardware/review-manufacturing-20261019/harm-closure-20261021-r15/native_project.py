"""Native wrapper bound to r15 HARM candidate, never r3/r4."""
import sys,json
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(ROOT));from native_review import call
info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf-8'));PROJECT=Path(info['candidate_project']);SESSION=json.loads((BASE/'native-session.json').read_text(encoding='utf-8'))['sessionId']
def invoke(name,code,args=None,timeout=120):
 cmd=['invoke','--session',SESSION,'--args',json.dumps(args or {},ensure_ascii=True),'--timeout',str(min(1800000,int((timeout-10)*1000)))]
 if len(code)>12000:
  p=BASE/(name+'.js');p.write_text(code,encoding='utf-8');cmd+=['--code-file',str(p)]
 else:cmd+=['--code',code]
 return call('r15-harm-'+name,cmd,timeout)
