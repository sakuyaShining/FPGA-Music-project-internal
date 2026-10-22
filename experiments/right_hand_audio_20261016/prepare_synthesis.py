"""Standalone controller and full music resource probes; no physical pinout."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
FADERS=ROOT.parent/'right_hand_faders_20261016'
VIS=ROOT.parent/'music_visualizer_20261015'
header=(ROOT/'rtl/rh_music_probe.v').read_text(encoding='utf-8').split('    rh_performance_control control(')[0]
header=header.replace('module rh_music_probe(','module rh_music_visualizer_probe(')
header=header.replace('    output wire signed [23:0] pcm','    output wire signed [23:0] pcm,\n    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,\n    output wire [31:0] rendered_frames,late_frames,analysis_gaps,spectrum_sequence')
ports='clk rst_n uart_rx_pin uart_tx_pin ev_valid ev_on ev_note ev_vel preset finger_valid finger_cmd finger_id finger_group finger_position pad touch_valid touch_ready touch_active touch_x touch_y touch_id radius slew_step part_to_control restore_valid voice_mask fader_y gains touch_done gain_done control_error led dac_din dac_ws dac_bck pa_en voice_valid voice_on voice_group voice_note pcm_valid pcm'.split()
wrapper=header+'rh_music_probe music('+','.join('.'+p+'('+p+')' for p in ports)+');\n'
wrapper+='''music_visualizer visualizer(.clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),.pcm(pcm[23:8]),
    .layer_mask(4'b0001),.base_note(7'd48),.note_valid(voice_valid),.note_on(voice_on),.note_id(voice_group),.note_number(voice_note),
    .pitch_valid(1'b0),.pitch_id(5'd0),.pitch_q8(16'sd0),.lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
    .rendered_frames(rendered_frames),.late_frames(late_frames),.analysis_gap_samples(analysis_gaps),.spectrum_sequence(spectrum_sequence));
endmodule
'''
(ROOT/'rh_music_visualizer_probe.v').write_text(wrapper,encoding='utf-8')
for profile,top in [('control','rh_performance_control'),('music','rh_music_probe'),('music_visualizer','rh_music_visualizer_probe')]:
 dst=ROOT/'synthesis'/profile;dst.mkdir(parents=True,exist_ok=True)
 files=list((ROOT/'rtl').glob('*.v'))+list((FADERS/'rtl').glob('*.v'))
 if profile!='control':files+=list((ROOT/'engine').glob('*.v'))
 if profile=='music_visualizer':files += list((VIS/'rtl').glob('*.v'))+[ROOT/'rh_music_visualizer_probe.v']
 for source in files:shutil.copyfile(source,dst/source.name)
 for source in [ROOT/'fader_gain_q8.hex']+list((ROOT/'engine').glob('*.hex')):
  shutil.copyfile(source,dst/source.name)
 if profile=='music_visualizer':
  for source in list((VIS/'rtl').glob('*.vh'))+list(VIS.glob('*1024.hex')):
   shutil.copyfile(source,dst/source.name)
 xml=['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>',
      '<Project><Template>FPGA</Template><Version>5</Version>',
      '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>','<FileList>']
 xml += ['<File path="'+p.name+'" type="file.verilog" enable="1"/>' for p in files]
 xml += ['</FileList></Project>']
 (dst/'probe.gprj').write_text('\n'.join(xml)+'\n',encoding='utf-8')
 (dst/'synth.tcl').write_text('open_project "'+(dst/'probe.gprj').as_posix()+'"\nset_option -top_module '+top+'\nrun syn\nexit\n',encoding='utf-8')
 print(dst)
