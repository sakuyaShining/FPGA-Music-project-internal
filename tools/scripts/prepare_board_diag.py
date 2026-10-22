"""Generate a diagnostic overlay on fixed 7ca52c9; never edit other worktrees."""
import hashlib
import json
import shutil
import subprocess
import re
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE='7ca52c9dd57bfc04d97e7ed2261fd802cdff9d97'
BUILD=ROOT/'sim_build/board_diag_20261009'
OUT=BUILD/'diagnostic_v5'
base=BUILD/'base'
if not base.exists():
    BUILD.mkdir(parents=True,exist_ok=True)
    archive=BUILD/'base.zip'
    subprocess.run(['git','archive','--format=zip','--output='+str(archive),BASE],cwd=ROOT,check=True)
    with zipfile.ZipFile(archive) as source_archive:
        source_archive.extractall(base)
for source_path in ['src/rtl/tdm_top.v','src/rtl/tdm_ship.v','src/rtl/note_map.v']:
    expected=subprocess.check_output(['git','show',BASE+':'+source_path],cwd=ROOT)
    if (base/source_path).read_bytes()!=expected:
        raise SystemExit('Base source does not match fixed commit: '+source_path)
if OUT.exists():
    raise SystemExit('Diagnostic directory already exists; preserve it and choose another directory.')
shutil.copytree(base,OUT,ignore=shutil.ignore_patterns('sim_build','impl'))
top=OUT/'src/rtl/tdm_top.v'
text=top.read_text(encoding='utf-8')
def replace(old,new):
    global text
    if text.count(old)!=1: raise ValueError('Expected exactly one hook: '+old[:90])
    text=text.replace(old,new)
replace('parameter integer FINGER_EXPR = 0','parameter integer FINGER_EXPR = 0,\n    parameter integer BOARD_DIAG = 0')
replace('wire [15:0] pad_state;', 'wire [15:0] pad_state_raw;\n    wire [15:0] pad_state=BOARD_DIAG ? 16\'d0 : pad_state_raw;')
replace('.state(pad_state),','.state(pad_state_raw),')
replace('reg  [2:0]  rb_st;', 'wire [7:0] diag_read;\n    wire diag_fvalid;\n    wire [1:0] diag_fcmd;\n    wire [4:0] diag_fid,diag_fgroup;\n    wire signed [11:0] diag_fpos;\n    reg  [2:0]  rb_st;')
replace('reg         tx_start;', 'reg [12:0] diag_stream_count;\n    reg [1:0] diag_stream_byte;\n    reg         tx_start;')
replace("rb_st <= 3'd0; tx_start <= 1'b0; rb_addr <= 8'd0; tx_data <= 8'd0;",
        "rb_st <= 3'd0; tx_start <= 1'b0; rb_addr <= 8'd0; tx_data <= 8'd0;diag_stream_count<=0;diag_stream_byte<=0;")
replace("rb_addr <= wr_data;\n                          rb_st   <= 3'd1;",
        "rb_addr <= wr_data;diag_stream_count<=0;diag_stream_byte<=0;\n                          rb_st   <= 3'd1;")
replace('default: tx_data<=R[{rb_addr, 3\'b000} +: 8];',
        'default: tx_data<=(BOARD_DIAG && rb_addr[7]) ? diag_read : R[{rb_addr, 3\'b000} +: 8];')
replace("3'd4: if (tx_done) rb_st <= 3'd0;", """3'd4: if (tx_done) begin
                    if(BOARD_DIAG && rb_addr==8'hA8 && diag_stream_count<13'd6143) begin
                        diag_stream_count<=diag_stream_count+1'b1;
                        diag_stream_byte<=diag_stream_byte==2 ? 0 : diag_stream_byte+1'b1;
                        rb_st<=3'd5;
                    end else rb_st<=3'd0;
                end
                3'd5: rb_st<=3'd3;""")
replace('.cmd_valid(finger_valid && !test_mode_eff), .cmd(finger_cmd),',
        '.cmd_valid((BOARD_DIAG ? diag_fvalid : finger_valid) && !test_mode_eff), .cmd(BOARD_DIAG ? diag_fcmd : finger_cmd),')
replace('.finger(finger_id), .group(finger_group), .position(finger_position),',
        '.finger(BOARD_DIAG ? diag_fid : finger_id), .group(BOARD_DIAG ? diag_fgroup : finger_group), .position(BOARD_DIAG ? diag_fpos : finger_position),')
replace('finger_pitch #(.NG(NG), .NF(32)) u_finger (',
        'finger_pitch #(.NG(BOARD_DIAG ? 2 : NG), .NF(BOARD_DIAG ? 2 : 32)) u_finger (')
replace('.cmd_valid((BOARD_DIAG ? diag_fvalid : finger_valid) && !test_mode_eff),',
        '.cmd_valid((BOARD_DIAG ? diag_fvalid : finger_valid) && !test_mode_eff && (!BOARD_DIAG || (diag_fid<2 && (diag_fcmd!=0 || diag_fgroup<2)))),')
replace('.finger(BOARD_DIAG ? diag_fid : finger_id), .group(BOARD_DIAG ? diag_fgroup : finger_group),',
        '.finger(BOARD_DIAG ? {4\'d0,diag_fid[0]} : finger_id), .group(BOARD_DIAG ? {4\'d0,diag_fgroup[0]} : finger_group),')
