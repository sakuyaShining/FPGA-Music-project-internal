// Exact RAM16SDP4 functional definition copied from installed vendor simulation library.
module RAM16SDP4 (DO, DI, WAD, RAD, WRE, CLK);

input CLK;
input WRE;

input [3:0] WAD;
input [3:0] DI;
input [3:0] RAD;
output [3:0] DO;

parameter INIT_0 = 16'h0000;
parameter INIT_1 = 16'h0000;
parameter INIT_2 = 16'h0000;
parameter INIT_3 = 16'h0000;

reg [15:0] mem0;
reg [15:0] mem1;
reg [15:0] mem2;
reg [15:0] mem3;

initial begin
	mem0 = INIT_0;
	mem1 = INIT_1;
	mem2 = INIT_2;
	mem3 = INIT_3;
end

assign DO[0] = mem0[RAD];
assign DO[1] = mem1[RAD];
assign DO[2] = mem2[RAD];
assign DO[3] = mem3[RAD];

always @(posedge CLK) begin
	if (WRE) begin
		mem0[WAD] <= DI[0];
		mem1[WAD] <= DI[1];
		mem2[WAD] <= DI[2];
		mem3[WAD] <= DI[3];
	end
end

endmodule
