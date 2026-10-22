from pathlib import Path
P=Path(__file__).resolve().parents[2];S=P/'experiments/config_transport_20261017/src'
def once(t,a,b):assert t.count(a)==1,(a,t.count(a));return t.replace(a,b)
def edit(name,fn):
    p=S/name;p.write_text(fn(p.read_text(encoding='utf-8')),encoding='utf-8')
def note(t):
    t=once(t,'parameter NG      = 32,','parameter SERIAL_CUSTOM_LEGACY=0,\n    parameter NG      = 32,')
    t=once(t,'reg custom_hold,bank_hold;','reg custom_hold,bank_hold;\n    reg [NG-1:0] group_custom;\n    wire [1:0] event_preset=(OWNED_EVENTS&&ev_owned)?own_preset:(SERIAL_CUSTOM_LEGACY?preset:own_preset);')
    t=once(t,'preset_hold<=own_preset;', 'preset_hold<=event_preset;')
    t=once(t,'custom_hold<=cfg_enabled[own_preset];bank_hold<=cfg_banks[own_preset];','custom_hold<=cfg_enabled[event_preset];bank_hold<=cfg_banks[event_preset];')
    t=t.replace('(owned_hold&&!rf_mode)', '((owned_hold||SERIAL_CUSTOM_LEGACY)&&!rf_mode)')
    t=t.replace('(owned_hold&&!rf_mode&&custom_hold)', '((owned_hold||SERIAL_CUSTOM_LEGACY)&&!rf_mode&&custom_hold)')
    t=once(t,'group_owned=0;','group_owned=0;group_custom=0;')
    # Reset occurs in a separate state register block; clear the extra flag there.
    t=once(t,'group_owned <= 0;','group_owned <= 0;group_custom<=0;') if 'group_owned <= 0;' in t else once(t,'group_owned<=0;','group_owned<=0;group_custom<=0;')
    t=once(t,'group_owned[gsel_r]<=owned_hold;','group_owned[gsel_r]<=owned_hold;\n                        group_custom[gsel_r]<=SERIAL_CUSTOM_LEGACY&&custom_hold;')
    t=once(t,'&& !group_owned[rf_grp[NB-1:0]]','&& !group_owned[rf_grp[NB-1:0]] && !group_custom[rf_grp[NB-1:0]]')
    return t
