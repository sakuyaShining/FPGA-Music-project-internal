"""Derive integration candidates from protected upstream copies, reproducibly."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent;P=R.parents[1]
old=P/'experiments/right_hand_audio_20261016'
def once(s,a,b):
    assert s.count(a)==1,a[:80]
    return s.replace(a,b)
s=(old/'engine/tdm_top_rh.v').read_text(encoding='utf-8')
s=once(s,'    parameter integer RIGHT_TIMBRE = 0','    parameter integer RIGHT_TIMBRE = 0,\n    parameter integer LEGACY_PAD = 1')
start=s.index('    pad_scan #(.NCH(16)) u_pad (');end=s.index('\n    );',start)+len('\n    );')
replacement='''    generate if(LEGACY_PAD)begin: legacy_input
'''+s[start:end]+'''
    end else begin: external_input
        assign pad=16'bz;
        assign pad_state_raw=16'd0;
        assign pd_ev_note=7'd0;
        assign pd_ev_on=1'b0;
        assign pd_ev_valid=1'b0;
        assign pad_raw_sel=12'd0;
        assign pad_base_sel=12'd0;
    end endgenerate'''
s=s[:start]+replacement+s[end:]
(R/'engine/tdm_top_rh.v').write_text(s,encoding='utf-8')
s=(old/'rtl/rh_music_probe.v').read_text(encoding='utf-8')
s=once(s,'module rh_music_probe(','module rh_music_probe #(parameter integer LEGACY_PAD=1)(')
s=once(s,'.RIGHT_TIMBRE(1)', '.RIGHT_TIMBRE(1),.LEGACY_PAD(LEGACY_PAD)')
(R/'rtl/rh_music_probe.v').write_text(s,encoding='utf-8')
s=(old/'rh_music_visualizer_probe.v').read_text(encoding='utf-8')
s=once(s,'module rh_music_visualizer_probe(', 'module instrument_joint_probe(')
s=once(s,'    input wire clk,rst_n,uart_rx_pin,','''    input wire [5:0] sense_n,
    input wire calibrate,scan_bus_grant,sensor_report_ready,
    input wire [13:0] threshold_on,threshold_off,
    output wire scan_bus_request,scan_bus_sck,scan_bus_mosi,scan_latch,
    output wire sensor_report_valid,sensor_report_calibration,sensor_protocol_error,sensor_grant_error,
    output wire [25:0] sensor_contact,sensor_invalid,
    output wire [233:0] sensor_position,
    output wire [31:0] sensor_sequence,
    input wire clk,rst_n,uart_rx_pin,''')
s=once(s,'rh_music_probe music(', 'rh_music_probe #(.LEGACY_PAD(0)) music(')
s=once(s,'endmodule','''instrument_sensor_probe sensor(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.sense_n(sense_n),
    .bus_request(scan_bus_request),.bus_grant(scan_bus_grant),.bus_sck(scan_bus_sck),.bus_mosi(scan_bus_mosi),.scan_latch(scan_latch),
    .threshold_on(threshold_on),.threshold_off(threshold_off),.report_valid(sensor_report_valid),.report_ready(sensor_report_ready),
    .contact(sensor_contact),.invalid(sensor_invalid),.position(sensor_position),.report_sequence(sensor_sequence),.report_calibration(sensor_report_calibration),.protocol_error(sensor_protocol_error),.grant_error(sensor_grant_error));
endmodule''')
(R/'rtl/instrument_joint_probe.v').write_text(s,encoding='utf-8')
for profile,top in [('sensor','instrument_sensor_probe'),('joint','instrument_joint_probe')]:
    dst=R/'synthesis'/profile;dst.mkdir(parents=True,exist_ok=True)
    files=list((R/'rtl').glob('*.v'))+(list((R/'engine').glob('*.v')) if profile=='joint' else [])
    for f in files+list((R/'rtl').glob('*.vh'))+list((R/'engine').glob('*.hex')):shutil.copyfile(f,dst/f.name)
    xml=['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>','<Project><Template>FPGA</Template><Version>5</Version>',
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>','<FileList>']
    xml+=['<File path="'+f.name+'" type="file.verilog" enable="1"/>' for f in files]
    xml+=['</FileList></Project>']
    (dst/'probe.gprj').write_text('\n'.join(xml)+'\n',encoding='utf-8')
    (dst/'synth.tcl').write_text('open_project "'+(dst/'probe.gprj').as_posix()+'"\nset_option -top_module '+top+'\nrun syn\nexit\n',encoding='utf-8')
    (dst/'inputs.json').write_text(json.dumps({f.name:hashlib.sha256((dst/f.name).read_bytes()).hexdigest() for f in files+list((R/'rtl').glob('*.vh'))+list((R/'engine').glob('*.hex'))},indent=2),encoding='utf-8')
print('Prepared optional legacy input and sensor/joint synthesis profiles')
