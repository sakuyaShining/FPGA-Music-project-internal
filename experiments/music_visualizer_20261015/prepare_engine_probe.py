"""Copy the hash-bound engine and add read-only monitor outputs in the COPY.

The original worktree is never edited. This is a resource/isolation probe, not
the final physical top; finger/PCM/module interfaces remain abstract ports.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent.parent/'notes/visualization-feasibility-20261015/probes/core_expression'
dst=ROOT/'engine_probe'
dst.mkdir(exist_ok=True)
files=[]
for p in list(BASE.glob('*.v'))+list(BASE.glob('*.hex')):
    shutil.copyfile(p,dst/p.name);files.append(p)
source=(BASE/'tdm_top.v').read_text(encoding='utf-8')
assert 'output wire [6:0] voice_note' in source
modified=source.replace('output wire [6:0] voice_note','output wire [6:0] voice_note,\n    output wire monitor_valid,\n    output wire signed [15:0] monitor_pcm')
modified=modified.replace('endmodule','assign monitor_valid=sample_en;\nassign monitor_pcm=audio[23:8];\nendmodule')
(dst/'tdm_top.v').write_text(modified,encoding='utf-8')
(dst/'tdm_top_reference.v').write_text(source.replace('module tdm_top #(','module tdm_top_reference #('),encoding='utf-8')
for p in list((ROOT/'rtl').glob('*.v'))+list((ROOT/'rtl').glob('*.vh'))+list(ROOT.glob('*1024.hex')):
    shutil.copyfile(p,dst/p.name)
wrapper=(BASE/'resource_core_probe.v').read_text(encoding='utf-8')
wrapper=wrapper.replace('module resource_core_probe(','module music_visualizer_engine_probe(')
wrapper=wrapper.replace('output wire [6:0] voice_note','output wire [6:0] voice_note,\n    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,\n    output wire update_done,\n    output wire [31:0] rendered_frames,late_frames,spectrum_sequence,analysis_gap_samples')
wrapper=wrapper.replace('    tdm_top #(','    wire monitor_valid;\n    wire signed [15:0] monitor_pcm;\n    tdm_top #(')
wrapper=wrapper.replace('.voice_note(voice_note)','.voice_note(voice_note),.monitor_valid(monitor_valid),.monitor_pcm(monitor_pcm)')
visual='''music_visualizer u_visualizer(.clk(clk),.rst_n(rst_n),.pcm_valid(monitor_valid),.pcm(monitor_pcm),
    .layer_mask(4'b0001),.base_note(7'd48),.note_valid(voice_valid),.note_on(voice_on),
    .note_id(voice_group),.note_number(voice_note),.pitch_valid(1'b0),.pitch_id(5'd0),.pitch_q8(16'sd0),
    .lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
    .update_done(update_done),.rendered_frames(rendered_frames),.late_frames(late_frames),
    .analysis_gap_samples(analysis_gap_samples),.spectrum_sequence(spectrum_sequence));
'''
wrapper=wrapper.replace('endmodule',visual+'endmodule')
(dst/'music_visualizer_engine_probe.v').write_text(wrapper,encoding='utf-8')
sources=[p.name for p in dst.glob('*.v') if p.name!='tdm_top_reference.v']
xml=['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>','<FileList>']
xml += [f'<File path="{name}" type="file.verilog" enable="1"/>' for name in sources]
xml += ['</FileList></Project>']
(dst/'probe.gprj').write_text('\n'.join(xml)+'\n')
(dst/'synth.tcl').write_text(f'open_project "{(dst/"probe.gprj").as_posix()}"\nset_option -top_module music_visualizer_engine_probe\nrun syn\nexit\n')
(dst/'copied-inputs.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
print(dst)
