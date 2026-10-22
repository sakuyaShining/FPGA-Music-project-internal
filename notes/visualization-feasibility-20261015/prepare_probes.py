"""Prepare isolated synthesis probes; do not modify or flash the source project.

The core probe exposes finger commands as top-level inputs so synthesis cannot
remove the expression logic. It is not a board pin assignment or a product build.
"""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
PROJECT = SOURCE / 'src/gowin/tdm_synth/tdm_live_test.gprj'

WRAPPER = '''module resource_core_probe(
    input wire clk, rst_n, uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din, dac_ws, dac_bck, pa_en,
    inout wire [15:0] pad,
    input wire finger_valid,
    input wire [1:0] finger_cmd,
    input wire [4:0] finger_id, finger_group,
    input wire signed [11:0] finger_position,
    output wire voice_valid, voice_on,
    output wire [4:0] voice_group,
    output wire [6:0] voice_note
);
    tdm_top #(.BOARD_DIAG(0), .FINGER_EXPR(1), .LIVE_MONITOR(0), .UART_BAUD(460800)) u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(1'b0), .ev_on(1'b0), .ev_note(7'd0), .ev_vel(4'd0),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin), .led(led),
        .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en), .pad(pad),
        .finger_valid(finger_valid), .finger_cmd(finger_cmd),
        .finger_id(finger_id), .finger_group(finger_group), .finger_position(finger_position),
        .voice_valid(voice_valid), .voice_on(voice_on), .voice_group(voice_group), .voice_note(voice_note)
    );
endmodule
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = []
    for item in ET.parse(PROJECT).getroot().find('FileList'):
        if item.attrib['type'] == 'file.verilog':
            files.append((PROJECT.parent / item.attrib['path']).resolve())
    files += list(PROJECT.parent.glob('*.hex'))
    source_hashes = {str(p.relative_to(SOURCE)).replace('\\', '/'): sha(p) for p in files}
    for profile in ('live_reference', 'core_expression'):
        dst = ROOT / 'probes' / profile
        dst.mkdir(parents=True, exist_ok=True)
        for src in files:
            shutil.copyfile(src, dst / src.name)
        top = 'tdm_live_test'
        if profile == 'core_expression':
            (dst / 'resource_core_probe.v').write_text(WRAPPER, encoding='utf-8')
            top = 'resource_core_probe'
        vnames = [p.name for p in files if p.suffix == '.v']
        if profile == 'core_expression':
            vnames.append('resource_core_probe.v')
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE gowin-fpga-project>',
               '<Project><Template>FPGA</Template><Version>5</Version>',
               '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>', '<FileList>']
        xml += [f'<File path="{name}" type="file.verilog" enable="1"/>' for name in vnames]
        xml += ['</FileList></Project>']
        (dst / 'probe.gprj').write_text('\n'.join(xml) + '\n', encoding='utf-8')
        tcl = [f'open_project "{(dst / "probe.gprj").as_posix()}"',
               f'set_option -top_module {top}', 'run syn', 'exit']
        (dst / 'synth.tcl').write_text('\n'.join(tcl) + '\n', encoding='utf-8')
    manifest = {'source_root': str(SOURCE), 'source_commit': 'a7427ed',
                'delivery_commit': '683db48', 'source_files': source_hashes,
                'probe_kind': 'synthesis only, no pin constraints, no product or board acceptance',
                'live_reference': 'original tdm_live_test wrapper and original module parameters',
                'core_expression': 'FINGER_EXPR1 BOARD_DIAG0 LIVE_MONITOR0; external finger inputs preserved',
                'removed_paths_in_core': 'board diagnosis and PC live monitor; comparison candidate only, not approved removal'}
    (ROOT / 'source-inputs.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'profiles': 2, 'copied_inputs_per_profile': len(files), 'root': str(ROOT)}))


if __name__ == '__main__':
    main()
