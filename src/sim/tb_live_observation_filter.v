`timescale 1ns/1ps
module tb_live_observation_filter;
    reg clk=0,rst_n=0,en=0;
    reg signed [23:0] sample=0;
    wire valid;
    wire signed [23:0] filtered;
    reg signed [15:0] inputs[0:4095];
    integer i,fd,count=0;
    always #5 clk=~clk;
    live_observation_filter dut(.clk(clk),.rst_n(rst_n),.sample_en(en),.sample(sample),.valid(valid),.filtered(filtered));
    always @(negedge clk) if(valid) begin $fdisplay(fd,"%0d",$signed(filtered)>>>8);count=count+1;end
    initial begin
        $readmemh("filter-input.hex",inputs);fd=$fopen("filter-output.txt","w");
        repeat(10) @(negedge clk);rst_n=1;
        for(i=0;i<4096;i=i+1) begin
            @(negedge clk);en=1;sample={inputs[i],8'b0};
            @(negedge clk);en=0;repeat(510) @(negedge clk);
        end
        repeat(300) @(negedge clk);
        if(count!=1024) $fatal(1,"decimation count %d",count);
        $fclose(fd);$display("RESULT observation_filter=PASS");$finish;
    end
endmodule
