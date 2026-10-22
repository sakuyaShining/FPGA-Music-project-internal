"""Add selected runtime/source assets missed by the initial extension list."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
from preserve_workspaces_20261022 import git,ENV,scan,stable_read,ASSET_EXTS
from finalize_raw_snapshots_20261022 import RUN

def main():
    index=RUN/'snapshots.json';records=json.loads(index.read_text(encoding='utf-8'))
    for r in records:
        if r.get('assets_reviewed'):continue
        stage=RUN/r['id'];mp=stage/r['manifest'];m=json.loads(mp.read_text(encoding='utf-8'))
        found,_=scan(Path(r['root']),{},r['parent'] is None)
        adds={n:p for n,p in found.items() if n not in m['files'] and p.suffix.lower() in ASSET_EXTS}
        entries=[];paths=[]
        for n,p in sorted(adds.items()):
            b,s=stable_read(p)
            if len(b)>95_000_000:raise ValueError('Oversize asset: '+str(p))
            dest=stage/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(b).digest():raise ValueError('Moving asset: '+n)
            m['files'][n]=dict(stored_path=n,codec='raw',bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),lf_sha256=hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest(),mtime_ns=s.st_mtime_ns)
            entries.append(n);paths.append(dest)
        if adds:
            m['asset_supplement_at']=datetime.now(timezone.utc).isoformat();m['asset_supplement_paths']=sorted(adds)
            mp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            entries.append(r['manifest']);paths.append(mp)
            oids=git('hash-object','--no-filters','-w','--stdin-paths',data=('\n'.join(str(p) for p in paths)+'\n').encode()).decode().splitlines()
            env=dict(ENV,GIT_INDEX_FILE=str(RUN/(r['id']+'-assets.index')))
            git('read-tree',r['commit'],env=env)
            git('update-index','-z','--index-info',env=env,data=b''.join(('100644 '+o+'\t'+n+'\0').encode('utf-8') for n,o in zip(entries,oids)))
            tree=git('write-tree',env=env).decode().strip();old=r['commit']
            r['commit']=git('commit-tree',tree,'-p',old,data=b'Preserve runtime fonts, UI assets and additional source/evidence inputs\n').decode().strip()
            git('update-ref','refs/heads/'+r['branch'],r['commit'],old)
            r['previous_raw_commit']=old;r['files']=len(m['files']);r['bytes']=sum(v['bytes'] for v in m['files'].values())
        r['assets_reviewed']=True;r['additional_assets']=len(adds)
        print('ASSETS '+r['id']+' '+str(len(adds)),flush=True)
    index.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
