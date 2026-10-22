from pathlib import Path
import re
P=Path(__file__).resolve().parents[2];R=P/'experiments/resource_safety_20261016'
s=(P/'experiments/left_hand_events_20261016/tb_bridge.v').read_text(encoding='utf-8')
start=s.index('    left_contact_bridge #(');end=s.index('));',start)+3
inst=s[start:end].replace('left_contact_bridge #(','left_contact_bridge_reference #(').replace(' dut(',' ref_impl(')
widths={'frame_ready':1,'own_valid':1,'own_on':1,'own_note':7,'own_vel':4,'own_instance':13,'finger_valid':1,'finger_cmd':2,'finger_id':5,'finger_group':5,'finger_position':12,'frame_error':1,'link_error':1,'sensor_error':1,'watchdog_error':1,'bound_contacts':2,'blocked_contacts':2}
decl=''
for name,width in widths.items():
    decl+='    wire '+('['+str(width-1)+':0] ' if width>1 else '')+'ref_'+name+';\n'
    inst=re.sub(r'\.'+name+r'\([^)]*\)', '.'+name+'(ref_'+name+')',inst)
a='{'+','.join(widths)+'}';b='{'+','.join('ref_'+n for n in widths)+'}'
check='''    integer equality_clocks=0,qq;
    always @(posedge clk)begin
        #2;
        if(A!==B)$fatal(1,"bridge cycle mismatch at %0d",equality_clocks);
        for(qq=0;qq<2;qq=qq+1)
            if({dut.generation[qq],dut.sounding_note[qq],dut.last_position[qq],dut.bad_count[qq]}!=={ref_impl.generation[qq],ref_impl.sounding_note[qq],ref_impl.last_position[qq],ref_impl.bad_count[qq]})$fatal(1,"bridge row mismatch");
        equality_clocks=equality_clocks+1;
    end
'''.replace('A!==B',a+'!=='+b)
s=s[:end]+'\n'+decl+inst+'\n'+check+s[end:]
s=s.replace('PASS bridge frames=', 'PASS bridge_reference_equiv frames=')
(R/'tb_bridge_equiv.v').write_text(s,encoding='utf-8')
print('Prepared bridge functional suite plus per-clock and logical row equivalence')
