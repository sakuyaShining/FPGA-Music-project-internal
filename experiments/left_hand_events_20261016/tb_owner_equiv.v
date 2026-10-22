`timescale 1ns/1ps
module tb_owner_equiv;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ev_valid=0,ev_on=0,ev_owned=0;
    reg [6:0] ev_note=60;
    reg [7:0] ev_vel=128;
    reg [12:0] instance_id=0;
    wire [1:0] busy,rv,ro,ron,rs,load,gate;
    wire [12:0] rid[0:1];wire [4:0] rg[0:1];wire [31:0] active[0:1];
    wire [8:0] slot[0:1];wire [23:0] inc[0:1];wire [7:0] amp[0:1],tag[0:1];wire [22:0] epar[0:1];wire signed [17:0] gq[0:1];
    note_map_owned #(.OWNED_EVENTS(1)) serial(.clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.ev_owned(ev_owned),.ev_instance(instance_id),
        .preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(1'b0),.rf_lo(7'd0),.rf_hi(8'd32),
        .load_en(load[0]),.load_slot(slot[0]),.load_inc(inc[0]),.load_amp(amp[0]),.load_gate(gate[0]),.load_start_tag(tag[0]),.load_epar(epar[0]),.load_gq(gq[0]),.busy(busy[0]),.active(active[0]),
        .result_valid(rv[0]),.result_owned(ro[0]),.result_on(ron[0]),.result_success(rs[0]),.result_instance(rid[0]),.result_group(rg[0]));
    note_map_owned_parallel #(.OWNED_EVENTS(1)) parallel(.clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.ev_owned(ev_owned),.ev_instance(instance_id),
        .preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(1'b0),.rf_lo(7'd0),.rf_hi(8'd32),
        .load_en(load[1]),.load_slot(slot[1]),.load_inc(inc[1]),.load_amp(amp[1]),.load_gate(gate[1]),.load_start_tag(tag[1]),.load_epar(epar[1]),.load_gq(gq[1]),.busy(busy[1]),.active(active[1]),
        .result_valid(rv[1]),.result_owned(ro[1]),.result_on(ron[1]),.result_success(rs[1]),.result_instance(rid[1]),.result_group(rg[1]));
    reg [90:0] loads0[0:31],loads1[0:31];
    reg [20:0] result0,result1;
    integer count0=0,count1=0,at0=0,at1=0,cycle=0,event_no=0,g,k,checked_loads=0,max_extra=0;
    reg [31:0] random_state=32'h20261017;
    function [31:0] rnd;
        input [31:0] v;reg [31:0] t;
        begin t=v^(v<<13);t=t^(t>>17);rnd=t^(t<<5);end
    endfunction
    always @(posedge clk)if(rst_n)begin
        cycle=cycle+1;
        if(load[0])begin loads0[count0]={slot[0],inc[0],amp[0],gate[0],tag[0],epar[0],gq[0]};count0=count0+1;end
        if(load[1])begin loads1[count1]={slot[1],inc[1],amp[1],gate[1],tag[1],epar[1],gq[1]};count1=count1+1;end
        if(rv[0])begin result0={ro[0],ron[0],rs[0],rid[0],rg[0]};at0=cycle;end
        if(rv[1])begin result1={ro[1],ron[1],rs[1],rid[1],rg[1]};at1=cycle;end
    end
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        for(event_no=0;event_no<500;event_no=event_no+1)begin
            @(negedge clk);while(|busy)@(negedge clk);repeat(2)@(negedge clk);
            count0=0;count1=0;at0=0;at1=0;random_state=rnd(random_state);
            ev_owned=event_no<36?1'b1:random_state[0]||random_state[1];
            ev_on=event_no<32?1'b1:(event_no==32||event_no==35)?1'b0:random_state[2]||random_state[3];
            instance_id=event_no<32?event_no:(event_no==32||event_no==35)?31:event_no==33?8191:random_state%80;
            ev_note=ev_owned?60:40+random_state[6:4];ev_vel=random_state[15:8];ev_valid=1;
            @(negedge clk);ev_valid=0;while(|busy)@(negedge clk);repeat(2)@(negedge clk);
            if(!at0||!at1||result0!==result1||count0!=count1||active[0]!==active[1]||serial.rr!==parallel.rr)$fatal(1,"allocation mismatch event=%0d",event_no);
            if(at0-at1>31||at0<at1||(!ev_owned&&at0!=at1))$fatal(1,"unbounded/legacy timing change");
            if(at0-at1>max_extra)max_extra=at0-at1;
            for(k=0;k<count0;k=k+1)begin if(loads0[k]!==loads1[k])$fatal(1,"partial load mismatch");checked_loads=checked_loads+1;end
            for(g=0;g<32;g=g+1)
                if({serial.gtab[g],serial.group_instance[g],serial.group_owned[g],serial.group_start_tag[g],serial.group_velocity[g]}!=={parallel.gtab[g],parallel.group_instance[g],parallel.group_owned[g],parallel.group_start_tag[g],parallel.group_velocity[g]})$fatal(1,"group state mismatch event=%0d group=%0d",event_no,g);
        end
        $display("PASS owner_equiv events=500 groups=32 partial_load_checks=%0d max_added_owned_clocks=%0d legacy_timing_exact allocation_state_exact arbitrary_instance_ids full32",checked_loads,max_extra);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
