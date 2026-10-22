// Bus-level contract: byte order, master ACK/NACK, repeated START,
// snapshotting, clock stretch, bounded failure, reset and recovery.
`timescale 1ns/1ps
module tb_i2c_contract;
    parameter integer SCL_HZ = 100000;
    reg clk=0, rst_n=0, req=0, rd=0;
    always #10 clk=~clk;
    reg [6:0] dev=7'h5A;
    reg [7:0] reg_a=0;
    reg [15:0] wr_d=0;
    reg [1:0] wr_n=0;
    reg [2:0] rd_n=1;
    wire [31:0] rd_d;
    wire busy,done,err,scl_lo,sda_lo;
    tri1 scl,sda;
    reg external_scl_low=0,external_sda_low=0;
    assign scl=(scl_lo || external_scl_low) ? 0 : 1'bz;
    assign sda=(sda_lo || external_sda_low) ? 0 : 1'bz;
    i2c_master #(.CLK_HZ(50000000),.SCL_HZ(SCL_HZ),.STRETCH_TIMEOUT(2000)) dut
      (clk,rst_n,req,dev,rd,reg_a,wr_d,wr_n,rd_n,rd_d,busy,done,err,scl_lo,sda_lo,sda,scl);
    mpr121_model #(.ADDR(7'h5A),.PROBE(0)) slave(clk,rst_n,sda,scl,12'hAF3);
    integer failures=0,starts=0,stops=0,acks=0,nacks=0,guard;
    always @(negedge sda) if (scl===1 && rst_n) starts=starts+1;
    always @(posedge sda) if (scl===1 && rst_n) stops=stops+1;
    always @(posedge scl) if (dut.st==4 && dut.bitc==8) begin
        if(sda===0) acks=acks+1;
        else if(sda===1) nacks=nacks+1;
        else failures=failures+1;
    end
    task check;
        input [255:0] name;
        input condition;
        begin
            if(condition===1) $display("PASS %0s",name);
            else begin failures=failures+1;$display("FAIL %0s",name);end
        end
    endtask
    task launch;
        input r;input [6:0] d;input [7:0] a;input [15:0] data;input [1:0] wn;input [2:0] rn;
        begin
            @(negedge clk);rd=r;dev=d;reg_a=a;wr_d=data;wr_n=wn;rd_n=rn;req=1;
            @(negedge clk);req=0;
        end
    endtask
    task finish_xfer;
        begin
            guard=0;
            while(!done && guard<100000) begin @(negedge clk);guard=guard+1;end
            check("bounded completion",done && !busy);
            @(negedge clk);
            check("done single pulse",!done);
        end
    endtask
    task xfer;
        input r;input [6:0] d;input [7:0] a;input [15:0] data;input [1:0] wn;input [2:0] rn;
        begin launch(r,d,a,data,wn,rn);finish_xfer;end
    endtask
    integer s0,p0;
    initial begin
        repeat(10) @(negedge clk);rst_n=1;repeat(10) @(negedge clk);
        xfer(0,7'h5A,8'h20,16'hA73C,2,1);check("write two bytes",!err && slave.regs[32]==8'h3C && slave.regs[33]==8'hA7);
        xfer(0,7'h5A,8'h22,16'h52CD,2,1);
        s0=starts;p0=stops;acks=0;nacks=0;
        xfer(1,7'h5A,8'h20,0,0,4);
        check("four byte little byte-order",!err && rd_d==32'h52CDA73C);
        check("three ACK then one NACK",acks==3 && nacks==1);
        check("two START one STOP",starts-s0==2 && stops-p0==1);
        xfer(1,7'h5A,8'h20,0,0,1);check("one byte zero fill",!err && rd_d==32'h3C);
        xfer(1,7'h5A,8'h20,0,0,3);check("three bytes zero fill",!err && rd_d==32'h00CDA73C);
        xfer(1,7'h5A,0,0,0,2);check("touch two bytes",!err && rd_d==32'hAF3);
        launch(1,7'h5A,8'h20,0,0,2);
        dev=7'h33;reg_a=0;rd_n=4;rd=0;wr_n=2;wr_d=16'hFFFF;
        finish_xfer;check("request snapshot",!err && rd_d==32'hA73C);
        fork
            begin launch(1,7'h5A,8'h20,0,0,2);finish_xfer;check("stretch preserves data",!err && rd_d==32'hA73C);end
            begin wait(busy);@(negedge scl);external_scl_low=1;repeat(300) @(negedge clk);external_scl_low=0;end
        join
        xfer(1,7'h33,0,0,0,1);check("missing slave NACK",err && rd_d==0 && !scl_lo && !sda_lo);
        s0=starts;xfer(1,7'h5A,0,0,0,0);check("zero read rejected",err && starts==s0);
        xfer(1,7'h5A,0,0,0,5);check("oversized read rejected",err && starts==s0);
        xfer(0,7'h5A,0,0,3,1);check("oversized write rejected",err && starts==s0);
        external_scl_low=1;repeat(5) @(negedge clk);
        xfer(1,7'h5A,8'h20,0,0,1);check("stuck SCL times out",err && !scl_lo && !sda_lo);
        external_scl_low=0;repeat(10) @(negedge clk);
        external_sda_low=1;repeat(5) @(negedge clk);
        xfer(1,7'h5A,8'h20,0,0,1);check("busy SDA times out",err && !scl_lo && !sda_lo);
        external_sda_low=0;repeat(10) @(negedge clk);
        xfer(1,7'h5A,8'h20,0,0,1);check("error cleared on next request",!err && rd_d==32'h3C);
        launch(1,7'h5A,8'h20,0,0,4);wait(busy);@(negedge clk);rst_n=0;
        @(negedge clk);check("reset releases lines",!busy && !scl_lo && !sda_lo);
        rst_n=1;repeat(10) @(negedge clk);
        if(failures) begin $display("RESULT i2c_contract=FAIL count=%0d",failures);$finish(1);end
        $display("RESULT i2c_contract=PASS rate=%0d",SCL_HZ);$finish;
    end
    initial begin #100000000;$display("RESULT i2c_contract=FAIL timeout");$finish(1);end
endmodule
