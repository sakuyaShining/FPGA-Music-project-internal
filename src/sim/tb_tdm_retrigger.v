`timescale 1ns/1ps
// Exercise real 512-slot pending-gate consumption, not only the envelope unit.
module tb_tdm_retrigger;
    reg clk=0,rst=0,en=0,gate=0;
    reg [8:0] pc=0,slot=0;
    integer i,beat;
    reg [15:0] prior [0:15];
    always #5 clk=~clk;
    always @(posedge clk) if(!rst)pc<=0;else pc<=pc+1'b1;
    tdm_engine #(.NSLOT(512),.PART(16)) dut(
        .clk(clk),.rst_n(rst),.sample_en(pc==0),.clr(1'b0),.pclr(1'b0),.gate_in(1'b0),
        .load_en(en),.load_slot(slot),.load_inc(24'd100000),.load_amp(8'd180),
        .load_gate(gate),.load_epar({16'd0,2'd3,5'd9}),
        .env_en(1'b1),.a_inc(16'd1024),.d_inc(16'd64),.d_m(2'd0),.d_k(5'd0),
        .s_lvl(16'd0),.r_inc(16'd64),.r_m(2'd3),.r_k(5'd4),.env_cutoff(16'd10),
        .exp_mode(1'b1),.load_gq(18'sd0),.pmod_cfg(58'd0),
        .finger_active(32'd0),.finger_offsets(576'd0));
    task group_gate;
        input value;
        integer k;
        begin
            while(pc!=300)@(negedge clk);
            for(k=0;k<16;k=k+1)begin
                slot=k;gate=value;en=1;@(negedge clk);
            end
            en=0;
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst=1;
        group_gate(1);repeat(512*70)@(negedge clk);
        for(beat=0;beat<8;beat=beat+1)begin
            group_gate(0);repeat(512*4)@(negedge clk);
            for(i=0;i<16;i=i+1)begin
                if(dut.stg_mem[i]!==4)$fatal(1,"expected releasing partial=%0d",i);
            end
            group_gate(1);repeat(512*4)@(negedge clk);
            for(i=0;i<16;i=i+1)begin
                if(dut.stg_mem[i]!==1)
                    $fatal(1,"rapid re-press lost beat=%0d partial=%0d stage=%0d level=%0d prior=%0d",beat,i,dut.stg_mem[i],dut.env_mem[i],prior[i]);
                prior[i]=dut.env_mem[i];
            end
            repeat(512*2)@(negedge clk);
            for(i=0;i<16;i=i+1)if(dut.env_mem[i]<=prior[i])
                $fatal(1,"reattack did not grow partial=%0d",i);
            repeat(512*40)@(negedge clk);
        end
        group_gate(0);repeat(512*200)@(negedge clk);
        for(i=0;i<16;i=i+1)if(dut.env_mem[i]!==0 || dut.stg_mem[i]!==0)
            $fatal(1,"stuck note partial=%0d",i);
        $display("RESULT tdm_retrigger=PASS 512-slot engine, 16 partials, 8 re-presses, final silence");
        $finish;
    end
    initial begin #10000000;$fatal(1,"timeout");end
endmodule
