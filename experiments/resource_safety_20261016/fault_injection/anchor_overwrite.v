// Continuous expression endpoint, not a physical touch tracker.
// Upstream binds a contact ID to an allocator-confirmed group, then sends
// chronological calibrated positions. 256 position units = one octave.
// Bind captures the position anchor; movement changes pitch without note-on.
// Same-pitch independent allocation and sensor identity tracking are upstream.
module finger_pitch #(parameter NG=32, parameter NF=32, parameter MULTI_BIND=0)(
    input wire clk, rst_n,
    input wire cmd_valid,
    input wire [1:0] cmd, // 0 bind, 1 move, 2 release
    input wire [$clog2(NF)-1:0] finger,
    input wire [$clog2(NG)-1:0] group,
    input wire signed [11:0] position,
    input wire voice_valid, voice_on,
    input wire [$clog2(NG)-1:0] voice_group,
    input wire [NG-1:0] voice_active,
    output wire [NG-1:0] expr_active,
    output wire [NG*18-1:0] expr_offsets
);
    reg [NG-1:0] owned, enabled;
    reg [$clog2(NF)-1:0] owner [0:NG-1];
    localparam FA=1<<$clog2(NF);
    reg signed [11:0] contact_anchor [0:FA-1];
    reg signed [17:0] offset [0:NG-1];
    // Five hex digits occupy 20 bits in Gowin's memory initializer.
    reg [19:0] ratio_rom [0:512];
    initial $readmemh("finger_ratio.hex", ratio_rom);
    assign expr_active = enabled;
    genvar g;
    generate for(g=0;g<NG;g=g+1) begin: pack
        assign expr_offsets[g*18 +: 18] = offset[g];
    end endgenerate
    // One shared lookup, rather than a separate ROM read for every voice.
    wire [NG-1:0] mine;
    generate for(g=0;g<NG;g=g+1) begin: finger_matches
        assign mine[g]=owned[g]&&owner[g]==finger;
    end endgenerate
    // All groups of one owned contact have the same anchor (bind invariant).
    // Release tails retain per-group offsets; only anchors are shared.
    wire signed [11:0] moving_anchor=(|mine)?contact_anchor[finger]:position;
    wire signed [12:0] delta = $signed({position[11],position}) -
                              $signed({moving_anchor[11],moving_anchor});
    wire [12:0] biased_delta=delta+13'sd256;
    wire [9:0] address = delta>256 ? 10'd512 : delta < -256 ? 10'd0 : biased_delta[9:0];
    wire signed [17:0] movement_offset=ratio_rom[address][17:0];
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            owned <= 0; enabled <= 0;
            for(i=0;i<NG;i=i+1) begin
                owner[i]<=0; offset[i]<=0;
            end
            for(i=0;i<FA;i=i+1)contact_anchor[i]<=0;
        end else begin
            if(cmd_valid&&cmd==0&&group<NG&&voice_active[group])
                contact_anchor[finger]<=position;
            for(i=0;i<NG;i=i+1) begin
                if(cmd_valid) begin
                    if(cmd==0) begin
                        // A contact can own only one group. An old release tail
                        // retains its last pitch, but no longer accepts movement.
                        if(!MULTI_BIND && owned[i] && owner[i]==finger) owned[i]<=0;
                        if(group==i && voice_active[i]) begin
                            owner[i]<=finger;
                            owned[i]<=1; enabled[i]<=1; offset[i]<=0;
                        end
                    end else if(owned[i] && owner[i]==finger) begin
                        if(cmd==1) begin
                            offset[i]<=movement_offset;
                        end else if(cmd==2) owned[i]<=0;
                    end
                end
                // Allocator reuse wins over commands: an old finger must never
                // move the newly allocated note, including same-clock races.
                if(voice_valid && voice_group==i) begin
                    owned[i]<=0;
                    if(voice_on) begin enabled[i]<=0; offset[i]<=0; end
                end
            end
        end
    end
endmodule
