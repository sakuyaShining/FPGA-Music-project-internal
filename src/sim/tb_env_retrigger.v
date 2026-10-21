`timescale 1ns/1ps
// Rapid re-press must restart ATTACK before the previous release has ended.
module tb_env_retrigger;
    reg [15:0] lvl;
    reg [2:0] stage;
    reg on, rel, exponential;
    wire [15:0] next_lvl;
    wire [2:0] next_stage;
    integer failures=0, mode, state, i;
    reg [15:0] before;
    osc_env dut(.lvl_i(lvl),.stg_i(stage),.trig_on(on),.trig_rel(rel),
        .a_inc(16'd512),.d_inc(16'd64),.d_m(2'd3),.d_k(5'd10),
        .s_lvl(16'd0),.r_inc(16'd64),.r_m(2'd3),.r_k(5'd11),
        .cutoff(16'd100),.exp_mode(exponential),.lvl_o(next_lvl),.stg_o(next_stage));
    task step;
        begin #1;lvl=next_lvl;stage=next_stage;#1;end
    endtask
    initial begin
        on=0;rel=0;exponential=0;lvl=0;stage=0;
        for(mode=0;mode<2;mode=mode+1) begin
            exponential=mode;
            // Repeat while a previous note is still releasing, at several levels.
            for(i=0;i<3;i=i+1) begin
                lvl=(i==0)?16'd22000:((i==1)?16'd100:16'd0);stage=4;
                before=lvl;on=1;rel=0;step;
                if(stage!==1 || lvl!==before) begin
                    $display("FAIL release retrigger mode=%0d level=%0d stage=%0d next=%0d",mode,before,stage,lvl);
                    failures=failures+1;
                end
                on=0;step;
                if(lvl<=before) begin
                    $display("FAIL re-pressed note did not grow mode=%0d",mode);
                    failures=failures+1;
                end
            end
            // Every non-idle state can be re-used; do not retain a decaying envelope.
            for(state=1;state<=3;state=state+1) begin
                lvl=12000;stage=state;on=1;step;
                if(stage!==1 || lvl!==12000) failures=failures+1;
                on=0;
            end
            // Existing idle start and ordinary release retain their semantics.
            lvl=0;stage=0;on=1;step;
            if(stage!==1 || lvl!==0) failures=failures+1;
            on=0;repeat(70)step;
            rel=1;step;rel=0;
            if(stage!==4) failures=failures+1;
            before=lvl;step;
            if(lvl>=before) failures=failures+1;
            repeat(15000)step;
            if(stage!==0 || lvl!==0) failures=failures+1;
        end
        if(failures) $fatal(1,"RETRIGGER FAIL checks=%0d",failures);
        $display("RETRIGGER PASS linear/exponential, release-level continuity, restart, final silence");
        $finish;
    end
endmodule
