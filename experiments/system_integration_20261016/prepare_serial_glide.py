"""Opt-in resource variant; original and base integration inputs are preserved.

Lazy epoch flags make every read see the original simultaneous sample update,
while two shared arithmetic units replace 32 parallel decay arithmetic copies.
Requires sample_en spacing >=NG+1 clocks (actual music chain uses512).
"""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent;D=R/'optimization';D.mkdir(exist_ok=True)
original=(R/'engine/pitch_mod.v').read_text(encoding='utf-8')
(D/'pitch_mod_reference.v').write_text(original.replace('module pitch_mod #(','module pitch_mod_reference #('),encoding='utf-8')
s=original.replace('    output wire signed [QW-1:0]        poff','    output reg update_overrun,\n    output wire signed [QW-1:0]        poff')
start=s.index('    always @(posedge clk or negedge rst_n) begin')
end=s.index('\n    //-------------------------------------------------------------------------',start)
old_block=s[start:end]
new_block='''    // Opt-in epoch implementation: logical reads observe the sample update
    // immediately, even before the background sweep materializes each group.
    reg [NG-1:0] pending;
    reg [$clog2(NG)-1:0] sweep;
    reg busy;
    reg [15:0] step_held;
    function signed [QW-1:0] advance;
        input signed [QW-1:0] value;
        input [15:0] step;
        reg signed [QW-1:0] positive,negative;
        begin
            positive=$signed({2'b00,step});negative=-positive;
            if(value>0)advance=(value>positive)?value-positive:{QW{1'b0}};
            else if(value<0)advance=(value<negative)?value-negative:{QW{1'b0}};
            else advance=0;
        end
    endfunction
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            pending<=0;sweep<=0;busy<=0;step_held<=0;update_overrun<=0;
            for(n=0;n<NG;n=n+1)gq[n]<=0;
        end else begin
            if(sample_en)begin
                if(|pending)update_overrun<=1;
                pending<={NG{1'b1}};step_held<=glide_step;sweep<=0;busy<=1;
            end else if(busy)begin
                if(pending[sweep])begin gq[sweep]<=advance(gq[sweep],step_held);pending[sweep]<=0;end
                if(sweep==NG-1)busy<=0;else sweep<=sweep+1'b1;
            end
            // Writes have exactly the original highest priority, including a
            // write coincident with sample_en or a sweep of that same group.
            if(gw_en===1'b1)begin gq[gw_note]<=gw_val;pending[gw_note]<=0;end
        end
    end
    wire signed [QW-1:0] logical_gq=pending[rd_note]?advance(gq[rd_note],step_held):gq[rd_note];
'''
s=s[:start]+new_block+s[end:]
old_read="wire signed [QW-1:0] gq_eff = (gw_en === 1'b1) ? gw_val : gq[rd_note];"
assert s.count(old_read)==1
s=s.replace(old_read,old_read.replace('gq[rd_note]','logical_gq'))
(D/'pitch_mod.v').write_text(s,encoding='utf-8')
base=R/'synthesis/joint';dst=R/'synthesis/joint_serial';dst.mkdir(parents=True,exist_ok=True)
for p in base.iterdir():
    if p.is_file() and p.suffix in ('.v','.vh','.hex','.gprj'):shutil.copyfile(p,dst/p.name)
shutil.copyfile(D/'pitch_mod.v',dst/'pitch_mod.v')
(dst/'synth.tcl').write_text('open_project "'+(dst/'probe.gprj').as_posix()+'"\nset_option -top_module instrument_joint_probe\nrun syn\nexit\n',encoding='utf-8')
(dst/'inputs.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.iterdir() if p.suffix in ('.v','.vh','.hex')},indent=2),encoding='utf-8')
(D/'variant.json').write_text(json.dumps(dict(status='opt-in candidate, not product replacement',original_sha256=hashlib.sha256((R/'engine/pitch_mod.v').read_bytes()).hexdigest(),variant_sha256=hashlib.sha256((D/'pitch_mod.v').read_bytes()).hexdigest(),minimum_sample_spacing_clocks=33,actual_music_spacing_clocks=512,unchanged_lfo_known_issue=True,removed_parallel_block=old_block),ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared optional shared-glide variant; base integration stays unchanged')