edit('note_map_owned.v',note)
def top(t):
    t=once(t,'parameter integer INSTRUMENT_ENV=0,','parameter integer CONFIG_SERIAL=0,INSTRUMENT_ENV=0,')
    t=once(t,'reg         u_have_addr;','reg         u_have_addr;') if 'reg         u_have_addr;' in t else t
    marker='    uart_rx #(.CLK_HZ(27000000), .BAUD(UART_BAUD)) u_uart ('
    block='''    wire cfg_sandbox,cfg_pair_reset;
    wire [7:0] cfg_read;
    wire tx_cfg_valid,tx_cfg_commit;
    wire [1:0] tx_cfg_slot;
    wire [3:0] tx_cfg_part;
    wire [87:0] tx_cfg_word;
    wire nm_cfg_ready,nm_cfg_applied,nm_cfg_error;
    wire raw_uart_wr=u_rx_valid & u_have_addr;
    wire cfg_owner=CONFIG_SERIAL&&cfg_sandbox;
    assign cfg_ready=nm_cfg_ready&&!cfg_owner;
    assign cfg_applied=nm_cfg_applied&&!cfg_owner;
    assign cfg_error=nm_cfg_error&&!cfg_owner;
    generate if(CONFIG_SERIAL)begin: serial_configuration
        uart_cfg_transport receiver(.clk(clk),.rst_n(rst_n),.rx_byte(u_rx_valid),
            .wr_en(raw_uart_wr),.wr_addr(u_addr),.wr_data(u_rx_data),.rd_addr(rb_addr),
            .idle_allowed(nm_active==0&&!nm_busy&&uartq_level==0&&!own_valid),.enabled_slots(u_nm.cfg_enabled),
            .rd_data(cfg_read),.sandbox(cfg_sandbox),.pair_reset(cfg_pair_reset),
            .cfg_valid(tx_cfg_valid),.cfg_commit(tx_cfg_commit),.cfg_slot(tx_cfg_slot),.cfg_part(tx_cfg_part),.cfg_word(tx_cfg_word),
            .cfg_ready(nm_cfg_ready),.cfg_applied(nm_cfg_applied),.cfg_error(nm_cfg_error));
    end else begin
        assign cfg_read=0;assign cfg_sandbox=0;assign cfg_pair_reset=0;
        assign tx_cfg_valid=0;assign tx_cfg_commit=0;assign tx_cfg_slot=0;assign tx_cfg_part=0;assign tx_cfg_word=0;
    end endgenerate
'''
    t=once(t,marker,block+marker)
    t=once(t,'else if (u_rx_valid) begin', 'else if(CONFIG_SERIAL&&cfg_pair_reset&&!u_rx_valid)u_have_addr<=0;\n        else if (u_rx_valid) begin')
    t=once(t,'wire        uart_wr_en   = u_rx_valid & u_have_addr;',"wire        uart_wr_en   = raw_uart_wr && (!cfg_owner || u_addr==8'h0f);")
    t=once(t,".wr_en(wr_en && !(wr_addr >= 8'h74 && wr_addr <= 8'h7C))", ".wr_en(wr_en && !(CONFIG_SERIAL&&wr_addr[7]) && !(wr_addr >= 8'h74 && wr_addr <= 8'h7C))")
    t=once(t,"default: tx_data <= (BOARD_DIAG && rb_addr[7]) ? diag_read : R[{rb_addr, 3'b000} +: 8];", "default: tx_data <= (CONFIG_SERIAL && rb_addr>=8'hd0 && rb_addr<=8'he9) ? cfg_read : (BOARD_DIAG && rb_addr[7]) ? diag_read : R[{rb_addr, 3'b000} +: 8];")
    t=once(t,'.GLIDE_EN(1\'b1), .SPEC_STAGED(1),', ".SERIAL_CUSTOM_LEGACY(CONFIG_SERIAL),.GLIDE_EN(1'b1), .SPEC_STAGED(1),")
    t=once(t,'.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),', '.cfg_valid(cfg_owner?tx_cfg_valid:cfg_valid),.cfg_commit(cfg_owner?tx_cfg_commit:cfg_commit),.cfg_slot(cfg_owner?tx_cfg_slot:cfg_slot),.cfg_part(cfg_owner?tx_cfg_part:cfg_part),.cfg_word(cfg_owner?tx_cfg_word:cfg_word),')
    t=once(t,'.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),','.cfg_ready(nm_cfg_ready),.cfg_applied(nm_cfg_applied),.cfg_error(nm_cfg_error),')
    return t
edit('tdm_top_owned.v',top)
edit('left_layer_music_probe.v',lambda t:once(once(t,'parameter integer INSTRUMENT_ENV=0,','parameter integer CONFIG_SERIAL=0,INSTRUMENT_ENV=0,'),'tdm_top_owned #(.INSTRUMENT_ENV(INSTRUMENT_ENV),','tdm_top_owned #(.CONFIG_SERIAL(CONFIG_SERIAL),.INSTRUMENT_ENV(INSTRUMENT_ENV),'))
edit('instrument_layer_probe.v',lambda t:once(once(t,'parameter INSTRUMENT_ENV=1','parameter CONFIG_SERIAL=1,INSTRUMENT_ENV=1'),'#(.INSTRUMENT_ENV(INSTRUMENT_ENV)) music','#(.CONFIG_SERIAL(CONFIG_SERIAL),.INSTRUMENT_ENV(INSTRUMENT_ENV)) music'))
print('transport hooks generated; needs simulation/resource validation')
