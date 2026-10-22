from common import *
p=R/'engine/src/pitch_mod.v';s=(R/'reference/pitch_mod.v').read_text(encoding='utf-8')
s=s.replace('reg [$clog2(NG)-1:0] sweep;','')
s=s.replace('reg signed [QW-1:0] gq [0:NG-1];','''// Separate single-write banks permit asynchronous distributed RAM inference.
    // Metadata, not data RAM, resets. A command wins if both write one group.
    reg [$clog2(NG)-1:0] sweep;
    reg signed [QW-1:0] command_mem [0:NG-1];
    reg signed [QW-1:0] materialized_mem [0:NG-1];
    reg [NG-1:0] initialized,from_command;
    wire signed [QW-1:0] sweep_gq=initialized[sweep]?
        (from_command[sweep]?command_mem[sweep]:materialized_mem[sweep]):{QW{1'b0}};
    wire signed [QW-1:0] read_gq=initialized[rd_note]?
        (from_command[rd_note]?command_mem[rd_note]:materialized_mem[rd_note]):{QW{1'b0}};
    // Debug view retained for sampled old-source comparisons, unused in datapath.
    wire signed [QW-1:0] gq [0:NG-1];
    genvar gi;
    generate for(gi=0;gi<NG;gi=gi+1)begin: logical_store
        assign gq[gi]=initialized[gi]?(from_command[gi]?command_mem[gi]:materialized_mem[gi]):{QW{1'b0}};
    end endgenerate''')
s=s.replace('for(n=0;n<NG;n=n+1)gq[n]<=0;','initialized<=0;from_command<=0;')
s=s.replace('if(pending[sweep])begin gq[sweep]<=advance(gq[sweep],step_held);pending[sweep]<=0;end',
 '''if(pending[sweep])begin
                    pending[sweep]<=0;initialized[sweep]<=1;from_command[sweep]<=0;
                end''')
s=s.replace("if(gw_en===1'b1)begin gq[gw_note]<=gw_val;pending[gw_note]<=0;end", "if(gw_en===1'b1)begin initialized[gw_note]<=1;from_command[gw_note]<=1;pending[gw_note]<=0;end")
s=s.replace('wire signed [QW-1:0] logical_gq=pending[rd_note]?advance(gq[rd_note],step_held):gq[rd_note];', '''always @(posedge clk)begin
        if(rst_n)begin
            if(!sample_en && busy && pending[sweep])materialized_mem[sweep]<=advance(sweep_gq,step_held);
            if(gw_en===1'b1)command_mem[gw_note]<=gw_val;
        end
    end
    wire signed [QW-1:0] logical_gq=pending[rd_note]?advance(read_gq,step_held):read_gq;''')
p.write_text(s,encoding='utf-8')
print('Implemented two single-write banks; no output cycle or arithmetic change')
