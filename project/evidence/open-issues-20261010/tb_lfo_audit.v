`timescale 1ns/1ps
module tb_lfo_audit;
    wire signed [17:0] poff;
    pitch_mod u(.clk(1'b0),.rst_n(1'b1),.sample_en(1'b0),
        .lfo_inc(24'd0),.vib_depth(16'd1000),.glide_step(16'd0),
        .vib_en(1'b1),.glide_en(1'b0),.gw_en(1'b0),.gw_note(5'd0),
        .gw_val(18'sd0),.rd_note(5'd0),.poff(poff));
    initial begin
        force u.lfo_ph=24'h7f0000;#1;
        $display("before half-period: lfo_t=%0d, poff=%0d",u.lfo_t,poff);
        force u.lfo_ph=24'h800000;#1;
        $display("after half-period: lfo_t=%0d, poff=%0d",u.lfo_t,poff);
        force u.lfo_ph=24'hff0000;#1;
        $display("before wrap: lfo_t=%0d, poff=%0d",u.lfo_t,poff);
        force u.lfo_ph=24'h000000;#1;
        $display("after wrap: lfo_t=%0d, poff=%0d",u.lfo_t,poff);
        $finish;
    end
endmodule
