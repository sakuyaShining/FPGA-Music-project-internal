`timescale 1ns/1ps
module tb_ili9341;
    reg clk=0, rst_n=1;
    always #18.519 clk=~clk;
    wire reset_n, cs_n, sck, mosi, dc, init_done, pixel_ready, busy, frame_done, window_error;
    reg start=0, pixel_valid=0;
    reg [8:0] x0=0,y0=0,x1=0,y1=0;
    reg [15:0] pixel=0;
    ili9341_window dut(.clk(clk),.rst_n(rst_n),.lcd_reset_n(reset_n),
        .lcd_cs_n(cs_n),.lcd_sck(sck),.lcd_mosi(mosi),.lcd_dc(dc),.init_done(init_done),
        .start(start),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
        .pixel_valid(pixel_valid),.pixel(pixel),.pixel_ready(pixel_ready),
        .busy(busy),.frame_done(frame_done),.window_error(window_error));
    integer fd, bit_count=0, byte_count=0, frame_count=0;
    reg [7:0] received=0;
    reg byte_dc;
    realtime last_rise=-1, last_fall=-1, last_data=-1000, last_dc=-1000, cs_start=-1, reset_start=0;
    realtime min_period=1e12, min_high=1e12, min_low=1e12, min_setup=1e12;
    task fail;
        input [255:0] message;
        begin $display("FAIL %0s at %.3f",message,$realtime); $fatal(1); end
    endtask
    always @(mosi) begin
        if (reset_n && !cs_n && last_rise>=0 && $realtime-last_rise<29.999) fail("data hold <30ns");
        last_data=$realtime;
    end
    always @(dc) begin
        if (reset_n && !cs_n && last_rise>=0 && $realtime-last_rise<9.999) fail("DC hold <10ns");
        last_dc=$realtime;
    end
    always @(negedge reset_n) begin
        bit_count=0; last_rise=-1; last_fall=-1; reset_start=$realtime;
        if (fd) $fdisplay(fd,"RESET %.3f",$realtime);
    end
    always @(posedge reset_n) begin
        if ($realtime-reset_start<9999.999) fail("reset pulse <10us");
        $fdisplay(fd,"RELEASE %.3f",$realtime);
    end
    always @(negedge cs_n) begin
        if (reset_n) begin
            if (sck!==0) fail("SCK not idle low");
            cs_start=$realtime; bit_count=0;
        end
    end
    always @(posedge sck) if (reset_n && !cs_n) begin
        if ($realtime-cs_start<39.999) fail("CS setup <40ns");
        if ($realtime-last_data<29.999) fail("data setup <30ns");
        if ($realtime-last_dc<9.999) fail("DC setup <10ns");
        if (last_rise>=0) begin
            if ($realtime-last_rise<99.999) fail("SCK period <100ns");
            if ($realtime-last_rise<min_period) min_period=$realtime-last_rise;
        end
        if (last_fall>=0) begin
            if ($realtime-last_fall<39.999) fail("SCK low <40ns");
            if ($realtime-last_fall<min_low) min_low=$realtime-last_fall;
        end
        if ($realtime-last_data<min_setup) min_setup=$realtime-last_data;
        last_rise=$realtime;
        if (bit_count==0) byte_dc=dc;
        else if (dc!==byte_dc) fail("DC changed within byte");
        received={received[6:0],mosi};
        bit_count=bit_count+1;
        if (bit_count==8) begin
            $fdisplay(fd,"BYTE %.3f %0d %02x",$realtime,byte_dc,received);
            bit_count=0; byte_count=byte_count+1;
        end
    end
    always @(negedge sck) if (reset_n && !cs_n && last_rise>=0) begin
        if ($realtime-last_rise<39.999) fail("SCK high <40ns");
        if ($realtime-last_rise<min_high) min_high=$realtime-last_rise;
        last_fall=$realtime;
    end
    always @(posedge cs_n) if (reset_n && cs_start>=0) begin
        if (bit_count!=0) fail("partial byte outside reset");
        if (last_rise>=0 && $realtime-last_rise<39.999) fail("CS hold <40ns");
    end
    function [15:0] test_color;
        input integer index;
        integer x,y;
        begin
            x=index%240; y=index/240;
            if (x==0 && y==0) test_color=16'hF800;
            else if (x==239 && y==0) test_color=16'h07E0;
            else if (x==0 && y==319) test_color=16'h001F;
            else if (x==239 && y==319) test_color=16'hFFFF;
            else case (x/40)
                0: test_color=16'hF800;
                1: test_color=16'h07E0;
                2: test_color=16'h001F;
                3: test_color=16'hFFE0;
                4: test_color=16'hF81F;
                5: test_color=16'h07FF;
            endcase
        end
    endfunction
    task begin_window;
        input integer tag, l,t,r,b;
        begin
            @(negedge clk); x0=l; y0=t; x1=r; y1=b; start=1;
            $fdisplay(fd,"START %.3f %0d %0d %0d %0d %0d",$realtime,tag,l,t,r,b);
            @(negedge clk); start=0;
        end
    endtask
    task send_pixels;
        input integer count, style;
        integer i;
        begin
            for (i=0;i<count;i=i+1) begin
                if (i%17==0) repeat(3) @(negedge clk);
                @(negedge clk);
                pixel=(style==0) ? test_color(i) : ((i%2==0) ? 16'h1234 : 16'hABCD);
                pixel_valid=1;
                @(posedge clk);
                while (!pixel_ready) @(posedge clk);
                @(negedge clk); pixel_valid=0;
            end
        end
    endtask
    initial begin
        fd=$fopen("spi-bytes.log","w");
        #1 rst_n=0;
        repeat(8) @(negedge clk);
        rst_n=1;
        wait(init_done);
        begin_window(0,0,0,9,9);
        @(negedge cs_n);
        repeat(3) @(posedge sck);
        #5 rst_n=0;
        repeat(8) @(negedge clk);
        rst_n=1;
        wait(init_done);
        begin_window(1,0,0,239,319);
        send_pixels(76800,0);
        wait(frame_done);
        $fdisplay(fd,"DONE %.3f 1",$realtime); frame_count=frame_count+1;
        begin_window(2,7,9,19,19);
        send_pixels(143,1);
        wait(frame_done);
        $fdisplay(fd,"DONE %.3f 2",$realtime); frame_count=frame_count+1;
        @(negedge clk); x0=20; y0=0; x1=19; y1=10; start=1;
        @(negedge clk); start=0;
        if (!window_error || busy) fail("invalid window not rejected");
        $fdisplay(fd,"INVALID_REJECTED %.3f",$realtime);
        repeat(20) @(posedge clk);
        $fdisplay(fd,"TIMING %.3f %.3f %.3f %.3f",min_period,min_high,min_low,min_setup);
        $fclose(fd);
        $display("PASS pin timing, reset recovery, full frame, partial rectangle, source stalls, invalid window; bytes=%0d frames=%0d",byte_count,frame_count);
        $finish;
    end
    initial begin #2000000000; fail("timeout"); end
endmodule
