// Four volatile slots, two banks per slot. Commit needs all 16 words.
// Writes target the inactive bank; allocator serializes admission and commit.
module instrument_table(
    input wire clk,rst_n,valid,commit,
    input wire [1:0] slot,
    input wire [3:0] part,
    input wire [47:0] word,
    output reg applied,error,
    output reg [3:0] enabled,banks,
    input wire [6:0] read_addr,
    output reg [47:0] read_word
);
    reg [47:0] words[0:127];
    reg [15:0] written[0:3];
    // Synchronous read permits BSRAM inference instead of a large LUT memory.
    always @(posedge clk)read_word<=words[read_addr];
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            applied<=0;error<=0;enabled<=0;banks<=0;
            for(i=0;i<4;i=i+1)written[i]<=0;
        end else begin
            applied<=0;error<=0;
            if(valid)begin
                if(commit)begin
                    if(&written[slot])begin
                        banks[slot]<=!banks[slot];enabled[slot]<=1;written[slot]<=0;applied<=1;
                    end else error<=1;
                end else if(word[23])error<=1;
                else begin words[{slot,!banks[slot],part}]<=word;written[slot][part]<=1;end
            end
        end
    end
endmodule
