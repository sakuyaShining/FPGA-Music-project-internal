// Observation-only FIR: 63-tap Hamming low-pass, 5kHz cutoff, Fs=27MHz/512.
// One serial MAC, output every fourth input. Music/I2S samples are untouched.
module live_observation_filter(input wire clk,rst_n,sample_en,
    input wire signed [23:0] sample, output reg valid,
    output reg signed [23:0] filtered);
    reg signed [15:0] history[0:63];
    reg signed [15:0] tap_q;
    reg [5:0] wp,base,tap;
    reg [1:0] decim;
    reg busy,emit;
    reg [1:0] phase;
    reg signed [39:0] acc;
    wire [5:0] ra=base-tap;
    function signed [15:0] coefficient;
        input [5:0] i;
        begin case(i)
            6'd0:coefficient=-16'sd10;
            6'd1:coefficient=-16'sd24;
            6'd2:coefficient=-16'sd32;
            6'd3:coefficient=-16'sd31;
            6'd4:coefficient=-16'sd17;
            6'd5:coefficient=16'sd12;
            6'd6:coefficient=16'sd49;
            6'd7:coefficient=16'sd82;
            6'd8:coefficient=16'sd92;
            6'd9:coefficient=16'sd63;
            6'd10:coefficient=-16'sd8;
            6'd11:coefficient=-16'sd107;
            6'd12:coefficient=-16'sd198;
            6'd13:coefficient=-16'sd238;
            6'd14:coefficient=-16'sd187;
            6'd15:coefficient=-16'sd36;
            6'd16:coefficient=16'sd184;
            6'd17:coefficient=16'sd402;
            6'd18:coefficient=16'sd524;
            6'd19:coefficient=16'sd464;
            6'd20:coefficient=16'sd188;
            6'd21:coefficient=-16'sd262;
            6'd22:coefficient=-16'sd760;
            6'd23:coefficient=-16'sd1118;
            6'd24:coefficient=-16'sd1137;
            6'd25:coefficient=-16'sd671;
            6'd26:coefficient=16'sd320;
            6'd27:coefficient=16'sd1731;
            6'd28:coefficient=16'sd3332;
            6'd29:coefficient=16'sd4810;
            6'd30:coefficient=16'sd5852;
            6'd31:coefficient=16'sd6230;
            6'd32:coefficient=16'sd5852;
            6'd33:coefficient=16'sd4810;
            6'd34:coefficient=16'sd3332;
            6'd35:coefficient=16'sd1731;
            6'd36:coefficient=16'sd320;
            6'd37:coefficient=-16'sd671;
            6'd38:coefficient=-16'sd1137;
            6'd39:coefficient=-16'sd1118;
            6'd40:coefficient=-16'sd760;
            6'd41:coefficient=-16'sd262;
            6'd42:coefficient=16'sd188;
            6'd43:coefficient=16'sd464;
            6'd44:coefficient=16'sd524;
            6'd45:coefficient=16'sd402;
            6'd46:coefficient=16'sd184;
            6'd47:coefficient=-16'sd36;
            6'd48:coefficient=-16'sd187;
            6'd49:coefficient=-16'sd238;
            6'd50:coefficient=-16'sd198;
            6'd51:coefficient=-16'sd107;
            6'd52:coefficient=-16'sd8;
            6'd53:coefficient=16'sd63;
            6'd54:coefficient=16'sd92;
            6'd55:coefficient=16'sd82;
            6'd56:coefficient=16'sd49;
            6'd57:coefficient=16'sd12;
            6'd58:coefficient=-16'sd17;
            6'd59:coefficient=-16'sd31;
            6'd60:coefficient=-16'sd32;
            6'd61:coefficient=-16'sd24;
            6'd62:coefficient=-16'sd10;
            default:coefficient=0;
        endcase end
    endfunction
    wire signed [31:0] product=tap_q*coefficient(tap);
    wire signed [39:0] sum=acc+{{8{product[31]}},product};
    wire signed [39:0] scaled=sum>>>15;
    integer k;
    initial for(k=0;k<64;k=k+1) history[k]=0;
    always @(posedge clk) begin
        tap_q<=history[ra];
        if(sample_en) history[wp]<=sample[23:8];
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            wp<=0;base<=0;tap<=0;decim<=0;busy<=0;phase<=0;
            acc<=0;emit<=0;valid<=0;filtered<=0;
        end else begin
            valid<=0;
            if(sample_en) begin
                base<=wp;wp<=wp+1'b1;decim<=decim+1'b1;
                emit<=decim==3;tap<=0;acc<=0;busy<=1;phase<=0;
            end else if(busy) begin
                if(phase!=2) phase<=phase+1'b1;
                else begin
                    acc<=sum;phase<=0;
                    if(tap==62) begin
                        busy<=0;
                        if(emit) begin
                            valid<=1;
                            filtered<=scaled>32767 ? 24'sh7fff00 : scaled< -32768 ? -24'sh800000 : {scaled[15:0],8'b0};
                        end
                    end else tap<=tap+1'b1;
                end
            end
        end
    end
endmodule
