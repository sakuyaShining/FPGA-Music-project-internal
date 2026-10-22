`timescale 1ns/1ps
module anchor_case #(parameter MB=0,NF=32)(output reg done=0);
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,cmd_valid=0,voice_valid=0,voice_on=0;
    reg [1:0] cmd=0;
    reg [$clog2(NF)-1:0] finger=0;
    reg [4:0] group=0,voice_group=0;
    reg signed [11:0] position=0;
    reg [31:0] voice_active=0;
    wire [31:0] a,b;
    wire [575:0] x,y;
    finger_pitch #(.NF(NF),.MULTI_BIND(MB)) dut(.clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd(cmd),.finger(finger),.group(group),.position(position),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_active(voice_active),.expr_active(a),.expr_offsets(x));
    finger_pitch_reference #(.NF(NF),.MULTI_BIND(MB)) ref_impl(.clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd(cmd),.finger(finger),.group(group),.position(position),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_active(voice_active),.expr_active(b),.expr_offsets(y));
    integer i,j,k,checks=0,binds=0,moves=0,releases=0,races=0;
    reg [31:0] rng=32'h71a6c981+MB+NF;
    task random_step;begin rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);end endtask
    task check;
        begin
            #1;
            if(a!==b||x!==y||dut.owned!==ref_impl.owned||dut.moving_anchor!==ref_impl.moving_anchor)$fatal(1,"anchor mismatch MB=%0d NF=%0d step=%0d",MB,NF,checks);
            for(j=0;j<32;j=j+1)begin
                if(dut.owner[j]!==ref_impl.owner[j])$fatal(1,"owner mismatch");
                if(ref_impl.owned[j]&&dut.contact_anchor[ref_impl.owner[j]]!==ref_impl.anchor[j])$fatal(1,"anchor invariant");
            end
            checks=checks+1;
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;voice_active=32'hffffffff;
        // Every group belongs to a shared finger, then saturating/negative moves.
        for(i=0;i<32;i=i+1)begin @(negedge clk);cmd_valid=1;cmd=0;finger=1;group=i;position=i*11;@(posedge clk);check;end
        for(i=0;i<8;i=i+1)begin @(negedge clk);cmd=1;position=(i&1)?-2048:2047;@(posedge clk);check;end
        for(k=0;k<50000;k=k+1)begin
            @(negedge clk);random_step;cmd_valid=rng[0]|rng[4];cmd=rng[2:1];finger=rng[7:3];group=rng[12:8];position=rng[24:13];
            random_step;voice_valid=rng[0];voice_on=rng[1];voice_group=rng[6:2];voice_active=rng;
            if(k%17==0)begin voice_group=group;voice_valid=1;end
            if(k==10000||k==30000)rst_n=0;else rst_n=1;
            if(cmd_valid)case(cmd)0:binds=binds+1;1:moves=moves+1;2:releases=releases+1;endcase
            if(cmd_valid&&voice_valid)races=races+1;
            @(posedge clk);check;
        end
        $display("PASS anchor_equiv MB=%0d NF=%0d clocks=%0d groups_checked=%0d binds=%0d moves=%0d releases=%0d concurrent_voice=%0d",MB,NF,checks,checks*32,binds,moves,releases,races);done=1;
    end
endmodule
module tb_anchor_equiv;
    wire a,b,c;
    anchor_case #(.MB(0)) a0(a);anchor_case #(.MB(1)) a1(b);anchor_case #(.MB(1),.NF(5)) a2(c);
    initial begin wait(a&&b&&c);$display("PASS anchor all modes and padded contact addresses");$finish;end
    initial begin #6000000;$fatal(1,"watchdog");end
endmodule
