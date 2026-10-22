`timescale 1ns/1ps
module tb_finger_pitch;
    reg clk=0, rst_n=0;
    always #5 clk=~clk;
    reg cv=0; reg [1:0] cmd=0;
    reg [4:0] fid=0, grp=0;
    reg signed [11:0] pos=0;
    reg vv=0, von=0; reg [4:0] vg=0;
    reg [31:0] va=32'hffffffff;
    wire [31:0] active;
    wire [575:0] offsets;
    finger_pitch u(.clk(clk),.rst_n(rst_n),.cmd_valid(cv),.cmd(cmd),
        .finger(fid),.group(grp),.position(pos),.voice_valid(vv),
        .voice_on(von),.voice_group(vg),.voice_active(va),
        .expr_active(active),.expr_offsets(offsets));
    task send;
        input [1:0] c; input [4:0] f,g; input signed [11:0] p;
        begin
            @(negedge clk); cv=1;cmd=c;fid=f;grp=g;pos=p;
            @(negedge clk); cv=0;
        end
    endtask
    task check;
        input integer g, want;
        begin
            if($signed(offsets[g*18 +: 18]) !== want)
                $fatal(1,"group %0d got %0d want %0d",g,$signed(offsets[g*18 +: 18]),want);
        end
    endtask
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        send(0,1,0,100); send(0,2,31,-100);
        send(1,1,0,356); check(0,65536); check(31,0);
        send(1,2,0,-356); check(31,-32768); check(0,65536);
        send(1,1,0,2047); check(0,65536);
        send(1,1,0,-2048); check(0,-32768);
        send(1,1,0,100); check(0,0);
        send(2,2,0,0); send(1,2,0,0); check(31,-32768);
        // Release tail retains pitch; reuse drops old ownership and expression.
        @(negedge clk); vv=1;von=1;vg=0;
        @(negedge clk); vv=0;
        send(1,1,0,356); check(0,0);
        if(active[0]) $fatal(1,"reused group remains controlled");
        // Same-clock allocation notification wins over a bind.
        @(negedge clk); vv=1;von=1;vg=0;cv=1;cmd=0;fid=3;grp=0;pos=0;
        @(negedge clk); vv=0;cv=0;
        send(1,3,0,256); check(0,0);
        va[3]=0; send(0,4,3,0);
        if(active[3]) $fatal(1,"bound inactive group");
        // Moving one contact to another group revokes its old ownership.
        send(0,5,4,0);send(1,5,0,256);send(0,5,5,0);send(1,5,0,-256);
        check(4,65536);check(5,-32768);
        @(negedge clk); rst_n=0;
        @(negedge clk);
        if(active!==0 || offsets!==0) $fatal(1,"reset left expression");
        $display("PASS finger_pitch: independent groups 0/31, anchors, clamps, release, reuse, races, reset");
        $finish;
    end
endmodule
