`timescale 1ns/1ps
module tb_renderer;
mv_renderer_before gold(.clk(1'b0),.rst_n(1'b1));
mv_renderer dut(.clk(1'b0),.rst_n(1'b1));
integer bank,seen,x,y,n=0;
reg [15:0] a,b;
initial begin
 for(bank=0;bank<16;bank=bank+1)for(seen=0;seen<2;seen=seen+1) begin
  gold.frame_layers=bank;dut.frame_layers=bank;
  gold.frame_seen=seen;dut.frame_seen=seen;
  for(y=0;y<512;y=y+1)for(x=0;x<512;x=x+1)begin
   a=gold.background(x[8:0],y[8:0]);b=dut.background(x[8:0],y[8:0]);
   if(a!==b)$fatal(1,"pixel mismatch x=%0d y=%0d bank=%0d seen=%0d old=%h new=%h",x,y,bank,seen,a,b);
   n=n+1;
  end
 end
 $display("PASS exhaustive renderer %0d pixels, all x/y/layers/seen",n);$finish;
end
endmodule
