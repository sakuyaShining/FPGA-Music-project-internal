// Minimal controller protocol candidate: reset, RGB565, portrait, sleep-out,
// display-on and bounded rectangle writes. Panel power/gamma settings are not
// qualified without the actual module's reference initialization.
module mv_panel_driver #(
    parameter integer CLK_HZ=27000000,
    parameter integer HALF_CYCLES=2,
    parameter integer PANEL_WIDTH=320, PANEL_HEIGHT=240,
    parameter [7:0] MADCTL=8'h20
)(
    input wire clk, rst_n,
    output reg lcd_reset_n,
    output wire lcd_cs_n, lcd_sck, lcd_mosi, lcd_dc,
    output reg init_done,
    input wire start,
    input wire [8:0] x0, y0, x1, y1,
    input wire pixel_valid,
    input wire [15:0] pixel,
    output wire pixel_ready,
    output wire busy,
    output reg frame_done, window_error
);
    localparam RESET_CYCLES=(CLK_HZ/1000000)*20;
    localparam WAIT_120MS=(CLK_HZ/1000)*120;
    localparam WAIT_20MS=(CLK_HZ/1000)*20;
    localparam RESET_LOW=0, RESET_WAIT=1, INIT_SEND=2, INIT_ACK=3,
               INIT_DELAY=4, IDLE=5, HEADER_SEND=6, HEADER_ACK=7,
               PIXEL_GET=8, HIGH_SEND=9, HIGH_ACK=10, LOW_SEND=11, LOW_ACK=12;
    reg [3:0] state;
    reg [31:0] wait_count;
    reg [2:0] init_index;
    reg [3:0] header_index;
    reg [8:0] left, top, right, bottom, current_x, current_y;
    reg [15:0] held_pixel;
    reg tx_valid, tx_dc;
    reg [7:0] tx_data;
    wire tx_ready, tx_done;
    assign pixel_ready=(state==PIXEL_GET);
    assign busy=(state!=IDLE);
    mv_spi_byte #(.HALF_CYCLES(HALF_CYCLES)) u_spi(
        .clk(clk), .rst_n(rst_n), .valid(tx_valid), .dc_in(tx_dc),
        .data_in(tx_data), .ready(tx_ready), .done(tx_done),
        .cs_n(lcd_cs_n), .sck(lcd_sck), .mosi(lcd_mosi), .dc(lcd_dc)
    );
    always @* begin
        tx_valid=0; tx_dc=0; tx_data=0;
        case (state)
            INIT_SEND: begin
                tx_valid=1;
                case (init_index)
                    0: tx_data=8'h01;
                    1: tx_data=8'h3A;
                    2: begin tx_data=8'h55; tx_dc=1; end
                    3: tx_data=8'h36;
                    4: begin tx_data=MADCTL; tx_dc=1; end
                    5: tx_data=8'h11;
                    6: tx_data=8'h29;
                endcase
            end
            HEADER_SEND: begin
                tx_valid=1; tx_dc=1;
                case (header_index)
                    0: begin tx_data=8'h2A; tx_dc=0; end
                    1: tx_data={7'd0,left[8]};
                    2: tx_data=left[7:0];
                    3: tx_data={7'd0,right[8]};
                    4: tx_data=right[7:0];
                    5: begin tx_data=8'h2B; tx_dc=0; end
                    6: tx_data={7'd0,top[8]};
                    7: tx_data=top[7:0];
                    8: tx_data={7'd0,bottom[8]};
                    9: tx_data=bottom[7:0];
                    10: begin tx_data=8'h2C; tx_dc=0; end
                endcase
            end
            HIGH_SEND: begin tx_valid=1; tx_dc=1; tx_data=held_pixel[15:8]; end
            LOW_SEND: begin tx_valid=1; tx_dc=1; tx_data=held_pixel[7:0]; end
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=RESET_LOW; wait_count<=RESET_CYCLES-1; lcd_reset_n<=0;
            init_index<=0; header_index<=0; init_done<=0;
            frame_done<=0; window_error<=0; held_pixel<=0;
            left<=0; top<=0; right<=0; bottom<=0; current_x<=0; current_y<=0;
        end else begin
            frame_done<=0; window_error<=0;
            case (state)
                RESET_LOW: if (wait_count!=0) wait_count<=wait_count-1;
                else begin lcd_reset_n<=1; wait_count<=WAIT_120MS-1; state<=RESET_WAIT; end
                RESET_WAIT: if (wait_count!=0) wait_count<=wait_count-1;
                else begin init_index<=0; state<=INIT_SEND; end
                INIT_SEND: if (tx_ready) state<=INIT_ACK;
                INIT_ACK: if (tx_done) begin
                    if (init_index==0 || init_index==5 || init_index==6) begin
                        wait_count<=(init_index==6 ? WAIT_20MS : WAIT_120MS)-1;
                        state<=INIT_DELAY;
                    end else begin init_index<=init_index+1; state<=INIT_SEND; end
                end
                INIT_DELAY: if (wait_count!=0) wait_count<=wait_count-1;
                else if (init_index==6) begin init_done<=1; state<=IDLE; end
                else begin init_index<=init_index+1; state<=INIT_SEND; end
                IDLE: if (start) begin
                    if (x0>x1 || y0>y1 || x1>=PANEL_WIDTH || y1>=PANEL_HEIGHT) window_error<=1;
                    else begin
                        left<=x0; top<=y0; right<=x1; bottom<=y1;
                        current_x<=x0; current_y<=y0;
                        header_index<=0; state<=HEADER_SEND;
                    end
                end
                HEADER_SEND: if (tx_ready) state<=HEADER_ACK;
                HEADER_ACK: if (tx_done) begin
                    if (header_index==10) state<=PIXEL_GET;
                    else begin header_index<=header_index+1; state<=HEADER_SEND; end
                end
                PIXEL_GET: if (pixel_valid) begin held_pixel<=pixel; state<=HIGH_SEND; end
                HIGH_SEND: if (tx_ready) state<=HIGH_ACK;
                HIGH_ACK: if (tx_done) state<=LOW_SEND;
                LOW_SEND: if (tx_ready) state<=LOW_ACK;
                LOW_ACK: if (tx_done) begin
                    if (current_x==right && current_y==bottom) begin frame_done<=1; state<=IDLE; end
                    else begin
                        if (current_x==right) begin current_x<=left; current_y<=current_y+1; end
                        else current_x<=current_x+1;
                        state<=PIXEL_GET;
                    end
                end
            endcase
        end
    end
endmodule
