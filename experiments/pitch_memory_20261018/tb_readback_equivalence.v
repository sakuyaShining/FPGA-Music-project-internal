`timescale 1ns/1ps
module tb_readback_equivalence;
 reg clk=0;always #5 clk=~clk;reg rst_n=1;
 reg inject_we=0,inject_done=0;reg [7:0] inject_wa=0,inject_wd=0;
 wire oldtx,newtx;tri [15:0] oldpad,newpad;
`define PORTS(PAD,TX) .clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(TX),.test_mode(1'b0),.preset(2'd0),.pad(PAD),.board_status(8'd0),.board_case(8'd0),.cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(88'd0),.own_valid(1'b0),.own_on(1'b0),.own_note(7'd0),.own_vel(4'd0),.own_instance(13'd0),.own_preset(2'd0),.ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),.finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),.timbre_gain_q8(160'd0),.timbre_voice_mask(32'd0)
 tdm_top_reference #(.LEGACY_PAD(0),.UART_BAUD(1687500),.LIVE_MONITOR(0)) oldtop(`PORTS(oldpad,oldtx));
 tdm_top_owned #(.LEGACY_PAD(0),.UART_BAUD(1687500),.LIVE_MONITOR(0)) newtop(`PORTS(newpad,newtx));
`undef PORTS
 integer n,seed=782018,replies=0,adjacent=0,sameedge=0;reg [31:0] r;reg [255:0] seen=0;
 initial begin
  force oldtop.wr_en=inject_we;force newtop.wr_en=inject_we;
  force oldtop.wr_addr=inject_wa;force newtop.wr_addr=inject_wa;
  force oldtop.wr_data=inject_wd;force newtop.wr_data=inject_wd;
  force oldtop.tx_done=inject_done;force newtop.tx_done=inject_done;
  #1;rst_n=0;repeat(4)@(negedge clk);rst_n=1;
  for(n=0;n<50000;n=n+1)begin
   @(negedge clk);r=$random(seed);inject_done=1;
   inject_we=0;inject_wa=r[15:8];inject_wd=r[23:16];
   case(oldtop.rb_st)
    0:begin inject_we=1;inject_wa=8'h0f;inject_wd=replies;end
    2:begin inject_we=1;inject_wa=oldtop.rb_addr;inject_wd=r[7:0];adjacent=adjacent+1;end
    3:begin
     // A current-edge write must NOT replace the pre-edge reply value.
     inject_we=1;inject_wa=oldtop.rb_addr;inject_wd=r[7:0];sameedge=sameedge+1;
     seen[oldtop.rb_addr]=1;replies=replies+1;
    end
    default:begin inject_we=r[0];end
   endcase
   if(n>1000 && n%4093==0)rst_n=0;
   if(n>1000 && n%4093==3)rst_n=1;
   @(posedge clk);#1;
   if({oldtop.rb_st,oldtop.rb_addr,oldtop.tx_start,oldtop.tx_data}!=={newtop.rb_st,newtop.rb_addr,newtop.tx_start,newtop.tx_data})
    $fatal(1,"readback FSM mismatch cycle=%0d addr=%h state=%0d old=%h new=%h",n,oldtop.rb_addr,oldtop.rb_st,oldtop.tx_data,newtop.tx_data);
   if(oldtx!==newtx)$fatal(1,"UART pin mismatch");
  end
  if(seen!=={256{1'b1}}||adjacent<1000||sameedge<1000)$fatal(1,"coverage missing");
  $display("PASS readback_equivalence cycles=%0d replies=%0d all256_addresses previous_edge_writes=%0d same_edge_writes=%0d",n,replies,adjacent,sameedge);$finish;
 end
endmodule
