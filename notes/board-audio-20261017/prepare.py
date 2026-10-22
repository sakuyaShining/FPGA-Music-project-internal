from pathlib import Path
import hashlib,json,zipfile,datetime,sys,shutil
P=Path(__file__).resolve().parents[2];U=P/'experiments/resource_safety_20261016';N=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
delivery=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence'):
    for name,digest in delivery[group].items():assert sha(U/name)==digest,(group,name)
for name,digest in delivery['design_documents'].items():assert sha(P/name)==digest,name
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir(parents=True)
paths={U/name for g in ('source_files','evidence') for name in delivery[g]};paths.add(U/'delivery.json');paths.update(P/name for name in delivery['design_documents'])
paths.update(P/name for name in ['src/constr/tdm_top.cst','src/constr/tdm_top.sdc','tools/scripts/prepare_board_diag.py'])
manifest={p.relative_to(P).as_posix():sha(p) for p in sorted(paths)}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in manifest:z.write(P/name,name)
with zipfile.ZipFile(B/'before.zip') as z:assert z.testzip() is None and all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in manifest.items())
(B/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
print('PASS pre-edit verified backup',len(manifest),B,flush=True)
R=P/'experiments/board_audio_20261017';S=R/'src';S.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(U));from common import sources
files=sources('all')+list((U/'engine').glob('*.hex'))+list((U/'rtl').glob('*.vh'))
assert len(files)==len({p.name for p in files})
for p in files:shutil.copyfile(p,S/p.name)
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files={p.relative_to(U).as_posix():sha(p) for p in files}),indent=2),encoding='utf-8')
def edit(name,changes):
    s=(S/name).read_text(encoding='utf-8')
    for a,b in changes:
        assert s.count(a)==1,(name,a[:80],s.count(a));s=s.replace(a,b)
    (S/name).write_text(s,encoding='utf-8')
edit('tdm_top_owned.v',[
('parameter integer BOARD_DIAG = 0,','parameter integer BOARD_DIAG = 0, parameter integer DIAG_FINGER=1,'),
('    input wire cfg_valid,cfg_commit,','''    input wire [7:0] board_status,board_case,
    output wire board_wr_en,
    output wire [7:0] board_wr_addr,board_wr_data,
    input wire cfg_valid,cfg_commit,'''),
('.wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),\n            .rd_addr(','.wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),.test_status(board_status),.test_case(board_case),\n            .rd_addr('),
('assign monitor_valid=sample_en;','assign board_wr_en=wr_en;assign board_wr_addr=wr_addr;assign board_wr_data=wr_data;\nassign monitor_valid=sample_en;')])
p=S/'tdm_top_owned.v';s=p.read_text(encoding='utf-8');assert s.count('BOARD_DIAG ? diag_')==5;s=s.replace('BOARD_DIAG ? diag_','(BOARD_DIAG && DIAG_FINGER) ? diag_');p.write_text(s,encoding='utf-8')
edit('board_diag.v',[
('    input wire clk, rst_n, sample_en,','    input wire clk, rst_n, sample_en,\n    input wire [7:0] test_status,test_case,'),
("            8'hA9:rd_data=FINGER_SCOPE;","            8'hA9:rd_data=FINGER_SCOPE;\n            8'hC0:rd_data=8'h72;8'hC1:rd_data=test_status;8'hC2:rd_data=test_case;8'hC3:rd_data=1;")])
edit('left_layer_music_probe.v',[
('LINK_TIMEOUT=8192)(', 'LINK_TIMEOUT=8192,BOARD_DIAG=0)('),
('    input wire [3:0] layer_selection,','''    input wire [7:0] board_status,board_case,
    output wire board_wr_en,
    output wire [7:0] board_wr_addr,board_wr_data,
    input wire [3:0] layer_selection,'''),
('.BOARD_DIAG(0)', '.BOARD_DIAG(BOARD_DIAG),.DIAG_FINGER(0)'),
('.cfg_valid(cfg_valid),.cfg_commit(cfg_commit)', '.board_status(board_status),.board_case(board_case),.board_wr_en(board_wr_en),.board_wr_addr(board_wr_addr),.board_wr_data(board_wr_data),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit)')])
print('Prepared isolated current engine and observer-only diagnostic hooks',R)
