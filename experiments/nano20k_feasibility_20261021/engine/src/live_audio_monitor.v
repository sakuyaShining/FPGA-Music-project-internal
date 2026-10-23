// Full-rate PCM16 observer; does not alter the music/audio output path.
// Start/stop register B5. Two 512-sample banks, 32 accepted-event queue entries.
// Frame: "FMV1", type(1=audio/2=event), frame_sequence LE16, length LE16,
// timestamp LE32 (audio sample counter), cumulative losses LE16, format=1,
// payload, CRC16-CCITT big endian over bytes after magic and before CRC.
module live_audio_monitor #(parameter FORMAT=1) (
    input wire clk, rst_n, sample_en, sample_valid,
    input wire signed [23:0] sample,
    input wire wr_en, input wire [7:0] wr_addr, wr_data,
    input wire event_valid, event_on,
    input wire [6:0] event_note, input wire [3:0] event_velocity,
    input wire tx_available, tx_done,
    output reg enabled, output wire owns_tx,
    output reg tx_start, output reg [7:0] tx_data
);
    reg [31:0] sample_clock, bank_time0, bank_time1;
    reg [15:0] pcm [0:1023];
    reg [47:0] events [0:31];
    reg [15:0] pcm_q;
    reg [47:0] event_q;
    reg [4:0] er, ew;
    reg [5:0] ec;
    reg bank, sending_bank, next_bank;
    reg [8:0] wi;
    reg [1:0] ready;
    reg [15:0] losses, frame_sequence, frame_losses, crc;
    reg [31:0] stamp;
    reg [15:0] frame_event;
    reg [10:0] pos;
    reg audio_frame;
    reg [2:0] st;
    wire [10:0] payload_len = audio_frame ? 11'd1024 : 11'd2;
    wire [10:0] total = 11'd18 + payload_len;
    wire [8:0] sample_ra = (pos-11'd16)>>1;
    wire [9:0] ra = {sending_bank, sample_ra};
    assign owns_tx = st!=0;
    function [15:0] crc_next;
        input [15:0] c; input [7:0] d;
        integer k; reg [15:0] v;
        begin
            v=c^{d,8'b0};
            for(k=0;k<8;k=k+1) v=v[15] ? (v<<1)^16'h1021 : v<<1;
            crc_next=v;
        end
    endfunction
    reg [7:0] byte_value;
    always @* begin
        byte_value=0;
        case(pos)
            0:byte_value=8'h46; 1:byte_value=8'h4d; 2:byte_value=8'h56; 3:byte_value=8'h31;
            4:byte_value=audio_frame ? 1 : 2;
            5:byte_value=frame_sequence[7:0]; 6:byte_value=frame_sequence[15:8];
            7:byte_value=payload_len[7:0]; 8:byte_value={5'b0,payload_len[10:8]};
            9:byte_value=stamp[7:0]; 10:byte_value=stamp[15:8];
            11:byte_value=stamp[23:16]; 12:byte_value=stamp[31:24];
            13:byte_value=frame_losses[7:0]; 14:byte_value=frame_losses[15:8];
            15:byte_value=FORMAT;
            default: begin
                if(pos==total-2) byte_value=crc[15:8];
                else if(pos==total-1) byte_value=crc[7:0];
                else if(audio_frame) byte_value=pos[0] ? pcm_q[15:8] : pcm_q[7:0];
                else byte_value=pos[0] ? frame_event[15:8] : frame_event[7:0];
            end
        endcase
    end
    always @(posedge clk) begin
        pcm_q<=pcm[ra];
        event_q<=events[er];
        if(enabled && sample_valid && !ready[bank]) pcm[{bank,wi}]<=sample[23:8];
        if(enabled && event_valid && ec<32) events[ew]<={sample_clock,4'b0,event_velocity,event_on,event_note};
    end
    // Queue can push/pop concurrently; ownership and readiness are single-writer.
    wire event_pop = enabled && st==0 && tx_available && ec!=0;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            enabled<=0;sample_clock<=0;bank_time0<=0;bank_time1<=0;
            er<=0;ew<=0;ec<=0;bank<=0;sending_bank<=0;next_bank<=0;wi<=0;ready<=0;
            losses<=0;frame_sequence<=0;frame_losses<=0;crc<=16'hffff;stamp<=0;
            frame_event<=0;pos<=0;audio_frame<=0;st<=0;tx_start<=0;tx_data<=0;
        end else begin
            tx_start<=0;
            if(sample_en) sample_clock<=sample_clock+1'b1;
            if(enabled) begin
                if(event_valid && ec<32) ew<=ew+1'b1;
                case({event_valid && ec<32,event_pop})
                    2'b10:ec<=ec+1'b1;
                    2'b01:ec<=ec-1'b1;
                    default:;
                endcase
                if(event_valid && ec==32 && losses!=16'hffff) losses<=losses+1'b1;
                if(sample_valid) begin
                    if(!ready[bank]) begin
                        if(wi==0) begin
                            if(bank) bank_time1<=FORMAT==2 ? sample_clock-1 : sample_clock; else bank_time0<=FORMAT==2 ? sample_clock-1 : sample_clock;
                        end
                        if(wi==511) begin ready[bank]<=1;bank<=~bank;wi<=0;end
                        else wi<=wi+1'b1;
                    end else if(losses!=16'hffff) losses<=losses+1'b1;
                end
            end
            case(st)
                0: if(enabled && tx_available) begin
                    if(ec!=0) begin
                        er<=er+1'b1; audio_frame<=0;st<=1;
                    end else if(ready!=0) begin
                        sending_bank<=ready[next_bank] ? next_bank : ~next_bank;
                        stamp<=(ready[next_bank] ? next_bank : ~next_bank) ? bank_time1 : bank_time0;
                        audio_frame<=1;st<=1;
                    end
                    pos<=0;crc<=16'hffff;frame_losses<=losses;
                end
                1: begin
                    if(!audio_frame && pos==0) begin
                        stamp<=event_q[47:16];frame_event<=event_q[15:0];
                    end
                    st<=2;
                end
                2: begin
                    tx_data<=byte_value;tx_start<=1;st<=3;
                    if(pos>=4 && pos<total-2) crc<=crc_next(crc,byte_value);
                end
                3: if(tx_done) begin
                    if(pos==total-1) begin
                        if(audio_frame) begin ready[sending_bank]<=0;next_bank<=~sending_bank;end
                        frame_sequence<=frame_sequence+1'b1;st<=0;
                    end else begin pos<=pos+1'b1;st<=1;end
                end
                default:st<=0;
            endcase
            if(wr_en && wr_addr==8'hB5) begin
                enabled<=wr_data[0];
                // Disabling finishes the in-flight frame; starting a new session clears queues.
                if(wr_data[0] && !enabled && st==0) begin
                    bank<=0;next_bank<=0;wi<=0;ready<=0;er<=0;ew<=0;ec<=0;losses<=0;frame_sequence<=0;
                end
            end
        end
    end
endmodule
