// Stage78: full 128-byte synchronous readback in RAM, selected live mirrors.
// No reset on parameter memory/mirrors. Read is one edge, read-before-write.
// Unselected flat bytes are intentionally zero and must have no consumers.
//
// ---------------------------------------------------------------------------
// 2026-10-23 板上实测补充（这两条都踩过，别再踩）
// ---------------------------------------------------------------------------
// 【1】两套存储，作用完全不同 —— 回读正确 ≠ 配置生效
//       mem[0:127] : 只服务回读。任何 addr<0x80 的写入都进这里。
//       value      : 只服务逻辑（regs_flat），**仅当 FLAT_MASK[g]=1 才存在**。
//     所以"写进去、回读对"完全不代表逻辑看得见。
//     实测：0x6F VEL_SHIFT 不在 mask 里，selftest 显示 0x6F=0x05 全绿，
//           但 r_vel_shift 恒为 0 ⇒ 力度只有 0/15 两档。
//     ⇒ 用 `python tools/check_live_mask.py` 兜住这一类。
//
// 【2】DEFAULTS 才是上电默认值的唯一来源
//     本模块不读 reg_bank.v 的 initial 块 —— 那是另一个模块，产品顶层
//     根本没有例化它。改 reg_bank.v 对产品毫无影响。
//     实测：改了 reg_bank.v 的 mem[8'h6E]=8'h80 之后，板上 0x6E 仍读 0x00。
//     ⇒ 默认值要么改这里的 DEFAULTS，要么写进 tdm_top_owned.v 的引导序列。
//       两处都改了：DEFAULTS 保证上电瞬间就对，引导序列保证确定性。
// ---------------------------------------------------------------------------
`timescale 1ns/1ps
module reg_bank_compact #(
 parameter [127:0] FLAT_MASK=128'h000b78011c1f03ff00ff000000000001
)(
 input wire clk,rst_n,wr_en,
 input wire [7:0] wr_addr,wr_data,
 input wire rd_en,
 input wire [7:0] rd_addr,
 output wire [7:0] rd_data,
 output wire [1023:0] regs_flat
);
 localparam [1023:0] DEFAULTS=1024'h110000000000000000000000000000000580000000000000000000000000000000000070000200000000008000027c000000000000000380004001ae6005dc010134fe0e2bffff220000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002;
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
