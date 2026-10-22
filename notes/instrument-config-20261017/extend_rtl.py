from pathlib import Path
P=Path(__file__).resolve().parents[2];S=P/'experiments/instrument_config_20261017/src'
def edit(name,fn):
    p=S/name;t=p.read_text(encoding='utf-8');p.write_text(fn(t),encoding='utf-8')
def once(t,a,b):
    assert t.count(a)==1,(a,t.count(a));return t.replace(a,b)
for name in ('tdm_top_owned.v','note_map_owned.v','left_layer_music_probe.v','instrument_layer_probe.v'):
    edit(name,lambda t:t.replace('input wire [47:0] cfg_word','input wire [87:0] cfg_word'))
edit('compat_music_probe.v',lambda t:t.replace('.cfg_word(48\'d0)',".cfg_word(88'd0)"))
def table(t):
    t=t.replace('[47:0]','[87:0]')
    t=once(t,"end else if(word[23])error<=1;",'''end else if(word[23] || |word[87:84] ||
                    (word[83] && (word[78:63]==0 || word[78:63]>32768 || word[54:53]==0 ||
                     word[47:32]==0 || word[22:7]>32768 || word[6:5]==0)))error<=1;''')
    return t
edit('instrument_table.v',table)
def note(t):
    t=once(t,'wire [47:0] custom_entry;','wire [87:0] custom_entry;')
    t=once(t,'output reg  [22:0]         load_epar,','output reg  [22:0]         load_epar,\n    output reg [39:0] load_env,')
    t=once(t,'custom_hold ? custom_entry :','custom_hold ? custom_entry[47:0] :')
    t=once(t,"load_epar <= 23'd0;","load_epar <= 23'd0;\n            load_env <= 40'd0;")
    t=once(t,'load_epar <= p_epar;',"load_epar <= p_epar;\n                    load_env <= (owned_hold&&!rf_mode&&custom_hold) ? custom_entry[87:48] : 40'd0;")
    return t
edit('note_map_owned.v',note)
def top(t):
    t=once(t,'parameter integer BOARD_DIAG = 0,','parameter integer INSTRUMENT_ENV=0, BOARD_DIAG = 0,')
    t=once(t,'wire [22:0]        nm_load_epar;','wire [22:0]        nm_load_epar;\n    wire [39:0] nm_load_env;')
    t=once(t,'.load_gate(nm_load_gate), .load_epar(nm_load_epar),','.load_gate(nm_load_gate), .load_epar(nm_load_epar), .load_env(nm_load_env),')
    t=once(t,'.PART(P), .FINGER_EXPR(FINGER_EXPR), .EXPLICIT_START(1), .RIGHT_TIMBRE(RIGHT_TIMBRE)', '.PART(P), .FINGER_EXPR(FINGER_EXPR), .EXPLICIT_START(1), .RIGHT_TIMBRE(RIGHT_TIMBRE), .INSTRUMENT_ENV(INSTRUMENT_ENV)')
    t=once(t,'.load_epar(load_epar),',".load_epar(load_epar),\n        .load_env((boot_scrub_write||test_mode_eff) ? 40'd0 : nm_load_env),")
    return t
edit('tdm_top_owned.v',top)
def left(t):
    t=once(t,'parameter integer NF=26,','parameter integer INSTRUMENT_ENV=0,NF=26,')
    t=once(t,'tdm_top_owned #(.FINGER_EXPR(1),','tdm_top_owned #(.INSTRUMENT_ENV(INSTRUMENT_ENV),.FINGER_EXPR(1),')
    return t
