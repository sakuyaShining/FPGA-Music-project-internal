"""Wire sensor reports to the owned bridge, then the existing real engine."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parent
def once(s,a,b):
    assert s.count(a)==1,a[:90]
    return s.replace(a,b)
s=(R/'rtl/instrument_joint_probe.v').read_text(encoding='utf-8')
s=once(s,'module instrument_joint_probe(', 'module instrument_owned_probe(')
s=once(s,'    input wire calibrate,scan_bus_grant,sensor_report_ready,', '''    input wire calibrate,scan_bus_grant,
    output wire sensor_report_ready,
    input wire [181:0] left_note_map,
    input wire [3:0] left_velocity,
    output wire frame_error,link_error,sensor_error,watchdog_error,
    output wire [25:0] bound_contacts,blocked_contacts,''')
s=once(s,'    input wire finger_valid,', '    output wire finger_valid,')
s=once(s,'    input wire [1:0] finger_cmd,', '    output wire [1:0] finger_cmd,')
s=once(s,'    input wire [4:0] finger_id,finger_group,', '    output wire [4:0] finger_id,finger_group,')
s=once(s,'    input wire signed [11:0] finger_position,', '    output wire signed [11:0] finger_position,')
s=once(s,'rh_music_probe #(.LEGACY_PAD(0)) music(', '''left_music_probe music(
    .left_valid(sensor_report_valid),.left_ready(sensor_report_ready),.left_contact(sensor_contact),.left_invalid(sensor_invalid),.left_position(sensor_position),.left_sequence(sensor_sequence),.left_calibration(sensor_report_calibration),.left_note_map(left_note_map),.left_velocity(left_velocity),
    .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts),''')
(R/'rtl/instrument_owned_probe.v').write_text(s,encoding='utf-8')
for profile,top in [('owned_joint','instrument_owned_probe'),('bridge','left_contact_bridge')]:
    D=R/'synthesis'/profile;D.mkdir(parents=True,exist_ok=True)
    files=list((R/'rtl').glob('*.v'))
    if profile=='owned_joint':files+=[p for p in (R/'candidate').glob('*.v') if p.name!='compat_music_probe.v']+[p for p in (R/'engine').glob('*.v') if p.name!='pitch_mod.v']+[R/'optimization/pitch_mod.v']
    for p in files+list((R/'rtl').glob('*.vh'))+list((R/'engine').glob('*.hex')):shutil.copyfile(p,D/p.name)
    xml=['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>','<Project><Template>FPGA</Template><Version>5</Version>',
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>','<FileList>']
    xml+=['<File path="'+p.name+'" type="file.verilog" enable="1"/>' for p in files];xml+=['</FileList></Project>']
    (D/'probe.gprj').write_text('\n'.join(xml)+'\n',encoding='utf-8')
    (D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module '+top+'\nrun syn\nexit\n',encoding='utf-8')
    (D/'inputs.json').write_text(json.dumps({p.name:dict(source=p.relative_to(R).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files+list((R/'rtl').glob('*.vh'))+list((R/'engine').glob('*.hex'))},indent=2),encoding='utf-8')
print('Prepared sensor-to-owned-note joint and standalone bridge probes')
