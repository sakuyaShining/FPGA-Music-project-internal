"""Check preserved versions and restore their selected inputs from Git.

This checks identity and recoverability, never product acceptance.
Requires Python 3.8+ and Git; does not use the original workspace paths.
"""
from pathlib import Path, PurePosixPath
import argparse, gzip, hashlib, json, subprocess, sys
import design_governance as governance
import engineering

ROOT=Path(__file__).resolve().parents[2]
ENTRY_FILES=['.gitattributes','.github/workflows/project-entry.yml','README.md','AGENTS.md','project/CURRENT.md','project/AGENT-START.md',
    'project/handoff.json','project/NEXT-AGENT-PROMPT.md','project/state.json',
    'project/catalog.json','project/dependencies.json','project/DESIGN-CURRENT.md',
    'project/design-state.json','project/QUICKSTART.md','project/versions/design-decision-20261023.json',
    'project/versions/latest-design-inputs-20261023.json',
    'project/versions/workspace-preservation-20261022.json',
    'docs/00-协作/AGENT-BOARD.md','tools/scripts/project_control.py',
    'tools/scripts/design_governance.py','project/governance.json',
    'project/decisions.json','project/producers.json','project/MAINTAINING-MAIN.md',
    'project/ENGINEERING.md','project/COLLABORATION-CHECKPOINT-20261024.md',
    'project/versions/engineering-sources-20261023.json','tools/scripts/engineering.py']

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
    required=ENTRY_FILES
    tracked=set(git('ls-files','-z').decode('utf-8').split('\0'))
    errors=['entry is absent or untracked: '+p for p in required if not (ROOT/p).is_file() or p not in tracked]
    try:
        engineering.check(ROOT)
    except (OSError, ValueError) as error:
        errors.append('Engineering checkpoint: ' + str(error))
    errors.extend(governance.validate(ROOT))
    policy=governance.read_json(ROOT/'project/governance.json')
    for name in list(policy['controlled_files'])+[policy['review_record']]:
        if name not in tracked:errors.append('Governed review/evidence is untracked: '+name)
    if fresh:
        published=governance.published_entry(ROOT)
        if published['status']!='CURRENT_PUBLISHED_MAIN':
            errors.append('Published main: '+published['status']+'; '+published.get('reason',''))
        freshness=governance.status(ROOT)
        errors.extend(freshness['errors'])
    dep=json.loads((ROOT/'project/dependencies.json').read_text(encoding='utf-8'))
    for archive in [dep['archive']]+dep.get('additional_archives',[]):
        ap=ROOT/archive['path']
        if archive['path'] not in tracked or not ap.is_file() or hashlib.sha256(ap.read_bytes()).hexdigest()!=archive['sha256']:
            errors.append('Registered archive is absent, untracked or modified: '+archive['path'])
    design=json.loads((ROOT/'project/design-state.json').read_text(encoding='utf-8'))
    for name,expected in design['reviewed_design_sources'].items():
        safe_relative(name)
        if name not in tracked or not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            errors.append('Reviewed design source changed without updating design identity: '+name)
    current=json.loads((ROOT/design['current_inputs_manifest']).read_text(encoding='utf-8'))
    safe_relative(current['archive'])
    if hashlib.sha256((ROOT/current['archive']).read_bytes()).hexdigest()!=current['archive_sha256']:
        errors.append('Current input manifest archive identity mismatch')
    if full:
        import zipfile
        with zipfile.ZipFile(ROOT/current['archive']) as z:
            expected_members=set(current['files'])|{'CAPTURE-MANIFEST.json'}
            if set(z.namelist())!=expected_members or len(z.namelist())!=len(expected_members):
                errors.append('Current input archive member mismatch')
            inside=json.loads(z.read('CAPTURE-MANIFEST.json'))
            outside=dict(current);outside.pop('archive_sha256',None)
            if inside!=outside:errors.append('Current input archive manifest mismatch')
            for name,item in current['files'].items():
                safe_relative(name);data=z.read(name)
                if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
                    errors.append('Current input identity mismatch: '+name)
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
    result=dict(status='FAIL' if errors else 'PASS',scope='Full captured content hashes' if full else 'Entry tracking and captured file availability',snapshots=len(ids),inputs=files,unique_verified_blobs=len(cache),current_design=design['design_version'],recovery_archive_files=len(current['files']),recovery_captured_at=current['captured_at'],live_workspaces_checked=False,remote_checked_now=remote,entry_freshness_checked=fresh,published_authority='main',review_freshness=freshness['status'] if fresh else 'NOT_CHECKED',implementation_start_authorized=False,errors=errors,product_acceptance=False)
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


