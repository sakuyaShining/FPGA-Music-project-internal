`timescale 1ns/1ps
module tb_wave;
    reg clk=0,rst_n=0,start=0,valid=0;
    reg signed [15:0] sample=0;
    always #5 clk=~clk;
    wire busy,write_valid,complete;
    wire [6:0] index;
    wire [15:0] data;
    integer kind=0,count=0,i,j,completed=0;
    reg [15:0] expected;
    mv_wave_capture dut(.clk(clk),.rst_n(rst_n),.start(start),.sample_valid(valid),.sample(sample),
        .busy(busy),.write_valid(write_valid),.complete(complete),.write_index(index),.write_data(data));
    always @(posedge clk) if(write_valid) begin
        case(kind)
            0: expected=16'h0000;
            1: expected=16'h7f7f;
            2: expected=16'h8080;
            3: expected=16'h807f;
            4: expected=(index==63 ? 16'h007f : 16'h0000);
        endcase
        if(index!=count || data!==expected) $fatal(1,"wave kind=%0d col=%0d data=%h expected=%h",kind,index,data,expected);
        count=count+1;
        if(complete) begin
            if(count!=128) $fatal(1,"wrong columns");
            completed=completed+1;
        end
    end
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        for(kind=0;kind<5;kind=kind+1) begin
            count=0;
            @(negedge clk);start=1;
            @(negedge clk);start=0;
            for(i=0;i<512;i=i+1) begin
                @(negedge clk);valid=1;
                case(kind)
                    0:sample=0;
                    1:sample=32767;
                    2:sample=-32768;
                    3:sample=(i%2==0 ? -32768 : 32767);
                    4:sample=(i==253 ? 32767 : 0);
                endcase
                // Include source pauses in the alternating-extrema case.
                if(kind==3) begin @(negedge clk);valid=0; end
            end
            @(negedge clk);valid=0;
            repeat(3) @(negedge clk);
            if(busy || count!=128) $fatal(1,"wave did not finish");
        end
        // Abort a partial capture; reset must discard it and return to idle.
        @(negedge clk);start=1;
        @(negedge clk);start=0;valid=1;
        repeat(2) @(negedge clk);
        rst_n=0;
        @(negedge clk);valid=0;rst_n=1;
        repeat(5) @(negedge clk);
        if(busy || write_valid || complete || completed!=5) $fatal(1,"reset recovery");
        $display("PASS wave 5 cases x128 columns, pauses, reset abort");$finish;
    end
endmodule
