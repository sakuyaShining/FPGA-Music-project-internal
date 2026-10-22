from pathlib import Path
P=Path(__file__).resolve().parents[2];R=P/'experiments/resource_safety_20261016'
s=(R/'rtl/left_contact_bridge.v').read_text(encoding='utf-8')
def once(a,b):
    global s
    assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
once('    reg [7:0] generation[0:NF-1];','    wire [7:0] generation[0:NF-1];')
once('    reg [6:0] sounding_note[0:NF-1];','    wire [6:0] sounding_note[0:NF-1];')
once('    reg [8:0] last_position[0:NF-1];','    wire [8:0] last_position[0:NF-1];')
once('    reg [BW-1:0] bad_count[0:NF-1];','    wire [BW-1:0] bad_count[0:NF-1];')
once('for(i=0;i<NF;i=i+1)begin generation[i]<=0;sounding_note[i]<=0;group[i]<=0;last_position[i]<=0;bad_count[i]<=0;end', 'for(i=0;i<NF;i=i+1)group[i]<=0;')
once("                        if(bad_count[index]<BAD_FRAMES)bad_count[index]<=bad_count[index]+1'b1;",'')
once('                    end else bad_count[index]<=0;','                    end')
once("                        generation[index]<=generation[index]+1'b1;",'')
once('own_note<=notes_q[index*7+:7];sounding_note[index]<=notes_q[index*7+:7];own_vel<=vel_q;', 'own_note<=notes_q[index*7+:7];own_vel<=vel_q;')
assert s.count('last_position[index]<=current_position;')==2
s=s.replace('last_position[index]<=current_position;','')
for field in ('generation','sounding_note','last_position','bad_count'):s=s.replace(field+'[index]',field+'_cur')
marker='    wire bad_expired='
assert s.count(marker)==1
pos=s.index(marker)
cache='''    // One synchronous row per strip, prefetched on IDLE/NEXT. Known bits
    // implement reset without clearing RAM. Same-address write forwarding is
    // required when SCAN immediately precedes MOVE (bad-frame update + move).
    localparam MW=24+BW;
    reg [MW-1:0] metadata[0:31];
    reg [NF-1:0] metadata_known;
    wire [4:0] metadata_addr=(state==IDLE)?5'd0:
        ((state==NEXT)?((index==NF-1)?5'd0:index+5'd1):index);
    reg [MW-1:0] metadata_read,forward_data;
    reg known_read,forward_read;
    reg metadata_we;
    reg [MW-1:0] metadata_write;
    wire [MW-1:0] metadata_cur=forward_read?forward_data:(known_read?metadata_read:{MW{1'b0}});
    wire [7:0] generation_cur=metadata_cur[MW-1 -:8];
    wire [6:0] sounding_note_cur=metadata_cur[BW+15 +:7];
    wire [8:0] last_position_cur=metadata_cur[BW +:9];
    wire [BW-1:0] bad_count_cur=metadata_cur[BW-1:0];
    always @(posedge clk)begin
        metadata_read<=metadata[metadata_addr];
        if(metadata_we)metadata[index]<=metadata_write;
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin metadata_known<=0;known_read<=0;forward_read<=0;forward_data<=0;end
        else begin
            known_read<=metadata_known[metadata_addr];
            forward_read<=metadata_we&&metadata_addr==index;
            if(metadata_we)begin metadata_known[index]<=1;forward_data<=metadata_write;end
        end
    end
    genvar mg;
    generate for(mg=0;mg<NF;mg=mg+1)begin: logical_rows
        // Logical views only. Runtime reads all use the single cached row.
        assign generation[mg]=metadata_known[mg]?metadata[mg][MW-1 -:8]:8'd0;
        assign sounding_note[mg]=metadata_known[mg]?metadata[mg][BW+15 +:7]:7'd0;
        assign last_position[mg]=metadata_known[mg]?metadata[mg][BW +:9]:9'd0;
        assign bad_count[mg]=metadata_known[mg]?metadata[mg][BW-1:0]:{BW{1'b0}};
    end endgenerate
'''
# Sounding note occupies bits BW+9 through BW+15 (generation above it).
cache=cache.replace('[BW+15 +:7]','[BW+9 +:7]')
s=s[:pos]+cache+s[pos:]
block='''    always @*begin
        metadata_we=rst_n&&((state==SCAN)||(state==BIND)||(state==MOVE));
        metadata_write=metadata_cur;
        if(state==SCAN)begin
            if(invalid_q[index])begin
                if(bad_count_cur<BAD_FRAMES)metadata_write[BW-1:0]=bad_count_cur+1'b1;
            end else metadata_write[BW-1:0]=0;
            if(!force_release&&!invalid_q[index]&&touch_q[index]&&!blocked[index]&&!seen[index])begin
                metadata_write[MW-1 -:8]=generation_cur+8'd1;
                metadata_write[BW+9 +:7]=notes_q[index*7+:7];
            end
        end else if(state==BIND||state==MOVE)metadata_write[BW +:9]=current_position;
    end
'''
once('    integer i;',block+'    integer i;')
(R/'selected/left_contact_bridge.v').write_text(s,encoding='utf-8')
(R/'reference/left_contact_bridge.v').write_text((R/'rtl/left_contact_bridge.v').read_text(encoding='utf-8').replace('module left_contact_bridge #(','module left_contact_bridge_reference #('),encoding='utf-8')
print('Prepared synchronous contact metadata with reset masking and forwarding')
