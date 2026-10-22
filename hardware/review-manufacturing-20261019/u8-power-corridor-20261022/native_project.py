"""Native calls bound only to the R21 isolated recovery project."""
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(ROOT))
from native_review import call
info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf8'))
PROJECT=Path(info['candidate_project'])
SESSION=json.loads((BASE/'native-session.json').read_text(encoding='utf8'))['sessionId']
def invoke(name,code,args=None,timeout=120):
    p=BASE/(name+'.js');p.write_text(code,encoding='utf8')
    return call('u8-native-'+name,['invoke','--session',SESSION,'--code-file',str(p),'--args',json.dumps(args or {},ensure_ascii=True),'--timeout',str(int((timeout-10)*1000))],timeout)
