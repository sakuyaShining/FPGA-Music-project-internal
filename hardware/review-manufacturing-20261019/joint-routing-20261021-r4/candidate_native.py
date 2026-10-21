"""Native API wrapper bound only to the independent r4 comparison session."""
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(ROOT))
from native_review import call
info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf-8'));PROJECT=Path(info['candidate_project'])
SESSION=json.loads((BASE/'native-session.json').read_text(encoding='utf-8'))['sessionId']
def invoke(name,code,args=None,timeout=120):
 # No extension identity override and no external filesystem API.
 command=['invoke','--session',SESSION,'--args',json.dumps(args or {},ensure_ascii=True),'--timeout',str(min(1800000,int((timeout-10)*1000)))]
 if len(code)>12000:
  f=BASE/(name+'.js');f.write_text(code,encoding='utf-8');command+=['--code-file',str(f)]
 else:command+=['--code',code]
 return call('r4-candidate-'+name,command,timeout)
