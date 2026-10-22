`timescale 1ns/1ps
module tb_board_audio;
    localparam DIV=16;
    reg clk=0;always #5 clk=~clk;
    reg reset_button=0,rx=1;
    wire tx,din,ws,bck,pa;wire [5:0] led;
    board_audio_top #(.UART_BAUD(1687500),.WARM_CYCLES(5120),.REPORT_CYCLES(1024),.CASE_CYCLES(32768),.TAIL_CYCLES(4096),.DIAG_CAPTURE_SAMPLES(64)) dut(
        .clk(clk),.reset_button(reset_button),.uart_rx_pin(rx),.uart_tx_pin(tx),.led(led),.dac_din(din),.dac_ws(ws),.dac_bck(bck),.pa_en(pa));
    integer cycles=0,samples=0,nonzero=0,last_pcm=-1,ons=0,offs=0,moves=0,i,j,found,bytes_seen=0;
    reg [7:0] v,echo;
    reg [31:0] active;
    always @(posedge clk)if(!dut.rst_n)last_pcm=-1;else begin
        cycles=cycles+1;
        if(!dut.armed&&pa)$fatal(1,"unarmed PA");
        if(!pa&&din!==0)$fatal(1,"mute leaked DIN");
        if(dut.fault)$fatal(1,"unexpected test fault");
        if(dut.music.child_valid&&dut.music.child_ready)begin if(dut.music.child_on)ons=ons+1;else offs=offs+1;end
        if(dut.music.finger_valid&&dut.music.finger_cmd==1)moves=moves+1;
        if(dut.music.core.monitor_valid)begin
            if(last_pcm>=0&&cycles-last_pcm!=512)$fatal(1,"PCM spacing");last_pcm=cycles;samples=samples+1;
            if(cycles>5120&&(^dut.music.core.monitor_pcm)===1'bx)$fatal(1,"unknown warm PCM");
            if(dut.music.core.monitor_pcm!=0)nonzero=nonzero+1;
        end
    end
    task send_byte;input [7:0] data;integer k;begin
        @(negedge clk);rx=0;repeat(DIV)@(negedge clk);
        for(k=0;k<8;k=k+1)begin rx=data[k];repeat(DIV)@(negedge clk);end
        rx=1;repeat(DIV+3)@(negedge clk);
    end endtask
    task recv_byte;output [7:0] data;integer k;begin
        @(negedge tx);repeat(DIV+DIV/2)@(negedge clk);
        for(k=0;k<8;k=k+1)begin data[k]=tx;repeat(DIV)@(negedge clk);end
        if(tx!==1)$fatal(1,"UART stop");bytes_seen=bytes_seen+1;
    end endtask
    task write_reg;input [7:0] addr,data;begin send_byte(addr);send_byte(data);repeat(12)@(negedge clk);end endtask
    task read_reg;input [7:0] addr;output [7:0] data;begin
        fork
            begin send_byte(15);send_byte(addr);end
            begin recv_byte(echo);if(echo!==addr)$fatal(1,"UART echo");recv_byte(data);end
        join
        repeat(8)@(negedge clk);
    end endtask
    task snapshot;begin
        write_reg(8'h83,1);
        for(j=0;j<4;j=j+1)begin read_reg(8'h89+j[7:0],v);active[j*8+:8]=v;end
    end endtask
    task start_case;input [7:0] c;begin
        while(!dut.music.left_ready||(|dut.bound))@(negedge clk);
        write_reg(8'hC0,8'hA6);write_reg(8'hC1,c);repeat(3500)@(negedge clk);
        if(!dut.running||dut.test_case!=c)$fatal(1,"case not started %0d",c);
    end endtask
    initial begin
        // Cold configuration without pressing reset: power-up must remain mute.
        repeat(6000)@(negedge clk);
        read_reg(8'hC0,v);if(v!=8'h72)$fatal(1,"board profile identity");
        read_reg(8'hA4,v);if(v!=8'hD3)$fatal(1,"diagnostic identity");
        write_reg(8'hC1,3);if(dut.running||pa)$fatal(1,"case armed itself");
        start_case(3);snapshot;found=0;for(i=0;i<32;i=i+1)found=found+active[i];if(found!=2)$fatal(1,"dual not two groups");
        write_reg(8'h80,1);wait(dut.music.core.board_observer.u_diag.valid_capture);repeat(3)@(negedge clk);
        fork
            begin send_byte(15);send_byte(8'hA8);end
            begin recv_byte(v);if(v!=8'hA8)$fatal(1,"capture header");for(i=0;i<192;i=i+1)begin recv_byte(v);if((^v)===1'bx)$fatal(1,"capture X");end end
        join
        write_reg(8'hC2,0);repeat(5000)@(negedge clk);if(pa||dut.music.core.nm_active)$fatal(1,"stop did not release");
        start_case(4);repeat(10000)@(negedge clk);if(moves<2||dut.music.core.finger_offsets==0)$fatal(1,"observer stole slide path");
        write_reg(8'hC2,0);repeat(5000)@(negedge clk);
        start_case(6);snapshot;if(active!=32'hffffffff||pa)$fatal(1,"stress occupancy / mute");
        repeat(17000)@(negedge clk);write_reg(8'hC2,0);repeat(5000)@(negedge clk);if(dut.music.core.nm_active||pa)$fatal(1,"stress cleanup");
        start_case(3);repeat(2000)@(negedge clk);
        @(negedge clk);reset_button=1;repeat(4)@(negedge clk);if(dut.rst_n||pa)$fatal(1,"reset polarity");reset_button=0;
        repeat(6000)@(negedge clk);if(dut.armed||dut.running||pa||dut.music.core.nm_active)$fatal(1,"reset residual");
        if(dut.music.core.monitor_pcm!==0)$fatal(1,"reset left hidden sounding slots");
        for(i=0;i<512;i=i+1)if(dut.music.core.u_tdm.gcur_mem[i]||dut.music.core.u_tdm.amp_mem[i]||dut.music.core.u_tdm.pv_mem[i])$fatal(1,"reset slot not quiet %0d",i);
        if(nonzero<20)$fatal(1,"no actual audio");
        $display("PASS board_audio cycles=%0d samples=%0d nonzero=%0d on=%0d off=%0d moves=%0d uart_bytes=%0d cold_mute profile dual slide stop full32_steal stress_mute capture64 active_high_reset",cycles,samples,nonzero,ons,offs,moves,bytes_seen);$finish;
    end
    initial begin #30000000;$fatal(1,"watchdog");end
endmodule
