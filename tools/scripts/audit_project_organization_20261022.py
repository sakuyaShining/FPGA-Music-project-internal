"""Read-only Git/worktree/storage audit; writes reports only in this worktree.

No fetch, checkout, add, commit, merge, push, prune, gc, file moves or deletes.
Reparse directories are recorded and never recursively followed.
"""
from pathlib import Path
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import hashlib,json,os,stat,subprocess,csv,re

ROOT=Path(__file__).resolve().parents[2]
MAIN=Path('C:/Users/Sakuya/FPGA-Music-project')
OUT=ROOT/'notes/project-organization-audit-20261022'
OUT.mkdir(parents=True,exist_ok=True)
ENV=os.environ.copy();ENV.update(GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
def git(root,*args,timeout=90):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,env=ENV,timeout=timeout)
    return p.returncode,p.stdout,p.stderr
def output(root,*args):
    rc,o,e=git(root,*args);assert rc==0,(str(root),args,e.decode('utf-8','replace'))
    return o
def paths(blob):return [x.decode('utf-8') for x in blob.split(b'\0') if x]
def statuses(blob):
    parts=blob.split(b'\0');i=0;items=[]
    while i<len(parts):
        x=parts[i];i+=1
        if not x:continue
        s=x[:2].decode();p=x[3:].decode('utf-8');v=dict(status=s,path=p)
        if 'R' in s or 'C' in s:v['old_path']=parts[i].decode('utf-8');i+=1
        items.append(v)
    return items
def trees(ref):
    data={}
    for row in output(MAIN,'ls-tree','-r','-z','-l',ref).split(b'\0'):
        if not row:continue
        left,name=row.split(b'\t',1);mode,kind,oid,size=left.split()
        if kind!=b'blob':continue
        data[name.decode('utf-8')]=dict(oid=oid.decode(),bytes=int(size),mode=mode.decode())
    return data
refs=output(MAIN,'for-each-ref','--format=%(refname)').decode().splitlines()
ref_trees={r:trees(r) for r in refs if r.startswith(('refs/heads/','refs/remotes/','refs/tags/'))}
def oid_set(refnames):
    if not refnames:return set()
    return {line.split(b' ',1)[0].decode() for line in output(MAIN,'rev-list','--objects',*refnames).splitlines()}
named_oids=oid_set(list(ref_trees))
internal_oids=oid_set([r for r in ref_trees if r.startswith('refs/remotes/internal/')])
blocks=output(MAIN,'worktree','list','--porcelain').decode('utf-8').strip().split('\n\n')
worktrees=[]
for block in blocks:
    d={}
    for line in block.splitlines():
        k,_,v=line.partition(' ');d[k]=v if v else True
    worktrees.append(d)
def totals(root,tracked):
    d=defaultdict(lambda:dict(tracked=0,bytes_in_worktree=0,missing_tracked=0))
    for rel in tracked:
        top=rel.split('/',1)[0];d[top]['tracked']+=1;p=root/rel
        try:d[top]['bytes_in_worktree']+=p.stat().st_size
        except OSError:d[top]['missing_tracked']+=1
    return dict(d)
def inspect_worktree(w):
    root=Path(w['worktree']);result=dict(**w,exists=root.is_dir())
    if not root.is_dir():return result
    tracked=paths(output(root,'ls-files','-z'))
    state=statuses(output(root,'status','--porcelain=v1','-z','--untracked-files=all'))
    modified=[s for s in state if s['status']!='??'];untracked=[s for s in state if s['status']=='??']
    branch=w.get('branch');head=w['HEAD']
    contains=output(root,'for-each-ref','--contains='+head,'--format=%(refname:short)','refs/heads','refs/remotes','refs/tags').decode().splitlines()
    a=git(root,'merge-base','--is-ancestor',head,'main')[0]
    board='docs/00-协作/AGENT-BOARD.md';agents='AGENTS.md'
    result.update(tracked_files=len(tracked),tracked_by_top=totals(root,tracked),
        status_counts=dict(Counter(s['status'] for s in state)),tracked_changes=len(modified),untracked_files=len(untracked),
        changes_by_top=dict(Counter(s['path'].split('/',1)[0] for s in modified)),
        untracked_by_top=dict(Counter(s['path'].split('/',1)[0] for s in untracked)),
        tracked_change_paths=modified,untracked_paths=[s['path'] for s in untracked],
        head_contained_in_named_refs=contains,head_is_ancestor_of_main=a==0,
        has_agents=(root/agents).is_file(),has_collaboration_board=(root/board).is_file(),
        agents_tracked=agents in tracked,board_tracked=board in tracked)
    return result
