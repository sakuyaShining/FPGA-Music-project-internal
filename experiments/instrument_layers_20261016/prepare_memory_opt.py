from pathlib import Path
R=Path(__file__).resolve().parent;D=R/'reference';D.mkdir(exist_ok=True)
p=R/'rtl/layer_dispatch.v';s=p.read_text(encoding='utf-8')
if not (D/'layer_dispatch.v').exists():(D/'layer_dispatch.v').write_text(s,encoding='utf-8')
s=(D/'layer_dispatch.v').read_text(encoding='utf-8')
assert s.count('            for(i=0;i<32;i=i+1)group_token[i]<=0;')==1
s=s.replace('            for(i=0;i<32;i=i+1)group_token[i]<=0;', '            // group_valid guards synchronous token RAM; its payload has no reset.')
s=s.replace('wire bind_ok=group_valid[bind_group]&&group_token[bind_group]=={tokens[bind_id],bind_slot};', '''wire [4:0] lookup_group=(state==IDLE&&in_finger_valid&&in_finger_cmd==0)?groups0[in_finger_id]:
        ((state==BIND&&!bind_second&&count[bind_id]>1)?groups1[bind_id]:bind_group);
    reg [14:0] checked_token;
    always @(posedge clk)checked_token<=group_token[lookup_group];
    wire bind_ok=group_valid[bind_group]&&checked_token=={tokens[bind_id],bind_slot};''')
# The low 5 token bits are the row index, so storing them duplicates identity.
s=s.replace('reg [12:0] tokens[0:NF-1];','reg [7:0] generations[0:NF-1];')
s=s.replace('tokens[i]<=0;', 'generations[i]<=0;')
s=s.replace('tokens[bind_id]', '{generations[bind_id],bind_id}')
s=s.replace('tokens[parent_instance[4:0]]<=parent_instance;', 'generations[parent_instance[4:0]]<=parent_instance[12:5];')
s=s.replace('tokens[parent_instance[4:0]]==parent_instance', 'generations[parent_instance[4:0]]==parent_instance[12:5]')
p.write_text(s,encoding='utf-8')
print('Synchronous token lookup with prefetch, group_valid guard, compact generation rows')
