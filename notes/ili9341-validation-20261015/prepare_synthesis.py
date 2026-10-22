"""Create standalone and core+driver synthesis probes, no board acceptance."""
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'visualization-feasibility-20261015/probes/core_expression'


def main():
    for profile in ('driver', 'core_driver'):
        dst = ROOT / 'synthesis' / profile
        dst.mkdir(parents=True, exist_ok=True)
        sources = []
        for source in (ROOT / 'rtl').glob('*.v'):
            shutil.copyfile(source, dst / source.name)
            sources.append(source.name)
        top = 'ili9341_window'
        if profile == 'core_driver':
            for source in BASE.glob('*.v'):
                shutil.copyfile(source, dst / source.name)
                sources.append(source.name)
            for source in BASE.glob('*.hex'):
                shutil.copyfile(source, dst / source.name)
            wrapper = (BASE / 'resource_core_probe.v').read_text(encoding='utf-8')
            ports = wrapper[wrapper.index('(')+1:wrapper.index(');')]
            ports += ''',
    input wire display_start, pixel_valid,
    input wire [8:0] x0,y0,x1,y1,
    input wire [15:0] pixel,
    output wire pixel_ready, display_busy, frame_done, window_error, init_done,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc
'''
            core = '''resource_core_probe u_core(
    .clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.led(led),
    .dac_din(dac_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(pa_en),.pad(pad),
    .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),
    .finger_group(finger_group),.finger_position(finger_position),
    .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note));
ili9341_window u_display(.clk(clk),.rst_n(rst_n),.lcd_reset_n(lcd_reset_n),
    .lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
    .init_done(init_done),.start(display_start),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
    .pixel_valid(pixel_valid),.pixel(pixel),.pixel_ready(pixel_ready),.busy(display_busy),
    .frame_done(frame_done),.window_error(window_error));
'''
            (dst / 'core_display_probe.v').write_text('module core_display_probe(' + ports + ');\n' + core + 'endmodule\n', encoding='utf-8')
            sources.append('core_display_probe.v')
            top = 'core_display_probe'
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE gowin-fpga-project>',
               '<Project><Template>FPGA</Template><Version>5</Version>',
               '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>', '<FileList>']
        xml += [f'<File path="{name}" type="file.verilog" enable="1"/>' for name in sources]
        xml += ['</FileList></Project>']
        (dst / 'probe.gprj').write_text('\n'.join(xml) + '\n', encoding='utf-8')
        (dst / 'synth.tcl').write_text(f'open_project "{(dst / "probe.gprj").as_posix()}"\nset_option -top_module {top}\nrun syn\nexit\n', encoding='utf-8')
    print(json.dumps({'prepared': ['driver', 'core_driver'], 'scope': 'synthesis only; no render analysis, FFT or physical pin assignment'}))


if __name__ == '__main__':
    main()