with ThreadPoolExecutor(max_workers=4) as pool:worktrees=list(pool.map(inspect_worktree,worktrees))
main_record=next(w for w in worktrees if Path(w['worktree'])==MAIN)
def disk_profile(root):
    root=Path(root);summary=defaultdict(lambda:dict(files=0,bytes=0,directories=0));links=[];errors=[];vfiles=[]
    stack=[root]
    while stack:
        d=stack.pop()
        try:entries=list(os.scandir(d))
        except OSError as e:errors.append(dict(path=str(d),error=str(e)));continue
        for e in entries:
            if d==root and e.name=='.git':continue
            p=Path(e.path);rel=p.relative_to(root);top=rel.parts[0]
            try:
                s=e.stat(follow_symlinks=False)
                if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    try:target=os.readlink(p)
                    except OSError:target=None
                    links.append(dict(path=rel.as_posix(),target=target,exists=p.exists()));continue
                if e.is_dir(follow_symlinks=False):summary[top]['directories']+=1;stack.append(p)
                elif e.is_file(follow_symlinks=False):
                    summary[top]['files']+=1;summary[top]['bytes']+=s.st_size
                    if p.suffix.lower() in ('.v','.sv','.vh'):vfiles.append(p)
            except OSError as ex:errors.append(dict(path=str(p),error=str(ex)))
    return dict(root=str(root),scope='Directory entry bytes excluding shared .git and reparse targets; not physical disk allocation',
                by_top=dict(summary),links=links,errors=errors),vfiles
profiles={};all_v=[]
for root in [MAIN,ROOT,Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project'),
             Path('D:/FPGA-Project/codex-builds/fpga-m1-agent-work'),Path('D:/FPGA-Project/codex-builds/fpga-m1-baseline-ref')]:
    if root.is_dir():
        p,vs=disk_profile(root);profiles[str(root)]=p;all_v.extend((root,f) for f in vs)
def hashes(p):
    before=p.stat();b=p.read_bytes();after=p.stat()
    if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:return dict(unstable=True)
    oid=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    return dict(sha256=hashlib.sha256(b).hexdigest(),git_raw_oid=oid(b),git_lf_oid=oid(b.replace(b'\r\n',b'\n')),bytes=len(b))
duplicates=defaultdict(list);source_inventory=[]
for root,p in all_v:
    h=hashes(p);rel=p.relative_to(root).as_posix();v=dict(root=str(root),path=rel,**h)
    source_inventory.append(v)
    if 'sha256' in h:duplicates[h['sha256']].append(dict(root=str(root),path=rel))
main_v=[x for x in source_inventory if x['root']==str(MAIN)]
product_vs=[x for x in main_v if x['path'].startswith('experiments/') and
            any('/'+folder+'/' in '/'+x['path'] for folder in ('src','rtl')) and
            not any(k in x['path'].split('/') for k in ('tb','reference','impl'))]
def protection(items):
    known=remote=unstable=0;missing=[]
    for x in items:
        if x.get('unstable'):unstable+=1;continue
        oids={x['git_raw_oid'],x['git_lf_oid']}
        if oids & named_oids:known+=1
        else:missing.append(dict(root=x['root'],path=x['path'],sha256=x['sha256']))
        if oids & internal_oids:remote+=1
    return dict(files=len(items),content_reachable_from_named_local_refs=known,
        content_reachable_from_cached_internal_refs=remote,unstable=unstable,not_found_in_named_local_refs=missing,
        caveat='Raw or CRLF-to-LF normalized Git blob match; cached remote refs do not prove current remote availability. File-level presence is not complete build or validation coverage.')
candidate=[x for x in source_inventory if x['root']==str(ROOT) and x['path'].startswith('experiments/nano20k_feasibility_20261021/') and
           any(x['path'].startswith('experiments/nano20k_feasibility_20261021/'+k) for k in ('engine/src/','engine/rtl/','rtl/'))]
