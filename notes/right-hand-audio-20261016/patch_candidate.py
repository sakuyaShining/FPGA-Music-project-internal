"""Create an opt-in candidate beside, not over, the copied/original engine."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'experiments/right_hand_audio_20261016'
def replace_once(text,old,new):
 assert text.count(old)==1,old[:100]
 return text.replace(old,new)
s=(ROOT/'engine/tdm_engine.v').read_text(encoding='utf-8')
s=replace_once(s,'module tdm_engine #(','module tdm_engine_rh #(')
s=replace_once(s,'    parameter EXPLICIT_START = 0 // Legacy direct clients may omit load_start.',
 '    parameter EXPLICIT_START = 0, // Legacy direct clients may omit load_start.\n    parameter RIGHT_TIMBRE = 0 // Opt-in, disabled path is structurally unchanged.')
s=replace_once(s,'    // ---- 输出 ----','''    // Independent performance modifiers. Q8 unity=256; bounded boost only.
    input wire [PART*10-1:0] timbre_gain_q8,
    input wire [NSLOT/PART-1:0] timbre_voice_mask,

    // ---- 输出 ----''')
insert='''
    // RIGHT_TIMBRE modifies only the read-side amplitude. Never writes base
    // amplitudes, phases, increments, gates, envelope state, tags or velocity.
    // Snapshot all coefficients/mask at logical slot0, before the entire rotated
    // accumulation traversal; do not snapshot at the unrelated sample_en edge.
    wire [CORE_AMP_W-1:0] rh_amp_eff;
    generate if (RIGHT_TIMBRE) begin: right_timbre
        reg [PART*10-1:0] gain_frame;
        reg [NSLOT/PART-1:0] mask_frame;
        wire first_slot = sl1 == 0;
        wire [PART*10-1:0] gain_use = first_slot ? timbre_gain_q8 : gain_frame;
        wire [NSLOT/PART-1:0] mask_use = first_slot ? timbre_voice_mask : mask_frame;
        wire [9:0] raw_gain = gain_use[(sl1 % PART)*10 +: 10];
        wire [9:0] gain = raw_gain < 10'd256 ? 10'd256 : raw_gain;
        wire [CORE_AMP_W+9:0] scaled = amp_eff * gain;
        wire [CORE_AMP_W-1:0] boosted = (|scaled[CORE_AMP_W+9:CORE_AMP_W+8]) ?
                   {CORE_AMP_W{1'b1}} : scaled[CORE_AMP_W+7:8];
        assign rh_amp_eff = mask_use[sl1/PART] ? boosted : amp_eff;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                gain_frame <= {PART{10'd256}};
                mask_frame <= 0;
            end else if(first_slot) begin
                gain_frame <= timbre_gain_q8;
                mask_frame <= timbre_voice_mask;
            end
        end
    end else begin: no_right_timbre
        assign rh_amp_eff = amp_eff;
    end endgenerate
'''
s=replace_once(s,'    // 表地址用【推进前】的相位（细节 1）',insert+'\n    // 表地址用【推进前】的相位（细节 1）')
s=replace_once(s,"amp2 <= increment_invalid ? {CORE_AMP_W{1'b0}} : amp_eff;","amp2 <= increment_invalid ? {CORE_AMP_W{1'b0}} : rh_amp_eff;")
(ROOT/'engine/tdm_engine_rh.v').write_text(s,encoding='utf-8')
t=(ROOT/'engine/tdm_top.v').read_text(encoding='utf-8')
t=replace_once(t,'module tdm_top #(','module tdm_top_rh #(')
t=replace_once(t,'    parameter integer UART_BAUD = 115200','    parameter integer UART_BAUD = 115200,\n    parameter integer RIGHT_TIMBRE = 0')
t=replace_once(t,'    output wire [6:0] voice_note','''    output wire [6:0] voice_note,
    input wire [159:0] timbre_gain_q8,
    input wire [31:0] timbre_voice_mask,
    output wire monitor_valid,
    output wire signed [23:0] monitor_pcm''')
t=replace_once(t,'    tdm_engine #(','    tdm_engine_rh #(')
t=replace_once(t,'.PART(P), .FINGER_EXPR(FINGER_EXPR), .EXPLICIT_START(1)',
 '.PART(P), .FINGER_EXPR(FINGER_EXPR), .EXPLICIT_START(1), .RIGHT_TIMBRE(RIGHT_TIMBRE)')
t=replace_once(t,'        .pmod_cfg(pmod_cfg),','        .pmod_cfg(pmod_cfg),\n        .timbre_gain_q8(timbre_gain_q8), .timbre_voice_mask(timbre_voice_mask),')
t=replace_once(t,'endmodule','assign monitor_valid=sample_en;\nassign monitor_pcm=audio;\nendmodule')
(ROOT/'engine/tdm_top_rh.v').write_text(t,encoding='utf-8')
print('Created opt-in candidate engine/top; originals unchanged')
