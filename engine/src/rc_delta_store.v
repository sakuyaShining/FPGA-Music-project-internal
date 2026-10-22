// Explicit calibration captures one complete frame. No assumption that startup
// fingers are absent, no automatic tracking of held fingers into the baseline.
// Node number = row_address*LANES + lane; all rows remain available for telemetry.
module rc_delta_store #(parameter integer LANES=6,CW=12)(
    input wire clk,rst_n,calibrate,
    input wire row_valid,
    output wire row_ready,
    input wire [3:0] row_address,
    input wire [LANES*CW-1:0] row_count,
    input wire [LANES-1:0] row_fault,
    input wire [31:0] row_sequence,
    output wire frame_valid,
    input wire frame_ready,
    output reg [31:0] frame_sequence,
    output reg frame_calibration,
    input wire [6:0] read_address,
    output wire [CW-1:0] read_delta,
    output reg read_valid,
    output reg protocol_error
);
    localparam IDLE=0,READ=1,WRITE=2,HOLD=3;
    reg [1:0] state;
    reg [3:0] expected,row_q;
    reg [31:0] sequence_q;
    reg [LANES*CW-1:0] counts_q;
    reg [LANES-1:0] faults_q;
    reg [2:0] lane;
    reg pending_cal,cal_mode;
    reg [LANES*16-1:0] known,valid;
    reg [2*CW-1:0] memory[0:127];
    reg [2*CW-1:0] old_word;
    reg [CW-1:0] delta_q,collision_old;
    reg collision_q;
    wire [7:0] wide_index=row_q*LANES+lane;
    wire [6:0] index=wide_index[6:0]; // LANES<=8, 16 rows => max127.
    wire [CW-1:0] raw=counts_q[lane*CW+:CW];
    wire [CW-1:0] base=old_word[2*CW-1:CW];
    assign row_ready=state==IDLE;
    assign frame_valid=state==HOLD;
    // Avoid unsupported READ_FIRST on the writing DPB port. The preceding
    // READ state already captured this word; collision bypass preserves the
    // other port's old-data contract without relying on cross-port silicon mode.
    assign read_delta=collision_q?collision_old:delta_q;
    always @(posedge clk)begin
        if(state!=WRITE)old_word<=memory[index];
        delta_q<=memory[read_address][CW-1:0];
        collision_q<=state==WRITE && read_address==index;
        collision_old<=old_word[CW-1:0];
        read_valid<=(read_address<LANES*16)?valid[read_address]:1'b0;
        if(state==WRITE)
            memory[index]<=cal_mode?{raw,{CW{1'b0}}}:{base,((raw>base)?raw-base:{CW{1'b0}})};
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin state<=IDLE;expected<=0;row_q<=0;sequence_q<=0;counts_q<=0;faults_q<=0;lane<=0;pending_cal<=0;cal_mode<=0;known<=0;valid<=0;frame_sequence<=0;frame_calibration<=0;protocol_error<=0;end
        else begin
            if(calibrate)pending_cal<=1;
            case(state)
                IDLE:if(row_valid)begin
                    if((row_address!=expected)||(row_address!=0&&row_sequence!=sequence_q))begin
                        protocol_error<=1;expected<=0;
                    end else begin
                        if(row_address==0)begin sequence_q<=row_sequence;cal_mode<=pending_cal||calibrate;pending_cal<=0;end
                        row_q<=row_address;counts_q<=row_count;faults_q<=row_fault;lane<=0;state<=READ;
                    end
                end
                READ:state<=WRITE;
                WRITE:begin
                    if(cal_mode)known[index]<=!faults_q[lane];
                    valid[index]<=cal_mode?!faults_q[lane]:(known[index]&&!faults_q[lane]);
                    if(lane==LANES-1)begin
                        expected<=row_q+1'b1;
                        if(row_q==15)begin frame_sequence<=sequence_q;frame_calibration<=cal_mode;state<=HOLD;end
                        else state<=IDLE;
                    end else begin lane<=lane+1'b1;state<=READ;end
                end
                HOLD:if(frame_ready)state<=IDLE;
            endcase
        end
    end
endmodule
