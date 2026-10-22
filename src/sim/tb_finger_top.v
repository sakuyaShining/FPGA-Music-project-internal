`timescale 1ns/1ps
module tb_finger_top;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg ev=0,on=0; reg [6:0] note=0;
    reg fv=0; reg [1:0] fc=0; reg [4:0] fid=0,fg=0;
    reg signed [11:0] fp=0;
    wire vv,vo;wire [4:0] vg;wire [6:0] vn;
    wire [15:0] pads;
    tdm_top #(.FINGER_EXPR(1)) u(.clk(clk),.rst_n(rst_n),
        .ev_valid(ev),.ev_on(on),.ev_note(note),.ev_vel(4'd12),
        .preset(2'd1),.test_mode(1'b0),.uart_rx_pin(1'b1),.uart_tx_pin(),
        .led(),.dac_din(),.dac_ws(),.dac_bck(),.pa_en(),.pad(pads),
        .finger_valid(fv),.finger_cmd(fc),.finger_id(fid),.finger_group(fg),
        .finger_position(fp),.voice_valid(vv),.voice_on(vo),.voice_group(vg),.voice_note(vn));
    integer g60=-1,g64=-1,checks=0;
    reg monitor=0;
    reg signed [17:0] group_q [0:31];
    integer gg,pp;
    always @(posedge clk) begin
        if(vv && vo && vn==60) g60=vg;
        if(vv && vo && vn==64) g64=vg;
        if(monitor) begin
            gg=u.u_tdm.sl1[8:4]; pp=u.u_tdm.sl1[3:0];
            if(pp==0) group_q[gg]=u.u_tdm.effective_poff;
            else if(u.u_tdm.effective_poff !== group_q[gg])
                $fatal(1,"expression split inside group %0d partial %0d",gg,pp);
            if(u.u_tdm.trig_on) $fatal(1,"movement retriggered envelope");
            checks=checks+1;
        end
    end
    task event_note;
        input b;input [6:0] n;
        begin
            @(negedge clk);ev=1;on=b;note=n;
            @(negedge clk);ev=0;
            repeat(1200) @(negedge clk);
        end
    endtask
    task send;
        input [1:0] c;input [4:0] f,g;input signed [11:0] p;
        begin
            @(negedge clk);fv=1;fc=c;fid=f;fg=g;fp=p;
            @(negedge clk);fv=0;
        end
    endtask
    task check_pitch;
        input integer g, q;
        integer k,inc,want;
        reg signed [63:0] reference_product;
        begin
            // Wait for a complete group traversal after the last update.
            repeat(1100) @(negedge clk);
            for(k=0;k<16;k=k+1) begin
                while(u.u_tdm.sl1 !== g*16+k) @(negedge clk);
                inc=u.u_tdm.eff_inc;
                reference_product=inc;
                reference_product=reference_product * q;
                want=inc + (reference_product >>> 16);
                if(u.u_tdm.effective_poff !== q)
                    $fatal(1,"group %0d offset %0d want %0d",g,u.u_tdm.effective_poff,q);
                if(u.u_tdm.ph_n !== ((u.u_tdm.ph1 + want) & 24'hffffff))
                    $fatal(1,"phase increment mismatch");
                @(negedge clk);
            end
        end
    endtask
    integer i;
    reg signed [17:0] rom [0:512];
    initial begin
        $readmemh("finger_ratio.hex",rom);
        repeat(5) @(negedge clk);rst_n=1;
        repeat(100) @(negedge clk);
        event_note(1,60);event_note(1,64);
        if(g60<0 || g64<0 || g60==g64) $fatal(1,"allocation notification incorrect");
        send(0,1,g60,100);send(0,2,g64,-100);
        send(1,1,0,228);send(1,2,0,-228);
        check_pitch(g60,rom[384]);check_pitch(g64,rom[128]);
        // Start coherence checks on a first partial, then update every few clocks.
        while(u.u_tdm.sl1[3:0] !== 0) @(negedge clk);
        monitor=1;
        for(i=0;i<80;i=i+1) begin
            send(1,1,0,100+(i%2 ? 8 : -8));
            repeat(7) @(negedge clk);
        end
        send(1,1,0,100);check_pitch(g60,0);check_pitch(g64,rom[128]);
        monitor=0;
        // Release, allocate a new note into the free group, reject stale movement.
        event_note(0,60);event_note(1,67);
        send(1,1,0,356);check_pitch(g60,0);
        if(u.contact_expression.u_finger.owned[g60]) $fatal(1,"stale ownership after reuse");
        // Exercise the full 5-bit engine group index, not just low voices.
        for(i=20;i<50;i=i+1) event_note(1,i);
        if(u.u_nm.gtab[31] !== 49) $fatal(1,"highest group not allocated");
        send(0,3,31,0);send(1,3,0,256);check_pitch(31,65536);
        check_pitch(g64,rom[128]);
        // A live owned voice is stolen after all 32 groups are occupied.
        send(0,4,0,0);send(1,4,0,256);check_pitch(0,65536);
        event_note(1,100);send(1,4,0,-256);
        if(u.contact_expression.u_finger.owned[0] || u.finger_active[0])
            $fatal(1,"stolen group kept expression ownership");
        if(checks<1000) $fatal(1,"insufficient coherence coverage");
        $display("PASS finger_top: allocator binding, independent notes, group 31, 16 partials, continuous updates, no retrigger, release/reuse/steal (%0d checks)",checks);
        $finish;
    end
    initial begin #5000000; $fatal(1,"timeout"); end
endmodule
