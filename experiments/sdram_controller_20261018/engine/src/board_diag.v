// Diagnostic-only observer. No physical sensors, no audio generation on host.
module board_diag #(
    parameter integer CAPTURE_SAMPLES=2048,
    parameter integer FINGER_SCOPE=32
)(
    input wire clk, rst_n, sample_en,
    input wire [7:0] test_status,test_case,
    input wire wr_en, input wire [7:0] wr_addr, wr_data, rd_addr,
    input wire stream_start, stream_next,
    input wire ev_ack, ev_on, input wire [6:0] ev_note,
    input wire [31:0] active, finger_active,
    input wire signed [23:0] dry_sample, audio_sample,
    input wire [2:0] queue_level, input wire note_busy,
    input wire voice_valid, input wire [4:0] voice_group,
    input wire [6:0] voice_note,
    output reg [7:0] rd_data,
    output reg finger_valid, output reg [1:0] finger_cmd,
    output reg [4:0] finger_id, finger_group,
    output wire signed [11:0] finger_position
);
    reg [11:0] position;
    assign finger_position=position;
    reg [15:0] ack_count,on_count,off_count;
    reg [31:0] sample_count;
    reg [15:0] period, period_min, period_max;
    reg period_seen;
    reg [15:0] ack_snap,on_snap,off_snap;
    reg [31:0] active_snap,samples_snap,fingers_snap;
    reg [4:0] last_group;
    reg [6:0] last_note;
    reg [10:0] read_index,write_index;
    reg [11:0] captured;
    reg capturing, valid_capture, select_fx;
    reg [7:0] capture_id;
    reg signed [23:0] capture_mem[0:CAPTURE_SAMPLES-1];
    reg signed [23:0] read_sample;
    // Synchronous read permits block RAM inference; indices stay stable during UART reads.
    always @(posedge clk) read_sample <= capture_mem[read_index];
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            ack_count<=0;on_count<=0;off_count<=0;sample_count<=0;
            period<=0;period_min<=16'hffff;period_max<=0;period_seen<=0;
            ack_snap<=0;on_snap<=0;off_snap<=0;active_snap<=0;samples_snap<=0;fingers_snap<=0;
            last_group<=0;last_note<=0;read_index<=0;write_index<=0;captured<=0;
            capturing<=0;valid_capture<=0;select_fx<=0;capture_id<=0;
            finger_valid<=0;finger_cmd<=0;finger_id<=0;finger_group<=0;position<=0;
        end else begin
            finger_valid<=0;
            if(stream_start) read_index<=0;
            else if(stream_next) read_index<=read_index+1'b1;
            period<=period+1'b1;
            if(sample_en) begin
                sample_count<=sample_count+1'b1;
                period<=0;period_seen<=1;
                if(period_seen) begin
                    if(period+1'b1<period_min) period_min<=period+1'b1;
                    if(period+1'b1>period_max) period_max<=period+1'b1;
                end
                if(capturing) begin
                    capture_mem[write_index]<=select_fx ? audio_sample : dry_sample;
                    captured<=captured+1'b1;
                    if(write_index==CAPTURE_SAMPLES-1) begin
                        capturing<=0;valid_capture<=1;capture_id<=capture_id+1'b1;
                    end else write_index<=write_index+1'b1;
                end
            end
            if(ev_ack) begin
                ack_count<=ack_count+1'b1;
                if(ev_on) on_count<=on_count+1'b1; else off_count<=off_count+1'b1;
            end
            if(voice_valid) begin last_group<=voice_group;last_note<=voice_note;end
            if(wr_en) begin
                case(wr_addr)
                    8'h80: if(wr_data[0] && !capturing) begin
                        capturing<=1;valid_capture<=0;captured<=0;write_index<=0;select_fx<=wr_data[1];
                    end
                    8'h81: read_index[7:0]<=wr_data;
                    8'h82: read_index[10:8]<=wr_data[2:0];
                    8'h83: begin
                        ack_snap<=ack_count;on_snap<=on_count;off_snap<=off_count;
                        active_snap<=active;samples_snap<=sample_count;fingers_snap<=finger_active;
                    end
                    8'hB0: finger_id<=wr_data[4:0];
                    8'hB1: finger_group<=wr_data[4:0];
                    8'hB2: position[7:0]<=wr_data;
                    8'hB3: position[11:8]<=wr_data[3:0];
                    8'hB4: begin finger_cmd<=wr_data[1:0];finger_valid<=1;end
                endcase
            end
        end
    end
    always @* begin
        rd_data=0;
        case(rd_addr)
            8'h80:rd_data={5'b0,select_fx,valid_capture,capturing};
            8'h81:rd_data=captured[7:0];8'h82:rd_data={4'b0,captured[11:8]};
            8'h83:rd_data=ack_snap[7:0];8'h84:rd_data=ack_snap[15:8];
            8'h85:rd_data=on_snap[7:0];8'h86:rd_data=on_snap[15:8];
            8'h87:rd_data=off_snap[7:0];8'h88:rd_data=off_snap[15:8];
            8'h89:rd_data=active_snap[7:0];8'h8A:rd_data=active_snap[15:8];
            8'h8B:rd_data=active_snap[23:16];8'h8C:rd_data=active_snap[31:24];
            8'h8D:rd_data=samples_snap[7:0];8'h8E:rd_data=samples_snap[15:8];
            8'h8F:rd_data=samples_snap[23:16];
            8'h90:rd_data=period_min[7:0];8'h91:rd_data=period_min[15:8];
            8'h92:rd_data=period_max[7:0];8'h93:rd_data=period_max[15:8];
            8'h94:rd_data=fingers_snap[7:0];8'h95:rd_data=fingers_snap[15:8];
            8'h96:rd_data=fingers_snap[23:16];8'h97:rd_data=fingers_snap[31:24];
            8'h9C:rd_data={3'b0,last_group};8'h9D:rd_data={1'b0,last_note};
            8'h9E:rd_data={5'b0,queue_level};8'h9F:rd_data={7'b0,note_busy};
            8'hA0:rd_data=read_sample[7:0];8'hA1:rd_data=read_sample[15:8];8'hA2:rd_data=read_sample[23:16];
            8'hA3:rd_data=capture_id;8'hA4:rd_data=8'hD3;8'hA5:rd_data=2;
            8'hA6:rd_data=16;8'hA7:rd_data=CAPTURE_SAMPLES/256;
            8'hA9:rd_data=FINGER_SCOPE;
            8'hC0:rd_data=8'h72;8'hC1:rd_data=test_status;8'hC2:rd_data=test_case;8'hC3:rd_data=1;
        endcase
    end
endmodule
