"""Check preserved versions and restore their selected inputs from Git.

This checks identity and recoverability, never product acceptance.
Requires Python 3.8+ and Git; does not use the original workspace paths.
"""
from pathlib import Path, PurePosixPath
import argparse, gzip, hashlib, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]

def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])

def safe_relative(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe relative path: '+name)
    return p

class Blobs:
    def __init__(self):
        self.proc=subprocess.Popen(['git','-C',str(ROOT),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    def read(self,oid):
        self.proc.stdin.write((oid+'\n').encode());self.proc.stdin.flush()
        header=self.proc.stdout.readline().decode().split()
        if len(header)!=3 or header[1]!='blob':raise ValueError('Missing blob: '+oid)
        data=self.proc.stdout.read(int(header[2]))
        if len(data)!=int(header[2]) or self.proc.stdout.read(1)!=b'\n':raise ValueError('Truncated blob: '+oid)
        return data
    def close(self):
        self.proc.stdin.close();self.proc.stdout.close();self.proc.wait()

def tree(commit):
    out={}
    for row in git('ls-tree','-r','-z',commit).split(b'\0'):
        if row:
            meta,path=row.split(b'\t',1);mode,kind,oid=meta.split()
            if kind==b'blob':out[path.decode('utf-8')]=oid.decode()
    return out

def check(full=False,remote=False,fresh=False):
    registry=json.loads((ROOT/'project/versions/workspace-preservation-20261022.json').read_text(encoding='utf-8'))
    state=json.loads((ROOT/'project/state.json').read_text(encoding='utf-8'))
    required=['README.md','AGENTS.md','project/CURRENT.md','project/AGENT-START.md','project/handoff.json','project/NEXT-AGENT-PROMPT.md','project/state.json','project/catalog.json','project/dependencies.json','project/versions/workspace-preservation-20261022.json','docs/00-协作/AGENT-BOARD.md','tools/scripts/project_control.py']
    tracked=set(git('ls-files','-z').decode('utf-8').split('\0'))
    errors=['entry is absent or untracked: '+p for p in required if not (ROOT/p).is_file() or p not in tracked]
    if fresh:
        if git('diff','HEAD','--','project/handoff.json','project/CURRENT.md','project/state.json').strip():
            errors.append('Unpublished entry changes: commit and synchronize the handoff before passing it to another agent')
        handoff=json.loads((ROOT/'project/handoff.json').read_text(encoding='utf-8'))
        lines=git('ls-remote','--heads',registry['remote_url'],'refs/heads/'+handoff['entry_branch']).decode().splitlines()
        if len(lines)!=1:errors.append('Current management entry branch is unavailable')
        else:
            latest=lines[0].split()[0]
            p=subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',latest,'HEAD'],capture_output=True)
            if p.returncode:errors.append('STALE ENTRY: fetch and read the current management branch before implementation')
    dep=json.loads((ROOT/'project/dependencies.json').read_text(encoding='utf-8'))
    for archive in [dep['archive']]+dep.get('additional_archives',[]):
        ap=ROOT/archive['path']
        if archive['path'] not in tracked or not ap.is_file() or hashlib.sha256(ap.read_bytes()).hexdigest()!=archive['sha256']:
            errors.append('Registered archive is absent, untracked or modified: '+archive['path'])
    if remote:
        live={line.split()[1]:line.split()[0] for line in git('ls-remote','--heads',registry['remote_url']).decode().splitlines()}
        for r in registry['snapshots']:
            if live.get('refs/heads/'+r['branch'])!=r['commit']:errors.append('Remote checkpoint mismatch: '+r['id'])
    ids=set();cache={};files=0;reader=Blobs()
    try:
        for record in registry['snapshots']:
            ident=record['id'];ids.add(ident);commit=record['commit'];paths=tree(commit)
            mf=record['manifest']
            if mf not in paths:errors.append(ident+': missing manifest');continue
            manifest=json.loads(reader.read(paths[mf]))
            if manifest['id']!=ident:errors.append(ident+': manifest ID mismatch')
            for rel,item in manifest['files'].items():
                safe_relative(rel);stored=item['stored_path'];safe_relative(stored)
                oid=paths.get(stored)
                if not oid:errors.append(ident+': missing input '+stored);continue
                files+=1
                if full:
                    key=(oid,item['codec'])
                    if key not in cache:
                        data=reader.read(oid)
                        if item['codec']=='gzip':data=gzip.decompress(data)
                        elif item['codec']!='raw':raise ValueError('Unknown codec')
                        cache[key]=(len(data),hashlib.sha256(data).hexdigest())
                    if cache[key]!=(item['bytes'],item['sha256']):errors.append(ident+': identity mismatch '+rel)
            print('CHECK '+ident+' '+commit[:12]+' inputs='+str(len(manifest['files'])),flush=True)
        for label,profile in state['profiles'].items():
            if profile.get('snapshot') and profile['snapshot'] not in ids:errors.append(label+': unregistered snapshot')
            if profile.get('role')=='probe' and profile.get('product_accepted'):errors.append(label+': probe marked accepted')
    finally:reader.close()
    result=dict(status='FAIL' if errors else 'PASS',scope='Full captured content hashes' if full else 'Entry tracking and captured file availability',snapshots=len(ids),inputs=files,unique_verified_blobs=len(cache),remote_checked_now=remote,entry_freshness_checked=fresh,errors=errors,product_acceptance=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if errors else 0

def restore(ident,output,with_delta=False):
    registry=json.loads((ROOT/'project/versions/workspace-preservation-20261022.json').read_text(encoding='utf-8'))
    record=next(r for r in registry['snapshots'] if r['id']==ident)
    if with_delta and ident!='m1-work':raise ValueError('Source delta overlay is allowed only for isolated M1 source review; no automatic hardware/native replay')
    output=output.resolve()
    if output.exists():raise ValueError('Refuse to overwrite an existing path: '+str(output))
    paths=tree(record['commit']);reader=Blobs()
    try:
        manifest=json.loads(reader.read(paths[record['manifest']]))
        # Validate all path names before creating the destination.
        for rel,item in manifest['files'].items():safe_relative(rel);safe_relative(item['stored_path'])
        output.mkdir(parents=True)
        restored=0;skipped=[]
        for rel,item in manifest['files'].items():
            if with_delta and not (rel.startswith(('engine/','rtl/','constraints/','tb/','reference/')) or ('/' not in rel and Path(rel).suffix in {'.py','.v','.vh','.hex','.md'})):
                skipped.append(rel);continue
            data=reader.read(paths[item['stored_path']])
            if item['codec']=='gzip':data=gzip.decompress(data)
            elif item['codec']!='raw':raise ValueError('Unknown codec')
            if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Hash mismatch: '+rel)
            dest=output/Path(*safe_relative(rel).parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            restored+=1
        if with_delta:
            import zipfile
            delta=json.loads((ROOT/'project/versions/post-capture-source-drift-20261022.json').read_text(encoding='utf-8'))
            ap=ROOT/delta['preserved_delta_archive']
            if hashlib.sha256(ap.read_bytes()).hexdigest()!=delta['preserved_delta_archive_sha256']:raise ValueError('Source delta archive hash mismatch')
            applied=[]
            with zipfile.ZipFile(ap) as z:
                dm=json.loads(z.read('DELTA-MANIFEST.json'))
                for name,item in dm['files'].items():
                    if not name.startswith(ident+'/'):continue
                    rel=item['source_relative_path'];safe_relative(rel)
                    if item['base_snapshot']!=record['commit'] or rel not in manifest['files']:raise ValueError('Delta base/input mismatch')
                    dest=output/Path(*safe_relative(rel).parts)
                    if hashlib.sha256(dest.read_bytes()).hexdigest()!=manifest['files'][rel]['sha256']:raise ValueError('Delta preimage mismatch')
                    data=z.read(name)
                    if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Delta source hash mismatch')
                    dest.write_bytes(data);applied.append(rel)
            if not applied:raise ValueError('No registered M1 source delta')
            effective={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for prefix in ('engine/src','engine/rtl','rtl','constraints') for p in (output/prefix).iterdir() if p.is_file() and p.suffix in {'.v','.sv','.vh','.hex','.cst','.sdc'}}
            record=dict(record,unvalidated_source_delta=dict(archive=delta['preserved_delta_archive'],captured_at=dm['captured_at'],files=applied,validation_inherited=False),effective_source_inputs=effective,restore_scope='Source/context only; historical evidence, old runtime markers and derived fixture copies omitted',omitted_historical_paths=skipped)
            (output/'AGENTS.md').write_text('# Restored M1 source entry\n\nRead PRESERVATION-ORIGIN.json first. This is the registered M1 checkpoint plus an unvalidated source delta. Existing README, reports and source-identity files are historical; they do not qualify this restored source. Do not run inherited absolute-path prepare/build scripts. Use a named task worktree and the current management project/AGENT-START.md before editing; preserve portable-package golden tests. Never program hardware or replay native CAD operations.\n',encoding='utf-8')
        (output/'PRESERVATION-ORIGIN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(status='RESTORED',id=ident,files=restored,source_delta=with_delta,output=str(output),product_acceptance=False),ensure_ascii=False))
    finally:reader.close()

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    c=sub.add_parser('check');c.add_argument('--full',action='store_true');c.add_argument('--remote',action='store_true',help='Read-only verification of actual remote branch commits');c.add_argument('--fresh-entry',action='store_true',help='Reject checkouts that do not contain the current published management entry')
    r=sub.add_parser('restore');r.add_argument('--snapshot',required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--with-source-delta',action='store_true')
    a=ap.parse_args()
    if a.command=='check':return check(a.full,a.remote,a.fresh_entry)
    restore(a.snapshot,a.output,a.with_source_delta);return 0

if __name__=='__main__':sys.exit(main())
