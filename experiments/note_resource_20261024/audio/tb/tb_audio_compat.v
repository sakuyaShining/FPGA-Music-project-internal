`timescale 1ns/1ps
module tb_audio_compat;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;
    reg [8:0] tick=0;
    wire sample_en=tick==511;
    always @(posedge clk)if(!rst_n)tick<=0;else tick<=tick+1'b1;
    reg load_en=0,load_gate=0;
    reg [8:0] load_slot=0;
    reg [23:0] load_inc=0;
    reg [7:0] load_amp=0,load_start_tag=0;
    reg [22:0] load_epar=0;
    reg [39:0] load_env=0;
    reg signed [17:0] load_gq=0;
    wire [57:0] pmod_cfg={24'd19218,16'd200,16'd11,2'b11};
    reg [159:0] timbre_gain_q8={16{10'd256}};
    reg [31:0] timbre_voice_mask=0,finger_active=0;
    reg [575:0] finger_offsets=0;
    wire signed [23:0] actual,expected;
    wire [31:0] actual_sum,expected_sum;
    tdm_engine_rh #(.NSLOT(512),.PART(16),.EXPLICIT_START(1),.INSTRUMENT_ENV(1),.RIGHT_TIMBRE(1),.FINGER_EXPR(1)) original(
        .clk(clk),.rst_n(rst_n),.sample_en(sample_en),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1),
        .load_en(load_en),.load_slot(load_slot),.load_inc(load_inc),.load_amp(load_amp),.load_gate(load_gate),
        .load_start_tag(load_start_tag),.load_epar(load_epar),.load_env(load_env),.load_gq(load_gq),
        .pmod_cfg(pmod_cfg),.finger_active(finger_active),.finger_offsets(finger_offsets),
        .timbre_gain_q8(timbre_gain_q8),.timbre_voice_mask(timbre_voice_mask),.env_en(1'b1),
        .a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938),
        .r_inc(16'd1),.r_m(2'd3),.r_k(5'd13),.d2_lvl(16'd10000),.d2_k(5'd15),.env_cutoff(16'd100),.exp_mode(1'b1),
        .sample_out(expected),.sum_raw(expected_sum),.slot_dbg());
    tdm_engine_transactional #(.NSLOT(512),.PART(16),.EXPLICIT_START(1),.INSTRUMENT_ENV(1),.RIGHT_TIMBRE(1),.FINGER_EXPR(1)) candidate(
        .clk(clk),.rst_n(rst_n),.sample_en(sample_en),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1),
        .load_en(load_en),.load_slot(load_slot),.load_inc(load_inc),.load_amp(load_amp),.load_gate(load_gate),
        .load_start_tag(load_start_tag),.load_epar(load_epar),.load_env(load_env),.load_gq(load_gq),
        .load_kill(1'b0),.publish_valid(1'b0),.publish_ready(),.publish_groups(32'd0),.publish_done(),.quiet_groups(),
        .pmod_cfg(pmod_cfg),.finger_active(finger_active),.finger_offsets(finger_offsets),
        .timbre_gain_q8(timbre_gain_q8),.timbre_voice_mask(timbre_voice_mask),.env_en(1'b1),
        .a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938),
        .r_inc(16'd1),.r_m(2'd3),.r_k(5'd13),.d2_lvl(16'd10000),.d2_k(5'd15),.env_cutoff(16'd100),.exp_mode(1'b1),
        .sample_out(actual),.sum_raw(actual_sum),.slot_dbg());
    reg [31:0] random_state=32'h261024a5;
    integer cycle,checked=0;
    initial begin
        repeat(8)@(negedge clk);rst_n=1;
        for(cycle=0;cycle<180000;cycle=cycle+1)begin
            @(negedge clk);
            random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
            load_en=cycle%5==0;load_slot=random_state[8:0];load_gate=random_state[9];
            load_inc=24'd10000+random_state[21:10];load_amp=random_state[15:8];
            load_start_tag=random_state[31:24];load_epar={16'd18000,2'd3,5'd12};
            load_env={4'd0,1'b1,4'd0,16'd117,4'd0,4'd0,2'd3,5'd13};
            load_gq=$signed({2'b00,random_state[15:0]})>>>4;
            if(cycle%512==0)begin
                timbre_voice_mask=random_state;finger_active=~random_state;
                timbre_gain_q8={16{10'd256+{2'd0,random_state[7:0]}}};
                finger_offsets={32{18'd111}};
            end
            if(cycle>2048)begin
                if(actual!==expected||actual_sum!==expected_sum||^actual===1'bx)$fatal(1,"legacy PCM changed");
                if(candidate.env_mem[load_slot]!==original.env_mem[load_slot]||
                   candidate.stg_mem[load_slot]!==original.stg_mem[load_slot]||
                   candidate.phase_mem[load_slot]!==original.phase_mem[load_slot])$fatal(1,"legacy state changed");
                checked=checked+1;
            end
        end
        $display("PASS legacy_audio checked_clocks=%0d",checked);$finish;
    end
endmodule
