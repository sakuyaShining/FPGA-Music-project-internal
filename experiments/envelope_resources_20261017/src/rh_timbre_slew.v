// Coherent gain bank with bounded slew. Audio continues while targets change.
module rh_timbre_slew #(
    parameter integer N=16,
    parameter integer GW=10,
    parameter integer UNITY=256,
    parameter integer LIMIT=1023
)(
    input wire clk,rst_n,sample_ce,
    input wire target_valid,
    output wire target_ready,
    input wire [N*GW-1:0] target_gain,
    input wire [GW-1:0] slew_step,
    input wire restore_valid,
    output reg [N*GW-1:0] current_gain,
    output reg bank_done,
    output reg tick_overrun
);
    localparam IW=(N<2)?1:$clog2(N);
    localparam IDLE=2'd0,STEP=2'd1,COMMIT=2'd2;
    reg [1:0] state;
    reg [IW-1:0] index;
    reg [N*GW-1:0] target_q,work;
    reg [GW-1:0] step_q;
    wire [GW-1:0] t=target_q[index*GW+:GW];
    wire [GW-1:0] c=current_gain[index*GW+:GW];
    wire [GW-1:0] distance=(t>c)?t-c:c-t;
    wire [GW-1:0] next_gain=(distance<=step_q)?t:((t>c)?c+step_q:c-step_q);
    assign target_ready=state==IDLE&&!restore_valid;
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            state<=IDLE;index<=0;step_q<=1;
            target_q<={N{UNITY[GW-1:0]}};current_gain<={N{UNITY[GW-1:0]}};work<={N{UNITY[GW-1:0]}};
            bank_done<=0;tick_overrun<=0;
        end else begin
            bank_done<=0;tick_overrun<=0;
            if(restore_valid)begin
                // Abort incomplete sweep; restore targets, then ramp at sample_ce.
                target_q<={N{UNITY[GW-1:0]}};state<=IDLE;
            end else begin
                if(sample_ce&&state!=IDLE)tick_overrun<=1;
                if(target_valid&&target_ready)
                    for(i=0;i<N;i=i+1)
                        target_q[i*GW+:GW] <= (target_gain[i*GW+:GW]<UNITY)?UNITY[GW-1:0]:
                           ((target_gain[i*GW+:GW]>LIMIT)?LIMIT[GW-1:0]:target_gain[i*GW+:GW]);
                case(state)
                    IDLE:if(sample_ce)begin
                        work<=current_gain;index<=0;step_q<=(slew_step==0)?{{(GW-1){1'b0}},1'b1}:slew_step;state<=STEP;
                    end
                    STEP:begin
                        work[index*GW+:GW]<=next_gain;
                        if(index==N-1)state<=COMMIT;else index<=index+1'b1;
                    end
                    COMMIT:begin current_gain<=work;bank_done<=1;state<=IDLE;end
                    default:state<=IDLE;
                endcase
            end
        end
    end
endmodule