def get_latest(output):
    """Clone the published entry into a NEW directory, without touching a worktree."""
    output=output.resolve()
    if output.exists():raise ValueError('Refuse to overwrite an existing path: '+str(output))
    registry=json.loads((ROOT/'project/versions/workspace-preservation-20261022.json').read_text(encoding='utf-8'))
    subprocess.run(['git','clone','--origin','internal','--branch',governance.BRANCH,
                    '--no-single-branch',governance.REMOTE,str(output)],check=True)
    subprocess.run(['git','-C',str(output),'config','remote.pushDefault','internal'],check=True)
    subprocess.run(['git','-C',str(output),'config','push.default','simple'],check=True)
    subprocess.run([sys.executable,str(output/'tools/scripts/project_control.py'),'check',
                    '--full','--remote','--fresh-entry'],check=True)
    print('Read '+str(output/'project/DESIGN-CURRENT.md')+' before implementation.')


def restore_design(output,area):
    """Restore selected observed inputs, never apply CAD changes or program hardware."""
    import zipfile
    output=output.resolve()
    if output.exists():raise ValueError('Refuse to overwrite an existing path: '+str(output))
    design=json.loads((ROOT/'project/design-state.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/design['current_inputs_manifest']).read_text(encoding='utf-8'))
    archive=ROOT/manifest['archive']
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['archive_sha256']:
        raise ValueError('Observed input archive hash mismatch')
    prefix='fpga/' if area=='fpga' else 'hardware/'
    selected={n:i for n,i in manifest['files'].items() if n.startswith(prefix)}
    with zipfile.ZipFile(archive) as z:
        # Verify every selected member before creating any output files.
        data={}
        for name,item in selected.items():
            safe_relative(name);rel=name[len(prefix):];safe_relative(rel)
            raw=z.read(name)
            if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
                raise ValueError('Observed input hash mismatch: '+name)
            data[rel]=raw
        output.mkdir(parents=True)
        for rel,raw in data.items():
            p=output/Path(*safe_relative(rel).parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    provenance=dict(design_version=design['design_version'],captured_at=manifest['captured_at'],
                    archive=manifest['archive'],archive_sha256=manifest['archive_sha256'],area=area,
                    files={n[len(prefix):]:i for n,i in selected.items()},validation_inherited=False,
                    original_readmes_are_historical=True,product_accepted=False)
    (output/'PRESERVATION-ORIGIN.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'AGENTS.md').write_text('# Observed WIP recovery\n\nRead PRESERVATION-ORIGIN.json and the published project/DESIGN-CURRENT.md first. This is a selected source/context capture, not an accepted complete product. Original README, project/CURRENT and source-identity files are historical. Do not execute inherited absolute-path scripts, program hardware, replay CAD transactions, or overwrite another owner. Import chosen inputs into a named task branch, review dependencies, then validate that exact source. Hardware ZIPs are recovery context only, never a manufacturing release.\n',encoding='utf-8')
    print(json.dumps(dict(status='RESTORED',area=area,files=len(selected),output=str(output),validation_inherited=False)))

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    c=sub.add_parser('check');c.add_argument('--full',action='store_true');c.add_argument('--remote',action='store_true',help='Read-only verification of actual remote branch commits');c.add_argument('--fresh-entry',action='store_true',help='Reject checkouts that do not contain the current published management entry')
    r=sub.add_parser('restore');r.add_argument('--snapshot',required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--with-source-delta',action='store_true')
    l=sub.add_parser('get-latest',help='Clone and verify published entry into a NEW directory');l.add_argument('--output',type=Path,required=True)
    d=sub.add_parser('restore-design',help='Recover observed WIP inputs, without accepting or applying them');d.add_argument('--output',type=Path,required=True);d.add_argument('--area',choices=['fpga','hardware-context'],default='fpga')
    a=ap.parse_args()
    if a.command=='check':return check(a.full,a.remote,a.fresh_entry)
    if a.command=='get-latest':get_latest(a.output);return 0
    if a.command=='restore-design':restore_design(a.output,a.area);return 0
    restore(a.snapshot,a.output,a.with_source_delta);return 0

if __name__=='__main__':sys.exit(main())
