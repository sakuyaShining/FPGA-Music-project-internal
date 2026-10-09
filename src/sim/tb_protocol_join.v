`timescale 1ns/1ps
// Combined candidate: register-boundary transactions + real event queues.
// UART wire encoding remains covered by evmerge and GUI frame tests.
module tb_protocol_join;
    reg clk=0;
    always #18.5185 clk=~clk;
    reg rst_n=0, ev=0, on=0;
    reg [6:0] note=0;
    reg [3:0] vel=0;
    reg we=0;
    reg [7:0] addr=0, data=0;
    wire [15:0] pad;
    tdm_top dut(.clk(clk),.rst_n(rst_n),.ev_valid(ev),.ev_on(on),.ev_note(note),.ev_vel(vel),
        .preset(2'd0),.test_mode(1'b0),.uart_rx_pin(1'b1),.uart_tx_pin(),
        .pad(pad),.led(),.dac_din(),.dac_ws(),.dac_bck(),.pa_en());
    integer failures=0, i, guard, accepted=0, offs=0;
    reg monitor_refresh=0;
    reg [7:0] first_amp[0:15];
    task check;
        input [511:0] label;
        input integer value, expected;
        begin
            if(value===expected) $display("PASS %0s",label);
            else begin $display("FAIL %0s got=%0d expected=%0d",label,value,expected); failures=failures+1; end
        end
    endtask
    task write_reg;
        input [7:0] a,d;
        begin @(negedge clk);we=1;addr=a;data=d;@(negedge clk);we=0;repeat(2) @(negedge clk);end
    endtask
    task send_note;
        input [6:0] n;
        input [3:0] v;
        begin @(negedge clk);ev=1;on=1;note=n;vel=v;@(negedge clk);ev=0;repeat(100) @(negedge clk);end
    endtask
    always @(negedge clk) if(rst_n) begin
        if(dut.nm_ev_ack) begin
            accepted=accepted+1;
            if(!dut.ev_on_r) offs=offs+1;
        end
        if(dut.nm_load_en && dut.nm_load_slot<16) begin
            if(monitor_refresh) check("refresh-keeps-original-velocity",dut.nm_load_amp,first_amp[dut.nm_load_slot]);
            else first_amp[dut.nm_load_slot]=dut.nm_load_amp;
        end
    end
    initial begin
        force dut.uart_wr_en=we;force dut.uart_wr_addr=addr;force dut.uart_wr_data=data;
        repeat(10) @(negedge clk);rst_n=1;repeat(2000) @(negedge clk);
        check("protocol-version",dut.R[8'h7f*8 +:8],8'h11);
        send_note(60,12);send_note(64,4);
        check("two-different-velocities",dut.u_nm.group_velocity[0],192);
        check("second-velocity",dut.u_nm.group_velocity[1],64);
        monitor_refresh=1;write_reg(8'h63,0);repeat(200) @(negedge clk);monitor_refresh=0;
        write_reg(8'h5A,8'h80);
        for(i=0;i<16;i=i+1) begin write_reg(8'h58,i);write_reg(8'h59,i+17);end
        for(i=0;i<16;i=i+1) check("draft-not-published",dut.u_nm.spec_ram[i],0);
        send_note(67,8);
        write_reg(8'h5A,1);
        repeat(100) @(negedge clk);
        for(i=0;i<16;i=i+1) check("whole-spectrum-published",dut.u_nm.spec_ram[i],i+17);
        check("newest-source-queue-depth",dut.SRCQ_DEPTH,4);
        check("no-unexpected-drops",dut.ev_drop_status,0);
        // Two downloads start at index 0; 0x72 remains reserved.
        write_reg(8'h73,0);write_reg(8'h70,60);write_reg(8'h71,1);
        check("first-download-advance",dut.s_idx,1);
        write_reg(8'h73,0);check("second-download-reset",dut.s_idx,0);
        write_reg(8'h70,72);write_reg(8'h71,1);write_reg(8'h73,1);
        write_reg(8'h50,1);repeat(2000) @(negedge clk);
        check("sequencer-started",dut.u_seq.started,1);
        write_reg(8'h50,0);repeat(500) @(negedge clk);
        check("stop-off-arrives-after-disable",offs,1);
        write_reg(8'h50,0);repeat(100) @(negedge clk);check("repeated-stop-no-duplicate",offs,1);
        check("active-before-reset",dut.nm_active!=0,1);
        rst_n=0;repeat(4) @(negedge clk);rst_n=1;repeat(2000) @(negedge clk);
        check("reset-clears-active-voices",dut.nm_active,0);
        for(i=0;i<32;i=i+1) check("reset-clears-note-identity",dut.u_nm.gtab[i],127);
        if(failures==0) $display("RESULT protocol_join=PASS");
        else $display("RESULT protocol_join=FAIL failures=%0d",failures);
        $finish;
    end
    initial begin #20000000;$display("RESULT protocol_join=TIMEOUT");$finish;end
endmodule
