from pathlib import Path
import shutil,hashlib,json
R=Path(__file__).resolve().parents[2]; S=R/'experiments/left_hand_events_20261016'; D=R/'experiments/instrument_layers_20261016'
D.mkdir(exist_ok=True)
for folder in ('engine','rtl','optimization'):
    (D/folder).mkdir(exist_ok=True)
    for p in (S/folder).iterdir():
        if p.is_file() and p.suffix in ('.v','.vh','.hex'):shutil.copyfile(p,D/folder/p.name)
(D/'candidate').mkdir(exist_ok=True)
def transform(path,changes):
    s=(S/path).read_text(encoding='utf-8')
    for a,b in changes:
        assert s.count(a)==1,(path,a[:90],s.count(a));s=s.replace(a,b)
    (D/path).write_text(s,encoding='utf-8')
transform('optimization/note_map_owned.v',[
('    input  wire [1:0]          preset,','''    input wire [1:0] preset, own_preset,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [47:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,'''),
('    reg owned_hold;','''    reg [1:0] preset_hold;
    reg custom_hold,bank_hold;
    wire [3:0] cfg_enabled,cfg_banks;
    wire [47:0] custom_entry;
    reg owned_hold;'''),
('    reg [$clog2(P)-1:0] k;','''    reg [$clog2(P)-1:0] k;
    wire [3:0] table_next_k=(st==ST_LOAD)?k[3:0]+4'd1:k[3:0];
    assign cfg_ready=(st==ST_IDLE);
    instrument_table table_store(.clk(clk),.rst_n(rst_n),
        .valid(cfg_valid&&cfg_ready),.commit(cfg_commit),.slot(cfg_slot),.part(cfg_part),.word(cfg_word),
        .applied(cfg_applied),.error(cfg_error),.enabled(cfg_enabled),.banks(cfg_banks),
        .read_addr({preset_hold,bank_hold,table_next_k}),.read_word(custom_entry));'''),
('assign ev_ack = (st == ST_IDLE) && ev_valid;', 'assign ev_ack = (st == ST_IDLE) && ev_valid && !cfg_valid;'),
('wire [47:0] pentry   = part_rom[{preset, k}];','wire [47:0] pentry = (owned_hold&&!rf_mode) ? (custom_hold ? custom_entry : part_rom[{preset_hold,k}]) : part_rom[{preset,k}];'),
('wire [7:0] amp_src    = spec_replace ? spec_eff : amp_add;', 'wire [7:0] amp_src = (owned_hold&&!rf_mode&&custom_hold) ? p_amp : (spec_replace ? spec_eff : amp_add);'),
('group_owned<=0;owned_hold<=0;instance_hold<=0;owner_index<=0;','group_owned<=0;owned_hold<=0;instance_hold<=0;owner_index<=0;preset_hold<=0;custom_hold<=0;bank_hold<=0;'),
('if (ev_valid) begin','if (ev_valid && !cfg_valid) begin'),
('                        n_hold <= ev_note;','''                        n_hold <= ev_note;
                        preset_hold<=own_preset;
                        custom_hold<=cfg_enabled[own_preset];bank_hold<=cfg_banks[own_preset];'''),
('else if (gact[rf_grp[NB-1:0]]) begin','else if (gact[rf_grp[NB-1:0]] && !group_owned[rf_grp[NB-1:0]]) begin')])
transform('candidate/tdm_top_owned.v',[
('parameter integer OWNED_EVENTS = 0','parameter integer OWNED_EVENTS = 0, parameter integer OWNER_W=13, MULTI_BIND=0'),
('input wire [12:0] own_instance,','''input wire [OWNER_W-1:0] own_instance,
    input wire [1:0] own_preset,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [47:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,'''),
('output wire [12:0] result_instance,','output wire [OWNER_W-1:0] result_instance,'),
('.ev_owned(select_owned),.ev_instance(own_instance),','''.ev_owned(select_owned),.ev_instance(own_instance),.own_preset(own_preset),
        .cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),
        .cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),'''),
('.OWNED_EVENTS(OWNED_EVENTS)', '.OWNED_EVENTS(OWNED_EVENTS),.OWNER_W(OWNER_W)'),
('finger_pitch #(.NG(NG), .NF(32))','finger_pitch #(.NG(NG), .NF(32),.MULTI_BIND(MULTI_BIND))')])
transform('engine/finger_pitch.v',[
('parameter NF=32','parameter NF=32, parameter MULTI_BIND=0'),
('if(owned[i] && owner[i]==finger) owned[i]<=0;','if(!MULTI_BIND && owned[i] && owner[i]==finger) owned[i]<=0;'),
('owner[i]<=finger; anchor[i]<=position;','owner[i]<=finger; anchor[i]<=MULTI_BIND ? moving_anchor : position;'),
('moving_anchor=position;','moving_anchor=position;')])
(D/'upstream.json').write_text(json.dumps(dict(source=str(S),inputs={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in S.rglob('*') if p.is_file() and not any(x in p.relative_to(S).parts for x in ('impl','evidence','__pycache__','synthesis'))}),indent=2),encoding='utf-8')
print(D)
