"""Capture reviewed local workspaces without changing their indexes or files.

Uses isolated indexes, raw Git blobs and new snapshot refs. Snapshots are WIP,
not atomic project transactions or product acceptance. No push in this script.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, subprocess, os, stat, json, hashlib, gzip, re

REPO = Path(__file__).resolve().parents[2]
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
TOPS = {'docs','src','tools','experiments','notes','hardware','project','handoff','delivery'}
EXTS = set('.v .sv .vh .hex .mem .cst .sdc .gprj .tcl .py .ps1 .sh .bat .cmd .md .json .csv .tsv .txt .xml .yaml .yml .toml .ini .cfg .png .svg .jpg .jpeg .pdf .js .ts .mjs .cjs .html .css .cir .dsn .ses .eprj3 .epcb2 .esch2 .wav .raw .pcm .log .timing_paths .gz'.split())
ASSET_EXTS=set('.ttf .otf .ico .qss .ui .qrc .qml .svh .vhd .vhdl .h .c .cpp .cxx .xlsx .docx .pptx .bin .db .do .f .lst'.split())
EXTS.update(ASSET_EXTS)
SKIP_DIRS = {'.git','node_modules','__pycache__','.venv','venv','impl','backups','.archify','.obsidian','_site-archive','vendor-examples'}
SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
TEXT_COMPRESS = {'.tsv','.txt','.log','.timing_paths','.raw','.pcm'}

def git(*args, env=None, data=None):
    p = subprocess.run(['git','-C',str(REPO),*args], input=data, capture_output=True, env=env or ENV)
    if p.returncode: raise RuntimeError((args,p.stderr.decode('utf-8','replace')[:2000]))
    return p.stdout

def stable_read(p):
    for _ in range(3):
        a=p.stat(); b=p.read_bytes(); z=p.stat()
        if (a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns): return b,z
    raise RuntimeError('Continuously changing file: '+str(p))

def scan(root, tracked, plain=False):
    found={}; excluded=[]; stack=[root]
    while stack:
        d=stack.pop()
        for e in os.scandir(d):
            p=Path(e.path); rel=p.relative_to(root).as_posix()
            s=e.stat(follow_symlinks=False)
            if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                excluded.append(dict(path=rel,reason='reparse-point; target is not recursively captured')); continue
            if e.is_dir(follow_symlinks=False):
                if e.name in SKIP_DIRS or e.name.startswith(('build_','synth_','synthesis_','backup-')) or (d==root and not plain and e.name not in TOPS):
                    excluded.append(dict(path=rel,reason='generated/vendor/out-of-scope directory')); continue
                stack.append(p)
            elif e.is_file(follow_symlinks=False):
                if rel in tracked: continue
                if e.name in {'.env','.git','.DS_Store'} or e.name.endswith(('.pyc','.tmp','.bak')): continue
                if p.suffix.lower() in EXTS or e.name in {'.gitignore','requirements.txt','Makefile','HANDOFF.md'}:
                    found[rel]=p
    # Already tracked files are preserved regardless of extension/ignore rules.
    for rel in tracked:
        p=root/rel
        if p.is_file(): found[rel]=p
    return found,excluded

def capture(label,root,parent,run,plain=False):
    root=Path(root); ref='refs/heads/codex/preserve-'+label+'-20261022'
    existing=subprocess.run(['git','-C',str(REPO),'rev-parse','--verify',ref],capture_output=True,env=ENV)
    if existing.returncode==0: raise RuntimeError('Ref exists; refuse overwrite: '+ref)
    tree={}
    if parent:
        for row in git('ls-tree','-r','-z',parent).split(b'\0'):
            if row:
                meta,name=row.split(b'\t',1); mode,kind,oid=meta.split()
                if kind==b'blob': tree[name.decode('utf-8')]=(mode.decode(),oid.decode())
    found,excluded=scan(root,tree,plain)
    stage=run/label;stage.mkdir(); entries=[]; captured={}; paths=[]; deleted=[]
    for rel in sorted(found):
        p=found[rel]; b,s=stable_read(p)
        if len(b)>95_000_000: raise RuntimeError('Oversize Git input; review separately: '+str(p))
        if len(b)<10_000_000 and SECRET.search(b): raise RuntimeError('Potential credential; review file: '+str(p))
        sha=hashlib.sha256(b).hexdigest(); stored=rel; payload=b; codec='raw'
        if p.suffix.lower() in TEXT_COMPRESS and len(b)>262144:
            stored='.preservation/compressed/'+rel+'.gz';payload=gzip.compress(b,compresslevel=6,mtime=0);codec='gzip'
        target=stage/stored;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
        mode=tree.get(rel,('100644',None))[0]
        entries.append((stored,mode));paths.append(target)
        captured[rel]=dict(stored_path=stored,codec=codec,bytes=len(b),sha256=sha,lf_sha256=hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest(),mtime_ns=s.st_mtime_ns)
    for rel in tree:
        if rel not in found: deleted.append(rel)
    # Recheck the entire selected set after copying; refuse mixed moving inputs.
    changed=[]
    for rel,item in captured.items():
        p=root/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: changed.append(rel)
    if changed: raise RuntimeError('Files changed during capture; retry new run: '+str(changed[:12]))
    manifest=dict(schema=1,id=label,captured_at=datetime.now(timezone.utc).isoformat(),source_root=str(root),source_parent=parent,
                  role='WIP preservation only; no acceptance, replay or deployment authorization',
                  consistency='Selected files unchanged across this capture; not an atomic multi-workspace transaction',
                  files=captured,deleted_tracked_paths=deleted,excluded=excluded,
                  scope='Tracked files and selected source/evidence extensions; generated/vendor directories and reparse targets excluded')
    mrel='.preservation/'+label+'.json';mp=stage/mrel;mp.parent.mkdir(exist_ok=True);mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    entries.append((mrel,'100644'));paths.append(mp)
    # hash-object stores exact bytes, independent of autocrlf and workspace filters.
    oids=git('hash-object','--no-filters','-w','--stdin-paths',data=('\n'.join(str(p) for p in paths)+'\n').encode()).decode().splitlines()
    if len(oids)!=len(entries): raise RuntimeError('Blob count mismatch')
    env=dict(ENV,GIT_INDEX_FILE=str(run/(label+'.index')))
    git('read-tree',parent if parent else '--empty',env=env)
    updates=[]
    for rel in deleted: updates.append(('0 '+'0'*40+'\t'+rel+'\0').encode())
    original_by_stored={v['stored_path']:k for k,v in captured.items()}
    for (rel,mode),oid in zip(entries,oids):
        # For compressed files remove an old raw tracked entry, if any.
        original=original_by_stored.get(rel)
        if original and original!=rel and original in tree: updates.append(('0 '+'0'*40+'\t'+original+'\0').encode())
        updates.append((mode+' '+oid+'\t'+rel+'\0').encode('utf-8'))
    git('update-index','-z','--index-info',env=env,data=b''.join(updates))
    tree_oid=git('write-tree',env=env).decode().strip()
    args=['commit-tree',tree_oid]+(['-p',parent] if parent else [])
    commit=git(*args,data=('Preserve '+label+' workspace inputs and WIP evidence (not product acceptance)\n').encode()).decode().strip()
    git('update-ref',ref,commit,'0'*40)
    return dict(id=label,root=str(root),branch=ref[len('refs/heads/'):],commit=commit,parent=parent,files=len(captured),bytes=sum(v['bytes'] for v in captured.values()),manifest=mrel,compressed=sum(v['codec']=='gzip' for v in captured.values()),excluded=len(excluded))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--only',nargs='*');a=ap.parse_args()
    a.run.mkdir(parents=True,exist_ok=True);out=a.run/'snapshots.json'
    results=json.loads(out.read_text(encoding='utf-8')) if out.exists() else []
    blocks=git('worktree','list','--porcelain').decode('utf-8').strip().split('\n\n'); jobs=[]
    for block in blocks:
        fields=dict((x.partition(' ')[0],x.partition(' ')[2]) for x in block.splitlines())
        root=Path(fields['worktree']);label='main' if root==Path('C:/Users/Sakuya/FPGA-Music-project') else root.parent.name
        if root.drive.upper()=='D:': label='workbuddy'
        jobs.append((label,root,fields['HEAD'],False))
    jobs.extend((label,Path(path),None,True) for label,path in [
        ('m1-work','D:/FPGA-Project/codex-builds/fpga-m1-agent-work'),
        ('m1-reference','D:/FPGA-Project/codex-builds/fpga-m1-baseline-ref'),
        ('native-source57','C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-U8BusWork-20261022'),
        ('native-trial50','C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Addr3Work-20261022'),
        ('native-r15','C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-HarmClosure-20261021-r15')])
    for label,root,parent,plain in jobs:
        if a.only and label not in a.only: continue
        if any(r['id']==label for r in results): continue
        print('Capturing '+label+' ...',flush=True)
        r=capture(label,root,parent,a.run,plain);results.append(r)
        out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(r,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
