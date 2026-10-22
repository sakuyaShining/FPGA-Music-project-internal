"""Append exact-byte corrections to draft snapshots, before final sealing.

Uses only already captured staging copies. Does not reread live workspaces,
rewrite old commits, force-push, or change any worktree index.
"""
import os,json,subprocess,hashlib,gzip
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from preserve_workspaces_20261022 import git,ENV

RUN=Path('D:/FPGA-Project/codex-builds/project-management-20261022')

def finalize(r):
    if r.get('exact_bytes_finalized'):return r
    stage=RUN/r['id'];m=json.loads((stage/r['manifest']).read_text(encoding='utf-8'))
    entries=[];paths=[]
    for rel,v in m['files'].items():
        p=stage/v['stored_path'];b=p.read_bytes();raw=gzip.decompress(b) if v['codec']=='gzip' else b
        if len(raw)!=v['bytes'] or hashlib.sha256(raw).hexdigest()!=v['sha256']:raise ValueError('Staging mismatch: '+r['id']+'/'+rel)
        entries.append(v['stored_path']);paths.append(p)
    entries.append(r['manifest']);paths.append(stage/r['manifest'])
    oids=git('hash-object','--no-filters','-w','--stdin-paths',data=('\n'.join(str(p) for p in paths)+'\n').encode()).decode().splitlines()
    assert len(oids)==len(entries)
    env=dict(ENV,GIT_INDEX_FILE=str(RUN/(r['id']+'-raw.index')))
    git('read-tree',r['commit'],env=env)
    modes={}
    for row in git('ls-tree','-r','-z',r['commit']).split(b'\0'):
        if row:
            meta,name=row.split(b'\t',1);modes[name.decode('utf-8')]=meta.split()[0].decode()
    git('update-index','-z','--index-info',env=env,data=b''.join((modes.get(n,'100644')+' '+o+'\t'+n+'\0').encode('utf-8') for n,o in zip(entries,oids)))
    tree=git('write-tree',env=env).decode().strip()
    old=r['commit'];new=git('commit-tree',tree,'-p',old,data=b'Finalize captured raw bytes without Git EOL filters; preserve previous draft history\n').decode().strip()
    git('update-ref','refs/heads/'+r['branch'],new,old)
    return dict(r,commit=new,previous_draft_commit=old,exact_bytes_finalized=True)

def main():
    p=RUN/'snapshots.json';records=json.loads(p.read_text(encoding='utf-8'));results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(finalize,records):
            results.append(r)
            print('FINALIZED '+r['id']+' '+r['commit'][:12],flush=True)
    p.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
