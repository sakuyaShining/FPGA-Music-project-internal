from pathlib import Path
P=Path(__file__).resolve().parents[2];R=P/'experiments/resource_safety_20261016';D=R/'selected';D.mkdir(exist_ok=True)
s=(R/'engine/finger_pitch.v').read_text(encoding='utf-8')
def once(a,b):
    global s
    assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
once('    reg signed [11:0] anchor [0:NG-1];','''    localparam FA=1<<$clog2(NF);
    reg signed [11:0] contact_anchor [0:FA-1];''')
once('''    integer j;
    reg signed [11:0] moving_anchor;
    always @* begin
        moving_anchor=position;
        for(j=0;j<NG;j=j+1)
            if(owned[j] && owner[j]==finger) moving_anchor=anchor[j];
    end''','''    wire [NG-1:0] mine;
    generate for(g=0;g<NG;g=g+1) begin: finger_matches
        assign mine[g]=owned[g]&&owner[g]==finger;
    end endgenerate
    // All groups of one owned contact have the same anchor (bind invariant).
    // Release tails retain per-group offsets; only anchors are shared.
    wire signed [11:0] moving_anchor=(|mine)?contact_anchor[finger]:position;''')
once('owner[i]<=0; anchor[i]<=0; offset[i]<=0;','owner[i]<=0; offset[i]<=0;')
once('''        end else begin
            for(i=0;i<NG;i=i+1) begin''','''            for(i=0;i<FA;i=i+1)contact_anchor[i]<=0;
        end else begin
            if(cmd_valid&&cmd==0&&group<NG&&voice_active[group])
                contact_anchor[finger]<=(!MULTI_BIND||!(|mine))?position:moving_anchor;
            for(i=0;i<NG;i=i+1) begin''')
once('owner[i]<=finger; anchor[i]<=MULTI_BIND ? moving_anchor : position;', 'owner[i]<=finger;')
(D/'finger_pitch.v').write_text(s,encoding='utf-8')
s=(R/'optimization/note_map_owned.v').read_text(encoding='utf-8')
once('    wire owner_hit=OWNED_EVENTS&&owned_hold&&gact[owner_index]&&group_owned[owner_index]&&group_instance[owner_index]==instance_hold;', '''    // Prefetch entry zero on admission; each failed comparison prefetches
    // the next row. No extra allocation cycles or event timing changes.
    wire [$clog2(NG):0] instance_next={1'b0,owner_index}+1'b1;
    wire [$clog2(NG)-1:0] instance_read_addr=(st==ST_IDLE)?{$clog2(NG){1'b0}}:
        ((st==ST_ALLOC)?instance_next[$clog2(NG)-1:0]:owner_index);
    reg [OWNER_W-1:0] scanned_instance;
    always @(posedge clk)scanned_instance<=group_instance[instance_read_addr];
    wire owner_hit=OWNED_EVENTS&&owned_hold&&gact[owner_index]&&group_owned[owner_index]&&scanned_instance==instance_hold;''')
once('                group_instance[reset_group]<=0;', '                // Payload identity is masked by reset gact/group_owned.')
(D/'note_map_owned.v').write_text(s,encoding='utf-8')
(R/'reference').mkdir(exist_ok=True)
(R/'reference/finger_pitch.v').write_text((R/'engine/finger_pitch.v').read_text(encoding='utf-8').replace('module finger_pitch #(','module finger_pitch_reference #('),encoding='utf-8')
(R/'reference/note_map_owned.v').write_text((R/'optimization/note_map_owned.v').read_text(encoding='utf-8').replace('module note_map_owned #(','module note_map_reference #('),encoding='utf-8')
print('Prepared same-cycle anchor sharing and synchronous instance prefetch')
