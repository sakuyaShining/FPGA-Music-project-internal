"""Opt-in bounded serial instance lookup. Legacy allocation timing is retained."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parent;O=R/'optimization'
s=(R/'candidate/note_map_owned.v').read_text(encoding='utf-8')
def once(a,b):
    global s
    assert s.count(a)==1,a[:100]
    s=s.replace(a,b)
once('    reg owned_hold;', '''    reg [$clog2(NG)-1:0] owner_index;
    reg owned_hold;''')
once('''(OWNED_EVENTS ? (owned_hold ? (group_owned[n]&&group_instance[n]==instance_hold) :
                (!group_owned[n]&&gtab[n]==n_hold)) : (gtab[n]==n_hold))''', '''(OWNED_EVENTS ? (!owned_hold&&!group_owned[n]&&gtab[n]==n_hold) : (gtab[n]==n_hold))''')
once('    // round-robin 抢占指针', '''    wire owner_hit=OWNED_EVENTS&&owned_hold&&gact[owner_index]&&group_owned[owner_index]&&group_instance[owner_index]==instance_hold;
    wire allocation_commit=(st==ST_ALLOC)&&(!OWNED_EVENTS||!owned_hold||owner_hit||owner_index==NG-1);

    // round-robin 抢占指针''')
once('else if (st == ST_ALLOC && on_cur && !found_match && !found_free)', 'else if (allocation_commit && on_cur && !found_match && !found_free && !owner_hit)')
once('group_owned<=0;owned_hold<=0;instance_hold<=0;', 'group_owned<=0;owned_hold<=0;instance_hold<=0;owner_index<=0;')
once('                        n_hold <= ev_note;', '                        n_hold <= ev_note;\n                        owner_index<=0;')
old='''                    gsel_r  <= gsel;
                    match_r <= found_match;
                    free_r  <= !gact[gsel];   // FREE bits alone cannot distinguish MIDI127.
                    st      <= ST_GLIDE;'''
new='''                    if(OWNED_EVENTS&&owned_hold)begin
                        if(owner_hit)begin
                            gsel_r<=owner_index;match_r<=1;free_r<=0;st<=ST_GLIDE;
                        end else if(owner_index==NG-1)begin
                            gsel_r<=gsel;match_r<=0;free_r<=!gact[gsel];st<=ST_GLIDE;
                        end else owner_index<=owner_index+1'b1;
                    end else begin
                        gsel_r<=gsel;match_r<=found_match;free_r<=!gact[gsel];st<=ST_GLIDE;
                    end'''
once(old,new)
(O/'note_map_owned.v').write_text(s,encoding='utf-8')
ref=(R/'candidate/note_map_owned.v').read_text(encoding='utf-8').replace('module note_map_owned #(','module note_map_owned_parallel #(')
(O/'note_map_owned_parallel.v').write_text(ref,encoding='utf-8')
src=R/'synthesis/owned_joint';D=R/'synthesis/owned_serial';D.mkdir(parents=True,exist_ok=True)
for p in src.iterdir():
    if p.is_file() and p.suffix in ('.v','.vh','.hex','.gprj'):shutil.copyfile(p,D/p.name)
shutil.copyfile(O/'note_map_owned.v',D/'note_map_owned.v')
(D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module instrument_owned_probe\nrun syn\nexit\n',encoding='utf-8')
inputs=json.loads((src/'inputs.json').read_text(encoding='utf-8'))
inputs['note_map_owned.v']=dict(source='optimization/note_map_owned.v',sha256=hashlib.sha256((O/'note_map_owned.v').read_bytes()).hexdigest())
(D/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
(O/'owner-variant.json').write_text(json.dumps(dict(status='opt-in candidate',shared_comparator=True,maximum_added_owned_search_clocks=31,legacy_timing_unchanged=True,parallel_sha256=hashlib.sha256((R/'candidate/note_map_owned.v').read_bytes()).hexdigest(),serial_sha256=hashlib.sha256((O/'note_map_owned.v').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
print('Prepared serial instance lookup; parallel candidate preserved')
