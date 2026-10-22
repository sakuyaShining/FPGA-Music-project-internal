`timescale 1ns/1ps
`define COMMON_PORTS \
 .clk(clk),.rst_n(rst_n),.sample_en(sample_en),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1), \
 .load_en(load_en),.load_slot(load_slot),.load_inc(load_inc),.load_amp(load_amp),.load_gate(load_gate), \
 .load_start_tag(load_tag),.load_epar({16'd22938,2'd3,5'd12}),.load_gq(18'sd0), \
 .env_en(1'b1),.a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938), \
 .r_inc(16'd1),.r_m(2'd3),.r_k(5'd10),.env_cutoff(16'd100),.exp_mode(1'b1), \
 .pmod_cfg(58'd0),.finger_active(finger_active),.finger_offsets(finger_offsets),.sum_raw(),.slot_dbg()
module tb_engine;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;reg [8:0] cc=0;wire sample_en=cc==0;
    always @(posedge clk)if(!rst_n)cc<=0;else cc<=cc+1'b1;
    reg load_en=0,load_gate=0;reg[8:0]load_slot=0;reg[23:0]load_inc=0;reg[7:0]load_amp=0,load_tag=1;
    reg[31:0]finger_active=0;reg[575:0]finger_offsets=0;
    reg[159:0]gains={16{10'd256}};reg[31:0]mask=32'hffffffff;
    wire signed[23:0]pcm_ref,pcm_off,pcm_unit,pcm_dynamic;
    tdm_engine #(.NSLOT(512),.PART(16),.FINGER_EXPR(1),.EXPLICIT_START(1)) ref_core(`COMMON_PORTS,.sample_out(pcm_ref));
    tdm_engine_rh #(.NSLOT(512),.PART(16),.FINGER_EXPR(1),.EXPLICIT_START(1),.RIGHT_TIMBRE(0)) off_core(`COMMON_PORTS,
        .timbre_gain_q8({160{1'b1}}),.timbre_voice_mask(32'hffffffff),.sample_out(pcm_off));
    tdm_engine_rh #(.NSLOT(512),.PART(16),.FINGER_EXPR(1),.EXPLICIT_START(1),.RIGHT_TIMBRE(1)) unit_core(`COMMON_PORTS,
        .timbre_gain_q8({16{10'd256}}),.timbre_voice_mask(32'hffffffff),.sample_out(pcm_unit));
    tdm_engine_rh #(.NSLOT(512),.PART(16),.FINGER_EXPR(1),.EXPLICIT_START(1),.RIGHT_TIMBRE(1)) dynamic_core(`COMMON_PORTS,
        .timbre_gain_q8(gains),.timbre_voice_mask(mask),.sample_out(pcm_dynamic));
    reg[159:0]model_gains={16{10'd256}};reg[31:0]model_mask=0;
    reg[63:0]product;reg[15:0]expected_amp;integer gain,slot,i,cycles=0,samples=0,different=0,saturated=0,zeros=0,tail_updates=0;
    reg released=0,exact_return=0;
    always @(posedge clk)begin
        if(!rst_n)begin model_gains={16{10'd256}};model_mask=0;end
        else if(cycles>1024)begin
            slot=dynamic_core.sl1;
            if(slot==0)begin model_gains=gains;model_mask=mask;end
            gain=model_gains[(slot%16)*10+:10];if(gain<256)gain=256;
            product=dynamic_core.amp_eff;
            if(model_mask[slot/16])product=product*gain/256;
            if(product>65535)begin product=65535;saturated=saturated+1;end
            expected_amp=dynamic_core.increment_invalid?0:product[15:0];
            if(dynamic_core.amp_eff==0)zeros=zeros+1;
            if(released&&dynamic_core.amp_eff>0&&gain>256&&model_mask[slot/16])tail_updates=tail_updates+1;
            #1;if(dynamic_core.amp2!==expected_amp)$fatal(1,"read-side gain oracle mismatch slot%0d",slot);
        end else if(dynamic_core.sl1==0)begin model_gains=gains;model_mask=mask;end
    end
    always @(negedge clk)if(rst_n)begin
        cycles=cycles+1;
        if(cycles>1024)begin
            if(pcm_ref!==pcm_off||pcm_ref!==pcm_unit)$fatal(1,"unity/disabled PCM regression");
            if({ref_core.ph1,ref_core.inc1,ref_core.env1,ref_core.stg1,ref_core.gc1,ref_core.gq1,ref_core.amp1,ref_core.epar1,ref_core.pe1,ref_core.pgq1,ref_core.effective_poff} !==
               {dynamic_core.ph1,dynamic_core.inc1,dynamic_core.env1,dynamic_core.stg1,dynamic_core.gc1,dynamic_core.gq1,dynamic_core.amp1,dynamic_core.epar1,dynamic_core.pe1,dynamic_core.pgq1,dynamic_core.effective_poff})
                $fatal(1,"phase/envelope/base/ownership state changed with timbre");
            if(sample_en)begin
                samples=samples+1;
                if(pcm_ref!==pcm_dynamic)different=different+1;
                if(exact_return&&pcm_ref!==pcm_dynamic)$fatal(1,"unity return not bit exact");
            end
        end
    end
    task load_all;
        input onoff;input[7:0]tag;
        begin
            for(i=0;i<512;i=i+1)begin
                @(negedge clk);load_en=1;load_slot=i;load_gate=onoff;load_tag=tag;
                load_inc=10000*(i/16+1)+3000*(i%16+1);
                load_amp=((i%16)==6||(i%16)==13)?0:(((i%16)==0)?255:4);
            end
            @(negedge clk);load_en=0;
        end
    endtask
    initial begin
        repeat(5)@(negedge clk);rst_n=1;load_all(1,1);
        repeat(512*96)@(negedge clk);
        @(negedge clk);for(i=0;i<16;i=i+1)gains[i*10+:10]=(i%2)?512:320;
        repeat(512*64+117)@(negedge clk);
        mask=32'haaaaaaab;finger_active=1;finger_offsets[17:0]=18'sd4096;
        repeat(512*64)@(negedge clk);
        gains={16{10'd1023}};mask=32'hffffffff;
        repeat(512*512)@(negedge clk);
        load_all(0,1);released=1;
        repeat(512*100)@(negedge clk);
        gains={16{10'd512}};finger_offsets[17:0]=-18'sd4096;
        repeat(512*100)@(negedge clk);
        // New note during active modifiers, retaining the same global modifier.
        @(negedge clk);load_en=1;load_slot=0;load_gate=1;load_tag=2;load_amp=100;load_inc=24000;
        @(negedge clk);load_en=0;
        repeat(512*30)@(negedge clk);
        gains={16{10'd256}};mask=0;
        repeat(512*3)@(negedge clk);exact_return=1;
        repeat(512*60)@(negedge clk);
        if(samples<900||different<100||saturated<10||zeros<100||tail_updates<100)$fatal(1,"insufficient coverage samples%0d diff%0d sat%0d zero%0d tails%0d",samples,different,saturated,zeros,tail_updates);
        $display("PASS engine cycles=%0d samples=%0d changed_pcm=%0d saturated=%0d zero_checks=%0d tail_gain_updates=%0d unity_off_exact state_preserved",cycles,samples,different,saturated,zeros,tail_updates);$finish;
    end
    initial begin #20000000;$fatal(1,"engine watchdog");end
endmodule
`undef COMMON_PORTS
