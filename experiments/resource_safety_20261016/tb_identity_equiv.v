`timescale 1ns/1ps
module tb_identity_equiv;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ev_valid=0,ev_on=0,ev_owned=0,refresh=0,cfg_valid=0,cfg_commit=0;
    reg [6:0] ev_note=0;
    reg [7:0] ev_vel=0;
    reg [14:0] ev_instance=0;
    reg [1:0] preset=0,own_preset=0,cfg_slot=0;
    reg [3:0] cfg_part=0;
    reg [47:0] cfg_word=0;
    wire [31:0] active_a,active_b;
    wire ack_a,ack_b,busy_a,busy_b,lv_a,lv_b,lg_a,lg_b,rv_a,rv_b,ro_a,ro_b,ron_a,ron_b,rs_a,rs_b,vv_a,vv_b,von_a,von_b;
    wire [8:0] ls_a,ls_b;
    wire [23:0] li_a,li_b;
    wire [7:0] la_a,la_b,tag_a,tag_b;
    wire [22:0] le_a,le_b;
    wire signed [17:0] lq_a,lq_b;
    wire [14:0] ri_a,ri_b;
    wire [4:0] rg_a,rg_b,vg_a,vg_b;
    wire [6:0] vn_a,vn_b;
    wire cr_a,cr_b,ca_a,ca_b,ce_a,ce_b;
`define PORTS(S) .clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.ev_owned(ev_owned),.ev_instance(ev_instance),.preset(preset),.own_preset(own_preset),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cr_``S),.cfg_applied(ca_``S),.cfg_error(ce_``S),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd32),.load_en(lv_``S),.load_slot(ls_``S),.load_inc(li_``S),.load_amp(la_``S),.load_gate(lg_``S),.load_start_tag(tag_``S),.load_epar(le_``S),.load_gq(lq_``S),.busy(busy_``S),.ev_ack(ack_``S),.active(active_``S),.result_valid(rv_``S),.result_owned(ro_``S),.result_on(ron_``S),.result_success(rs_``S),.result_instance(ri_``S),.result_group(rg_``S),.voice_valid(vv_``S),.voice_on(von_``S),.voice_group(vg_``S),.voice_note(vn_``S)
    note_map_owned #(.OWNED_EVENTS(1),.OWNER_W(15),.SPEC_STAGED(1),.GLIDE_EN(1)) dut(`PORTS(a));
    note_map_reference #(.OWNED_EVENTS(1),.OWNER_W(15),.SPEC_STAGED(1),.GLIDE_EN(1)) ref_impl(`PORTS(b));
    integer clocks=0,events=0,loads=0,results=0,i,j;
    reg [31:0] rng=32'h71398aff;
    task random_step;begin rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);end endtask
    always @(negedge clk)begin
        if({ack_a,busy_a,active_a,lv_a,ls_a,li_a,la_a,lg_a,tag_a,le_a,lq_a,rv_a,ro_a,ron_a,rs_a,ri_a,rg_a,vv_a,von_a,vg_a,vn_a,cr_a,ca_a,ce_a}!==
           {ack_b,busy_b,active_b,lv_b,ls_b,li_b,la_b,lg_b,tag_b,le_b,lq_b,rv_b,ro_b,ron_b,rs_b,ri_b,rg_b,vv_b,von_b,vg_b,vn_b,cr_b,ca_b,ce_b})$fatal(1,"identity output mismatch clock=%0d",clocks);
        for(j=0;j<32;j=j+1)begin
            if({dut.gtab[j],dut.group_velocity[j],dut.group_start_tag[j],dut.group_owned[j],dut.gact[j]}!=={ref_impl.gtab[j],ref_impl.group_velocity[j],ref_impl.group_start_tag[j],ref_impl.group_owned[j],ref_impl.gact[j]})$fatal(1,"group metadata mismatch");
            if(dut.gact[j]&&dut.group_owned[j]&&dut.group_instance[j]!==ref_impl.group_instance[j])$fatal(1,"active identity mismatch");
        end
        if(dut.st==1&&dut.owned_hold&&dut.gact[dut.owner_index]&&dut.group_owned[dut.owner_index]&&dut.scanned_instance!==ref_impl.group_instance[dut.owner_index])$fatal(1,"prefetch missed row");
    end
    always @(posedge clk)if(rst_n)begin clocks=clocks+1;if(lv_a)loads=loads+1;if(rv_a)results=results+1;end
    initial begin
        repeat(3)@(posedge clk);@(negedge clk);rst_n=1;
        for(i=0;i<5000;i=i+1)begin
            @(posedge clk);#2;
            while(busy_a)begin @(posedge clk);#2;end
            random_step;ev_valid=1;ev_on=(i<96)?1:rng[0]|rng[1];ev_note=(i<96)?i[6:0]:rng[8:2];ev_owned=(i<96)?i[0]:rng[9];ev_vel=rng[17:10];ev_instance=(i<96)?i:rng[14:0];preset=rng[19:18];own_preset=rng[21:20];
            if(i%11==0)ev_note=127;
            if(i%7==0)ev_instance=i%32;
            @(posedge clk);while(!ack_a)@(posedge clk);#2;ev_valid=0;events=events+1;
            random_step;
            refresh=(i%73==0);cfg_valid=(i%13==0);cfg_commit=rng[1];cfg_slot=rng[3:2];cfg_part=rng[7:4];cfg_word={16'h0100,rng[15:8],1'b0,16'd15000,2'd3,rng[4:0]};
            repeat(2)@(posedge clk);#2;refresh=0;cfg_valid=0;
            if(i==1700||i==3400)begin rst_n=0;repeat(3)@(posedge clk);#2;rst_n=1;end
        end
        repeat(800)@(posedge clk);#2;
        $display("PASS identity_equiv events=%0d clocks=%0d group_checks=%0d loads=%0d results=%0d cycle_exact prefetch full32 MIDI127 stale_keys refresh cfg reset",events,clocks,clocks*32,loads,results);$finish;
    end
    initial begin #50000000;$fatal(1,"watchdog");end
endmodule
