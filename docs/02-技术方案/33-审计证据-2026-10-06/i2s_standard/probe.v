`timescale 1ns/1ps
module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0;
wire be,bck,lr,se,sd,ws;
audio_clk_en #(.DIV_BCK(16),.BCK_PER_LRCK(32)) c(clk,rst_n,be,bck,lr,se);
i2s_tx t(clk,rst_n,be,lr,se,24'h123400,sd,ws);
reg last_ws=0; integer n=0; reg [15:0] word=0; integer count=0;
always @(posedge bck) if(rst_n) begin
  word={word[14:0],sd}; n=n+1;
  if(ws!=last_ws) begin
    if(count>2) $display("standard_I2S expected=1234 received=%h bits=%0d",word,n);
    count=count+1; last_ws=ws; n=0;
  end
end
initial begin #23 rst_n=1; #30000 $finish; end
endmodule