edit('left_layer_music_probe.v',left)
edit('instrument_layer_probe.v',lambda t:once(once(t,'module instrument_layer_probe(','module instrument_layer_probe #(parameter INSTRUMENT_ENV=1)('),'left_layer_music_probe music(','left_layer_music_probe #(.INSTRUMENT_ENV(INSTRUMENT_ENV)) music('))
def core(t):
    t=once(t,'parameter RIGHT_TIMBRE = 0','parameter INSTRUMENT_ENV=0,\n    parameter RIGHT_TIMBRE = 0')
    t=once(t,'input  wire [22:0]                 load_epar,','input  wire [22:0]                 load_epar,\n    input wire [39:0] load_env, // custom flag / attack / phase dividers / release')
    t=once(t,'localparam integer LAT  = 4;','localparam integer LAT  = 4;\n    localparam integer EPW=31+(INSTRUMENT_ENV?40:0);')
    for a in ('reg [30:0]        pe_mem','reg [30:0] epar_mem','reg [30:0]        epar1','reg [30:0]        pe1'):
        t=once(t,a,a.replace('[30:0]','[EPW-1:0]'))
    marker='    osc_env #(.ENV_W(ENV_W), .STG_W(STG_W)) u_env ('
    block='''    // Extended metadata shares exactly the pending/active epar lifetime.
    // No extra lookup keyed by a mutable preset: released/old notes keep their copy.
    wire [EPW-1:0] next_epar,pending_epar;
    wire [ENV_W-1:0] env_calc,env_a_inc;
    wire [STG_W-1:0] stg_calc;
    wire [1:0] env_r_m;wire [4:0] env_r_k;
    generate if(INSTRUMENT_ENV)begin: per_instrument_env
        wire [39:0] eff_env=replace_params?pe1[70:31]:epar1[70:31];
        wire custom=eff_env[35];
        reg [14:0] phase_count=0,phase_read=0;
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin phase_count<=0;phase_read<=0;end
            else begin
                if(sc==NSLOT-1)phase_count<=phase_count+1'b1;
                phase_read<=phase_count;
            end
        end
        wire [3:0] shift=(stg1==1)?eff_env[34:31]:(stg1==2)?eff_env[14:11]:(stg1==4)?eff_env[10:7]:4'd0;
        wire [14:0] mask=~(15'h7fff << shift);
        wire tick=(phase_read & mask)==0;
        wire hold_level=custom&&!tick&&!trig_on&&!trig_rel;
        assign env_n=hold_level?env1:env_calc;
        assign stg_n=hold_level?stg1:stg_calc;
        assign env_a_inc=custom?eff_env[30:15]:a_inc;
        assign env_r_m=custom?eff_env[6:5]:r_m;
        assign env_r_k=custom?eff_env[4:0]:r_k;
        assign next_epar={eff_env,EXPLICIT_START&&replace_params?pe1[30:23]:epar1[30:23],eff_epar};
        assign pending_epar={load_env,EXPLICIT_START?load_start_tag:8'd0,load_epar};
    end else begin: legacy_env
        assign env_n=env_calc;assign stg_n=stg_calc;
        assign env_a_inc=a_inc;assign env_r_m=r_m;assign env_r_k=r_k;
        assign next_epar={EXPLICIT_START&&replace_params?pe1[30:23]:epar1[30:23],eff_epar};
        assign pending_epar={EXPLICIT_START?load_start_tag:8'd0,load_epar};
    end endgenerate

'''
    t=once(t,marker,block+marker)
    for a,b in [('.a_inc    (a_inc)','.a_inc    (env_a_inc)'),('.r_m      (r_m)','.r_m      (env_r_m)'),('.r_k      (r_k)','.r_k      (env_r_k)'),('.lvl_o    (env_n)','.lvl_o    (env_calc)'),('.stg_o    (stg_n)','.stg_o    (stg_calc)')]:t=once(t,a,b)
    t=once(t,'epar_mem [sl1] <= {EXPLICIT_START && replace_params ? pe1[30:23] : epar1[30:23], eff_epar};','epar_mem [sl1] <= next_epar;')
    t=once(t,"pe_mem [load_slot] <= {EXPLICIT_START ? load_start_tag : 8'd0, load_epar};",'pe_mem [load_slot] <= pending_epar;')
    return t
edit('tdm_engine_rh.v',core)
print('isolated per-slot envelope extension generated; needs validation')
