`timescale 1ns/1ps
module tb_board_test;
 reg clk=0,rst_n=0,rx=1;
 always #18.5185 clk=~clk;
 wire tx;
 wire [15:0] pad;
 tdm_board_test dut(.clk(clk),.rst_n(~rst_n),.uart_rx_pin(rx),.uart_tx_pin(tx),.pad(pad));
 defparam dut.u_top.board_observer.u_diag.CAPTURE_SAMPLES=16;
 integer fails=0;
 task check;
 input [255:0] label;input integer got,want;
 begin if(got!==want) begin $display("FAIL %0s got=%0d expected=%0d",label,got,want);fails=fails+1;end
 else if(label!="stop") $display("PASS %0s",label);end endtask
 task send_byte;
 input[7:0] value;integer k;
 begin @(negedge clk);rx=0;repeat(234) @(negedge clk);
 for(k=0;k<8;k=k+1) begin rx=value[k];repeat(234) @(negedge clk);end
 rx=1;repeat(234) @(negedge clk);end endtask
 task write_reg;
 input[7:0] addr,value;
 begin send_byte(addr);send_byte(value);repeat(10) @(negedge clk);end endtask
 task receive;
 output[7:0] value;integer k,guard;
 begin guard=0;while(tx!==0 && guard<12000) begin @(posedge clk);guard=guard+1;end
 if(guard==12000) begin fails=fails+1;$display("FAIL UART timeout");end
 repeat(351) @(posedge clk);
 for(k=0;k<8;k=k+1) begin value[k]=tx;repeat(234) @(posedge clk);end
 check("stop",tx,1);end endtask
 reg[7:0] address_byte,data_byte;
 reg[7:0] stream_byte;
 reg[23:0] stream_expected0,stream_expected1;
 task read_check;
 input[7:0] addr,value;
 begin fork write_reg(8'h0f,addr);begin receive(address_byte);receive(data_byte);end join
 check("read address",address_byte,addr);check("read value",data_byte,value);
 repeat(300) @(negedge clk);end endtask
 integer k;
 initial begin
 repeat(20) @(negedge clk);rst_n=1;repeat(600) @(negedge clk);
 read_check(8'hA4,8'hD3);read_check(8'hA5,2);
 read_check(8'h7F,8'h11);read_check(8'hA9,32);
 write_reg(8'h83,1);read_check(8'h89,0);
 write_reg(8'h00,8'h08);read_check(8'h00,8'h08);
 write_reg(8'hB0,5);read_check(8'h00,8'h08);
 write_reg(8'h60,8'hBC);write_reg(8'h61,15);
 write_reg(8'h83,1);read_check(8'h83,1);read_check(8'h85,1);read_check(8'h89,1);
 write_reg(8'hB0,0);write_reg(8'hB1,0);write_reg(8'hB2,0);write_reg(8'hB3,0);write_reg(8'hB4,0);
 write_reg(8'h83,1);read_check(8'h94,1);
 write_reg(8'hB2,16);write_reg(8'hB4,1);
 check("finger update did not note-on",dut.u_top.board_observer.u_diag.on_count,1);
 write_reg(8'h60,8'hC0);write_reg(8'h61,15);
 write_reg(8'hB0,1);write_reg(8'hB1,1);write_reg(8'hB2,0);write_reg(8'hB3,0);write_reg(8'hB4,0);
 write_reg(8'hB2,8'hF0);write_reg(8'hB3,15);write_reg(8'hB4,1);
 check("two independent owners",dut.u_top.finger_active[1:0],3);
 check("first offset stays positive",$signed(dut.u_top.finger_offsets[17:0])>0,1);
 check("second offset negative",$signed(dut.u_top.finger_offsets[35:18])<0,1);
 write_reg(8'h60,64);write_reg(8'h61,15);
 write_reg(8'h80,1);repeat(9000) @(negedge clk);
 read_check(8'h80,2);read_check(8'h81,16);
 for(k=0;k<16;k=k+1) begin
 if(^dut.u_top.board_observer.u_diag.capture_mem[k]===1'bx) begin fails=fails+1;$display("FAIL capture X");end
 end
 read_check(8'h90,0);read_check(8'h91,2);read_check(8'h92,0);read_check(8'h93,2);
 write_reg(8'h60,60);write_reg(8'h61,15);write_reg(8'h83,1);
 read_check(8'h83,4);read_check(8'h87,2);read_check(8'h89,0);read_check(8'h94,3);
 // Expression remains enabled on release tail; ownership is revoked, not pitch.
 write_reg(8'h60,8'hBC);write_reg(8'h61,15);write_reg(8'h83,1);read_check(8'h94,2);
 stream_expected0=dut.u_top.board_observer.u_diag.capture_mem[0];
 stream_expected1=dut.u_top.board_observer.u_diag.capture_mem[1];
 fork
 write_reg(8'h0f,8'ha8);
 begin
 receive(stream_byte);check("stream tag",stream_byte,8'ha8);
 receive(stream_byte);check("stream sample0 low",stream_byte,stream_expected0[7:0]);
 receive(stream_byte);check("stream sample0 mid",stream_byte,stream_expected0[15:8]);
 receive(stream_byte);check("stream sample0 high",stream_byte,stream_expected0[23:16]);
 receive(stream_byte);check("stream sample1 low",stream_byte,stream_expected1[7:0]);
 receive(stream_byte);check("stream sample1 mid",stream_byte,stream_expected1[15:8]);
 receive(stream_byte);check("stream sample1 high",stream_byte,stream_expected1[23:16]);
 for(k=6;k<6144;k=k+1) receive(stream_byte);
 end
 join
 rst_n=0;repeat(20) @(negedge clk);rst_n=1;repeat(600) @(negedge clk);
 write_reg(8'h83,1);read_check(8'h83,0);read_check(8'h89,0);read_check(8'h80,0);
 write_reg(8'h00,8'h08);
 write_reg(8'h60,8'hFF);write_reg(8'h61,15);
 write_reg(8'h60,8'hBC);write_reg(8'h61,15);
 check("MIDI127 and60 independent",dut.u_top.nm_active,3);
 write_reg(8'h60,127);write_reg(8'h61,15);
 check("MIDI127 off preserves60",dut.u_top.nm_active,2);
 write_reg(8'h60,60);write_reg(8'h61,15);
 check("MIDI127 corner cleanup",dut.u_top.nm_active,0);
 // The board-test endpoint must retain all 32 groups and IDs, not two only.
 write_reg(8'h00,8'h08);
 for(k=0;k<32;k=k+1) begin write_reg(8'h60,8'h80+40+k);write_reg(8'h61,15);end
 check("32 active notes",dut.u_top.nm_active,32'hffffffff);
 write_reg(8'hB0,31);write_reg(8'hB1,31);write_reg(8'hB2,0);write_reg(8'hB3,0);write_reg(8'hB4,0);
 write_reg(8'hB2,16);write_reg(8'hB4,1);
 check("group31 expression enabled",dut.u_top.finger_active[31],1);
 check("group31 offset positive",$signed(dut.u_top.finger_offsets[31*18 +: 18])>0,1);
 write_reg(8'h60,71);write_reg(8'h61,15);
 write_reg(8'h60,8'hD4);write_reg(8'h61,15);
 check("reused group clears expression",dut.u_top.finger_active[31],0);
 write_reg(8'hB2,32);write_reg(8'hB4,1);
 check("old finger cannot move reused group",dut.u_top.finger_offsets[31*18 +: 18],0);
 for(k=0;k<31;k=k+1) begin write_reg(8'h60,40+k);write_reg(8'h61,15);end
 write_reg(8'h60,84);write_reg(8'h61,15);
 check("all notes released",dut.u_top.nm_active,0);
 if(fails==0) $display("RESULT board_test=PASS");else $display("RESULT board_test=FAIL fails=%0d",fails);
 $finish;
 end
 initial begin #1_000_000_000;$display("RESULT board_test=TIMEOUT");$finish;end
endmodule