backups={}
for name,root,prefix in [('refs/heads/backup/hardware-20261022',Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project'),'hardware/'),
                         ('refs/heads/backup/ca03-20261022',Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project'),None)]:
    if name not in ref_trees:continue
    tree=ref_trees[name];counts=Counter();modified=[]
    for rel,v in tree.items():
        if prefix and not rel.startswith(prefix):continue
        p=root/rel
        if not p.is_file():counts['missing_in_live_worktree']+=1;continue
        h=hashes(p)
        if h.get('unstable'):counts['unstable']+=1;continue
        if v['oid'] in (h['git_raw_oid'],h['git_lf_oid']):counts['matching_raw_or_lf']+=1
        else:counts['different_from_snapshot']+=1;modified.append(rel)
    pointer='hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json'
    extra={}
    if prefix and pointer in tree:
        old=json.loads(output(MAIN,'show',name+':'+pointer));live=json.loads((root/pointer).read_text(encoding='utf-8-sig'))
        extra=dict(pointer_snapshot=dict(updated_at=old.get('updated_at'),pcb_sha256=old.get('pcb_sha256'),native_drc=old.get('native_drc')),
                   pointer_live=dict(updated_at=live.get('updated_at'),pcb_sha256=live.get('pcb_sha256'),native_drc=live.get('native_drc')))
    backups[name]=dict(root=str(root),tree_entries=len(tree),comparison_scope=prefix or 'whole snapshot tree',counts=dict(counts),different_paths=modified,**extra)
tree_stats={}
for ref,tree in ref_trees.items():
    tops=defaultdict(lambda:dict(files=0,bytes=0))
    for rel,v in tree.items():tops[rel.split('/',1)[0]]['files']+=1;tops[rel.split('/',1)[0]]['bytes']+=v['bytes']
    tree_stats[ref]=dict(files=len(tree),bytes=sum(v['bytes'] for v in tree.values()),by_top=dict(tops))
remote_checks={}
def remote_check(name):
    try:
        rc,o,e=git(MAIN,'-c','credential.interactive=never','ls-remote','--heads',name,timeout=35)
        return name,dict(returncode=rc,heads=o.decode('utf-8','replace').splitlines(),error=e.decode('utf-8','replace'),local_tracking_not_updated=True)
    except subprocess.TimeoutExpired:return name,dict(status='TIMEOUT; remote state unverified',local_tracking_not_updated=True)
with ThreadPoolExecutor(max_workers=2) as pool:remote_checks=dict(pool.map(remote_check,['internal','origin']))
rc,o,e=git(MAIN,'fsck','--connectivity-only','--no-reflogs',timeout=90)
fsck=dict(returncode=rc,stdout_lines=o.decode('utf-8','replace').splitlines(),stderr_lines=e.decode('utf-8','replace').splitlines(),
          scope='Read-only connectivity check, not full blob-content verification')
for name,blob in [('source-inventory.json',source_inventory),('duplicate-verilog-content.json',{h:ps for h,ps in duplicates.items() if len(ps)>1})]:
    (OUT/name).write_text(json.dumps(blob,ensure_ascii=False,indent=2),encoding='utf-8')
result=dict(captured_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),scope='Read-only point-in-time; active chats may change files during/after audit',
    worktrees=worktrees,tree_stats=tree_stats,disk_profiles=profiles,
    source_protection=dict(main_experiment_sources=protection(product_vs),current_candidate=protection(candidate)),
    backup_snapshots=backups,remote_live_checks=remote_checks,git_connectivity=fsck,
    other_locations=dict(builds='D:/FPGA-Project/codex-builds',deliverables='D:/FPGA-Project/codex-deliverables',native_cad='C:/Users/Sakuya/Documents/LCEDA-Pro/projects'),
    no_mutating_git_commands=True,no_source_or_hardware_files_modified=True)
(OUT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'worktrees.csv').open('w',newline='',encoding='utf-8-sig') as f:
    keys=['worktree','HEAD','branch','tracked_files','tracked_changes','untracked_files','has_agents','has_collaboration_board','head_is_ancestor_of_main']
    w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(worktrees)
print(json.dumps(dict(worktrees=len(worktrees),detached=sum(bool(w.get('detached')) for w in worktrees),
    main_tracked=main_record['tracked_files'],main_changes=main_record['tracked_changes'],main_untracked=main_record['untracked_files'],
    candidate_source_protection={k:v for k,v in result['source_protection']['current_candidate'].items() if k!='not_found_in_named_local_refs'},
    remote_checks=remote_checks,git_connectivity_rc=rc,report=str(OUT/'inventory.json')),ensure_ascii=False,indent=2))
