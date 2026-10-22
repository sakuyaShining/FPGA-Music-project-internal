// Two independently addressed asynchronous read ports, replicated single-write
// distributed RAM. No reset; pitch_mod metadata masks all uninitialized entries.
// Target: GW2AR RAM16SDP4. The vendor model is compiled only by test scripts.
module pitch_native_store #(parameter NG=32,QW=18)(
 input wire clk,we,input wire [$clog2(NG)-1:0] wa,ra,rb,
 input wire [QW-1:0] data,output wire [QW-1:0] qa,qb
);
 localparam WORDS=(NG+15)/16,GROUPS=(QW+3)/4,PW=GROUPS*4;
 wire [PW-1:0] padded={{(PW-QW){1'b0}},data};
 wire [7:0] wide_wa=wa,wide_ra=ra,wide_rb=rb;
 wire [PW-1:0] a[0:WORDS-1],b[0:WORDS-1];
 genvar k,j;
 generate for(k=0;k<WORDS;k=k+1)begin: bank
  for(j=0;j<GROUPS;j=j+1)begin: nibble
   RAM16SDP4 first(.DO(a[k][j*4+:4]),.DI(padded[j*4+:4]),.WAD(wide_wa[3:0]),.RAD(wide_ra[3:0]),.WRE(we&&((wide_wa>>4)==k)),.CLK(clk));
   RAM16SDP4 second(.DO(b[k][j*4+:4]),.DI(padded[j*4+:4]),.WAD(wide_wa[3:0]),.RAD(wide_rb[3:0]),.WRE(we&&((wide_wa>>4)==k)),.CLK(clk));
  end
 end endgenerate
 assign qa=a[wide_ra>>4][QW-1:0];
 assign qb=b[wide_rb>>4][QW-1:0];
endmodule