replace('.voice_valid(voice_valid), .voice_on(voice_on), .voice_group(voice_group),\n            .voice_active(nm_active),\n            .expr_active(finger_active), .expr_offsets(finger_offsets)',
        '.voice_valid(voice_valid && (!BOARD_DIAG || voice_group<2)), .voice_on(voice_on), .voice_group(voice_group),\n            .voice_active(nm_active[(BOARD_DIAG ? 2 : NG)-1:0]),\n            .expr_active(finger_active[(BOARD_DIAG ? 2 : NG)-1:0]), .expr_offsets(finger_offsets[(BOARD_DIAG ? 2 : NG)*18-1:0])')
replace('end else begin: no_contact_expression',
        'if(BOARD_DIAG) begin: remaining_groups\n            assign finger_active[31:2]=0;\n            assign finger_offsets[575:36]=0;\n        end\n    end else begin: no_contact_expression')
replace('\nendmodule', '''
    generate if(BOARD_DIAG) begin: board_observer
        board_diag #(.FINGER_SCOPE(2)) u_diag(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),
          .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
          .rd_addr(rb_addr==8'hA8 ? 8'hA0+{6'd0,diag_stream_byte} : rb_addr),
          .stream_start(wr_en && wr_addr==8'h0F && wr_data==8'hA8),
          .stream_next(rb_st==3'd4 && tx_done && rb_addr==8'hA8 && diag_stream_byte==2),
          .ev_ack(nm_ev_ack),.ev_on(ev_on_r),.ev_note(ev_note_r),
          .active(nm_active),.finger_active(finger_active),
          .dry_sample(sample),.audio_sample(audio),.queue_level(ev_q_level),.note_busy(nm_busy),
          .voice_valid(voice_valid),.voice_group(voice_group),.voice_note(voice_note),
          .rd_data(diag_read),.finger_valid(diag_fvalid),.finger_cmd(diag_fcmd),
          .finger_id(diag_fid),.finger_group(diag_fgroup),.finger_position(diag_fpos));
    end else begin: no_board_observer
        assign diag_read=0;
        assign diag_fvalid=0;assign diag_fcmd=0;assign diag_fid=0;assign diag_fgroup=0;assign diag_fpos=0;
    end endgenerate
endmodule''')
top.write_text(text,encoding='utf-8')
nm=OUT/'src/rtl/note_map.v'
ntext=nm.read_text(encoding='utf-8')
hook="if (!rst_n) begin\n            st        <= ST_IDLE;"
assert ntext.count(hook)==1
ntext=ntext.replace('integer gi;', 'integer gi;\n    integer reset_group;')
ntext=ntext.replace(hook,"if (!rst_n) begin\n            gact <= 0;\n            for(reset_group=0;reset_group<NG;reset_group=reset_group+1) gtab[reset_group]<=FREE;\n            st        <= ST_IDLE;")
nm.write_text(ntext,encoding='utf-8')
ship=OUT/'src/rtl/tdm_ship.v'
stext=ship.read_text(encoding='utf-8')
assert stext.count('tdm_top u_top (')==1
stext=stext.replace('tdm_top u_top (', '''// Physical S1 on pin 87 is active high (official audio top inverts rst).
    reg [1:0] reset_release;
    initial reset_release=0;
    always @(posedge clk or posedge rst_n) begin
        if(rst_n) reset_release<=0;
        else reset_release<={reset_release[0],1'b1};
    end
    wire core_rst_n=reset_release[1];
    tdm_top #(.BOARD_DIAG(1),.FINGER_EXPR(1)) u_top (''')
stext=stext.replace('.clk(clk), .rst_n(rst_n),','.clk(clk), .rst_n(core_rst_n),')
ship.write_text(stext,encoding='utf-8')
cst=OUT/'src/constr/tdm_top.cst'
cst.write_text(cst.read_text(encoding='utf-8').replace('"rst_n" IO_TYPE=LVCMOS33 PULL_MODE=UP;',
                                                      '"rst_n" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;'),encoding='utf-8')
shutil.copy2(ROOT/'src/board_diag/board_diag.v',OUT/'src/rtl/board_diag.v')
prj=OUT/'src/gowin/tdm_synth/tdm_synth.gprj'
prj.write_text(prj.read_text(encoding='utf-8').replace('<FileList>','<FileList>\n        <File path="../../rtl/board_diag.v" type="file.verilog" enable="1"/>'),encoding='utf-8')
spec_doc=OUT/'docs/02-技术方案/34-当前版本规格-基线v1.md'
def bind_row(match):
    path=match.group(1)
    blob=subprocess.check_output(['git','hash-object',str(OUT/path)],cwd=ROOT).decode().strip()[:12]
    return '| `%s` | `%s` |'%(path,blob)
spec_doc.write_text(re.sub(r'\|\s*`(src/rtl/[\w_]+\.v)`\s*\|\s*`[0-9a-f]{12}`\s*\|',
                          bind_row,spec_doc.read_text(encoding='utf-8')),encoding='utf-8')
manifest=dict(base_commit=BASE,diagnostic=True,physical_pads_enabled=False,finger_expression=True,
              finger_scope=2,physical_reset_active_high=True,
              files={str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((OUT/'src').rglob('*')) if p.is_file()})
(BUILD/'diagnostic_v5-source.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(OUT)
