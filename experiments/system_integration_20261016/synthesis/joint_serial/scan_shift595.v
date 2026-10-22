// One complete 8-bit word per latch. External arbiter must hold grant until
// bus_request drops. Other SPI traffic may shift the 595, but never latch it.
module scan_shift595 #(parameter integer HALF_PERIOD=8)(
    input wire clk,rst_n,word_valid,
    output wire word_ready,
    input wire [7:0] word_data,
    output wire bus_request,
    input wire bus_grant,
    output reg sck,mosi,latch,
    output reg word_latched,
    output reg word_done,
    output reg grant_error
);
    localparam IDLE=0,WAIT=1,LOW=2,HIGH=3,LATCH=4,FINISH=5;
    reg [2:0] state,bit_index;
    reg [7:0] data_q;
    localparam TW=(HALF_PERIOD<2)?1:$clog2(HALF_PERIOD);
    reg [TW-1:0] timer;
    assign word_ready=state==IDLE;
    assign bus_request=state!=IDLE;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin state<=IDLE;bit_index<=0;data_q<=0;timer<=0;sck<=0;mosi<=0;latch<=0;word_latched<=0;word_done<=0;grant_error<=0;end
        else begin
            word_done<=0;
            word_latched<=0;
            if(state>=LOW&&!bus_grant)grant_error<=1;
            case(state)
                IDLE:if(word_valid)begin data_q<=word_data;state<=WAIT;end
                WAIT:if(bus_grant)begin bit_index<=7;mosi<=data_q[7];timer<=0;state<=LOW;end
                LOW:if(timer==HALF_PERIOD-1)begin timer<=0;sck<=1;state<=HIGH;end else timer<=timer+1'b1;
                HIGH:if(timer==HALF_PERIOD-1)begin
                    timer<=0;sck<=0;
                    if(bit_index==0)state<=LATCH;
                    else begin bit_index<=bit_index-1'b1;mosi<=data_q[bit_index-1'b1];state<=LOW;end
                end else timer<=timer+1'b1;
                LATCH:if(timer==HALF_PERIOD-1)begin timer<=0;latch<=1;word_latched<=1;state<=FINISH;end else timer<=timer+1'b1;
                FINISH:if(timer==HALF_PERIOD-1)begin latch<=0;word_done<=1;state<=IDLE;end else timer<=timer+1'b1;
                default:state<=IDLE;
            endcase
        end
    end
endmodule
