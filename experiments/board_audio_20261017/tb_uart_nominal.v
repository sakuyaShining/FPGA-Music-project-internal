`timescale 1ns/1ps
module tb_uart_nominal;
    localparam DIV=234;
    reg clk=0;always #5 clk=~clk;
    reg reset_button=0,rx=1;
    wire tx,pa;wire [5:0] led;
    board_audio_top #(.WARM_CYCLES(5120),.REPORT_CYCLES(1024),.CASE_CYCLES(196608),.TAIL_CYCLES(4096),.DIAG_CAPTURE_SAMPLES(64)) dut(.clk(clk),.reset_button(reset_button),.uart_rx_pin(rx),.uart_tx_pin(tx),.led(led),.pa_en(pa));
    reg [7:0] v,echo;
    task send_byte;input [7:0] data;integer k;begin
        @(negedge clk);rx=0;repeat(DIV)@(negedge clk);for(k=0;k<8;k=k+1)begin rx=data[k];repeat(DIV)@(negedge clk);end rx=1;repeat(DIV+3)@(negedge clk);
    end endtask
    task recv_byte;output [7:0] data;integer k;begin
        @(negedge tx);repeat(DIV+DIV/2)@(negedge clk);for(k=0;k<8;k=k+1)begin data[k]=tx;repeat(DIV)@(negedge clk);end if(tx!==1)$fatal(1,"UART stop");
    end endtask
    task write_reg;input [7:0] addr,data;begin send_byte(addr);send_byte(data);repeat(12)@(negedge clk);end endtask
    task read_reg;input [7:0] addr;output [7:0] data;begin
        fork begin send_byte(15);send_byte(addr);end begin recv_byte(echo);if(echo!==addr)$fatal(1,"echo");recv_byte(data);end join repeat(8)@(negedge clk);
    end endtask
    initial begin
        repeat(6000)@(negedge clk);read_reg(8'hC0,v);if(v!=8'h72||pa)$fatal(1,"profile / cold mute");
        write_reg(8'hC0,8'hA6);write_reg(8'hC1,1);read_reg(8'hC2,v);if(v!=1||!pa||dut.music.core.nm_active==0)$fatal(1,"nominal baud play");
        write_reg(8'h83,1);read_reg(8'h90,v);if(v!=0)$fatal(1,"period low");read_reg(8'h91,v);if(v!=2)$fatal(1,"period high");
        write_reg(8'hC2,0);repeat(4000)@(negedge clk);if(pa||dut.music.core.nm_active)$fatal(1,"nominal baud stop");
        $display("PASS nominal_uart configured_baud=115200 actual_divider=234 profile arm A4 snapshot period512 stop");$finish;
    end
    initial begin #5000000;$fatal(1,"watchdog");end
endmodule
