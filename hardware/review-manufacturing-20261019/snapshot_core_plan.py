"""Copy one complete JSON planning save while the offline planner continues."""
import hashlib
import json
import sys
from native_review import ROOT
label=sys.argv[1];assert label.replace('-','').isalnum()
data=json.loads((ROOT/'grid-plan-core-fresh.json').read_text(encoding='utf-8'))
assert len(data['routes'])>=18 and data['estimated_remaining_connection_objects']<=119
assert hashlib.sha256((ROOT/data['source_file']).read_bytes()).hexdigest()==data['source_sha256']
path=ROOT/f'grid-plan-core-{label}.json';assert not path.exists()
path.write_text(json.dumps(data,indent=2),encoding='utf-8')
print('SAVED',path,'completed nets',len(data['routes']),'estimated unconnected',data['estimated_remaining_connection_objects'],flush=True)
