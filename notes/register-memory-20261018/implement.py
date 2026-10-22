from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parents[2]/'experiments/register_memory_20261018'
old=(R/'reference/reg_bank_original.v').read_text(encoding='utf-8')
defaults=[0]*128
for a,v in re.findall(r"mem\[8'h([0-9A-Fa-f]+)\]\s*=\s*8'h([0-9A-Fa-f]+)",old):defaults[int(a,16)]=int(v,16)
top=(R/'reference/tdm_top_owned_original.v').read_text(encoding='utf-8')
addresses=sorted({int(a,16) for a in re.findall(r"R\[8'h([0-9A-Fa-f]+)\*8\s*\+:",top)})
mask=sum(1<<a for a in addresses)
initial=''.join('%02x'%v for v in defaults[::-1])
code='''// Stage78: full 128-byte synchronous readback in RAM, selected live mirrors.
// No reset on parameter memory/mirrors. Read is one edge, read-before-write.
// Unselected flat bytes are intentionally zero and must have no consumers.
`timescale 1ns/1ps
module reg_bank_compact #(
 parameter [127:0] FLAT_MASK=128'hMASK
)(
 input wire clk,rst_n,wr_en,
 input wire [7:0] wr_addr,wr_data,
 input wire rd_en,
 input wire [7:0] rd_addr,
 output wire [7:0] rd_data,
 output wire [1023:0] regs_flat
);
 localparam [1023:0] DEFAULTS=1024'hDEFAULTS;
 reg [7:0] mem[0:127];
 genvar g;
 generate for(g=0;g<128;g=g+1)begin: BYTES
  initial mem[g]=DEFAULTS[g*8+:8];
  if(FLAT_MASK[g])begin: LIVE
   reg [7:0] value;
   initial value=DEFAULTS[g*8+:8];
   always @(posedge clk) if(wr_en && wr_addr==g) value<=wr_data;
   assign regs_flat[g*8+:8]=value;
  end else begin: UNUSED
   assign regs_flat[g*8+:8]=8'd0;
  end
 end endgenerate
 always @(posedge clk) if(wr_en && !wr_addr[7]) mem[wr_addr[6:0]]<=wr_data;
 // Keep asynchronous output reset outside the RAM primitive. The RAM itself
 // is never reset. Out-of-range reads preserve the reference simulation X.
 reg [7:0] read_raw;
 reg read_valid;
 always @(posedge clk) if(rd_en)begin
  if(!rd_addr[7]) read_raw<=mem[rd_addr[6:0]];
  else read_raw<=8'hxx;
 end
 always @(posedge clk or negedge rst_n)
  if(!rst_n) read_valid<=1'b0;
  else if(rd_en) read_valid<=1'b1;
 assign rd_data=read_valid ? read_raw : 8'd0;
endmodule
'''.replace('128\'hMASK',"128'h%032x"%mask).replace("1024'hDEFAULTS","1024'h"+initial)
(R/'src/reg_bank_compact.v').write_text(code,encoding='utf-8')
start=top.index('    reg_bank #(.AW(8), .DW(8), .NW(128)) u_reg (')
end=top.index('\n    );',start)+len('\n    );')
top=top[:start]+'''    // Stage78: preserve only statically consumed bytes as parallel mirrors.
    // Every writable byte remains in RAM for synchronous UART readback.
    localparam [127:0] REG_LIVE_MASK=128'hMASK;
    wire reg_write = wr_en && !(wr_addr >= 8'h74 && wr_addr <= 8'h7C);
    wire [7:0] reg_read_addr, reg_read_data;
    reg_bank_compact #(.FLAT_MASK(REG_LIVE_MASK)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(reg_write), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(1'b1), .rd_addr(reg_read_addr), .rd_data(reg_read_data),
        .regs_flat(R)
    );'''.replace('128\'hMASK',"128'h%032x"%mask)+top[end:]
anchor='    reg  [7:0]  tx_data;'
insert='''
    assign reg_read_addr=rb_addr;
    // The UART state3 historically sampled the pre-edge flat value. A RAM
    // sample from the preceding edge needs that edge's write forwarded.
    // A write on the current state3 edge still takes effect AFTER the reply
    // is sampled, exactly as before. rb_addr is stable through states1..3.
    reg reg_read_forward;
    reg [7:0] reg_read_forward_data;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin reg_read_forward<=0; reg_read_forward_data<=0; end
        else begin
            reg_read_forward<=reg_write && wr_addr==rb_addr && !wr_addr[7];
            reg_read_forward_data<=wr_data;
        end
    end
    wire [7:0] reg_reply=reg_read_forward ? reg_read_forward_data : reg_read_data;
'''
assert top.count(anchor)==1;top=top.replace(anchor,anchor+insert)
oldexpr="R[{rb_addr, 3'b000} +: 8]";assert top.count(oldexpr)==1;top=top.replace(oldexpr,'reg_reply')
(R/'src/tdm_top_owned.v').write_text(top,encoding='utf-8')
(R/'evidence/register-map.json').write_text(json.dumps(dict(live_addresses=addresses,live_mask='%032x'%mask,defaults=defaults,unused_flat_bytes='zero; no consumers permitted',full_readback_bytes=128),indent=2),encoding='utf-8')
print('Prepared compact bank:',len(addresses),'live bytes and 128-byte readback')
