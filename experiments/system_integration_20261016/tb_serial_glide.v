`timescale 1ns/1ps
module tb_serial_glide;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,sample_en=0,gw_en=0,vib_en=0,glide_en=0;
    reg [23:0] lfo_inc=0;
    reg [15:0] vib_depth=0,glide_step=0;
    reg [4:0] gw_note=0,rd_note=0;
    reg signed [17:0] gw_val=0;
    wire signed [17:0] actual,expected;
    wire overrun;
    pitch_mod dut(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),.lfo_inc(lfo_inc),.vib_depth(vib_depth),.glide_step(glide_step),.vib_en(vib_en),.glide_en(glide_en),.gw_en(gw_en),.gw_note(gw_note),.gw_val(gw_val),.rd_note(rd_note),.poff(actual),.update_overrun(overrun));
    pitch_mod_reference ref_mod(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),.lfo_inc(lfo_inc),.vib_depth(vib_depth),.glide_step(glide_step),.vib_en(vib_en),.glide_en(glide_en),.gw_en(gw_en),.gw_note(gw_note),.gw_val(gw_val),.rd_note(rd_note),.poff(expected));
    reg [31:0] random_state=32'h20261016;
    function [31:0] next_random;
        input [31:0] v;
        reg [31:0] t;
        begin t=v^(v<<13);t=t^(t>>17);next_random=t^(t<<5);end
    endfunction
    integer cycle=0,loads=0,epochs=0,checks=0,g;
    task check_all;
        begin
            if(actual!==expected||dut.lfo_ph!==ref_mod.lfo_ph)$fatal(1,"pitch output mismatch cycle=%0d actual=%d ref=%d",cycle,actual,expected);
            for(g=0;g<32;g=g+1)
                if((dut.pending[g]?dut.advance(dut.gq[g],dut.step_held):dut.gq[g])!==ref_mod.gq[g])$fatal(1,"logical group state mismatch cycle=%0d group=%0d",cycle,g);
            if(overrun)$fatal(1,"unexpected scheduling overrun");checks=checks+1;
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        for(cycle=0;cycle<40000;cycle=cycle+1)begin
            @(negedge clk);random_state=next_random(random_state);
            sample_en=cycle%64==0;rd_note=random_state[4:0];gw_note=random_state[9:5];gw_en=random_state[12:10]==0;
            gw_val=random_state[30:13];vib_en=random_state[1];glide_en=random_state[2];
            lfo_inc=random_state[23:0];vib_depth=random_state[31:16];glide_step=(cycle%257==0)?0:random_state[15:0];
            if(sample_en)epochs=epochs+1;if(gw_en)loads=loads+1;
            #1;check_all;@(posedge clk);#1;check_all;
        end
        // Unsupported cadence must produce a diagnostic, never be advertised
        // as an accepted operating mode. The full chain's period is512.
        @(negedge clk);gw_en=0;sample_en=1;@(negedge clk);sample_en=0;@(negedge clk);sample_en=1;
        @(posedge clk);#1;if(!overrun)$fatal(1,"overrun diagnostic missing");
        $display("PASS serial_glide cycles=40000 checks=%0d group_state_checks=%0d loads=%0d epochs=%0d step_changes write_races bypass_lfo_exact overrun_detected",checks,checks*32,loads,epochs);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
