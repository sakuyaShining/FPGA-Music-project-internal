from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import re
import shutil
import subprocess

from contact_rtl_reference import INPUTS, OUTPUTS
from diagnose_timing import ROOT, PROJECT, digest, output_path
from build import slacks


def wrapper():
    input_width = sum(width for name, width in INPUTS)
    output_width = sum(width for name, width in OUTPUTS)
    declarations = '\n'.join('wire '+('['+str(width-1)+':0] ' if width > 1 else '')+name+';' for name, width in INPUTS+OUTPUTS)
    return '''module note_contact_timing_probe(
input wire clk,load,shift,capture,
input wire [3:0] data_in,
output wire [3:0] data_out);
DECLARATIONS
reg [INPUT_WIDTH-1:0] staging=0,controls=0;
reg [OUTPUT_WIDTH-1:0] observation=0;
assign {INPUT_NAMES}=controls;
assign data_out=observation[3:0];
always @(posedge clk)begin
    if(shift)staging<=(staging<<4)|data_in;
    if(load)controls<=staging;
    if(capture)observation<={OUTPUT_NAMES};
    else if(shift)observation<=observation>>4;
end
note_contact_adapter dut(.clk(clk),PORTS);
endmodule
'''.replace('DECLARATIONS', declarations).replace('INPUT_WIDTH', str(input_width)).replace('OUTPUT_WIDTH', str(output_width)).replace('INPUT_NAMES', ','.join(name for name, width in INPUTS)).replace('OUTPUT_NAMES', ','.join(name for name, width in OUTPUTS)).replace('PORTS', ',\n'.join('.'+name+'('+name+')' for name, width in INPUTS+OUTPUTS))


def main():
    parser = argparse.ArgumentParser(description='Full-constraint standalone contact-transport diagnostic PnR/STA, NEVER a product image')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    executable = Path(os.environ.get('FPGA_GOWIN_GW_SH', 'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'))
    sources = [Path(__file__).resolve(), ROOT/'rtl/note_contact_adapter.v', ROOT/'contact_rtl_reference.py',
               ROOT/'constraints/router_probe.sdc', ROOT/'constraints/router_probe.cst', ROOT/'build.py', ROOT/'diagnose_timing.py']
    identities = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    output.mkdir(parents=True)
    snapshot = output/'original-inputs'
    snapshot.mkdir()
    for source in sources:
        shutil.copyfile(source, snapshot/source.name)
    shutil.copyfile(ROOT/'rtl/note_contact_adapter.v', output/'note_contact_adapter.v')
    for name in ('router_probe.sdc', 'router_probe.cst'):
        shutil.copyfile(ROOT/'constraints'/name, output/name)
    (output/'note_contact_timing_probe.v').write_bytes(wrapper().encode('utf-8'))
    project = output/'contact.gprj'
    files = ''.join('<File path="'+name+'" type="'+kind+'" enable="1"/>' for name, kind in (
        ('note_contact_adapter.v', 'file.verilog'), ('note_contact_timing_probe.v', 'file.verilog'),
        ('router_probe.sdc', 'file.sdc'), ('router_probe.cst', 'file.cst')))
    project.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+files+'</FileList></Project>', encoding='utf-8')
    script = output/'build.tcl'
    script.write_text('open_project "'+project.as_posix()+'"\nset_option -top_module note_contact_timing_probe\nset_option -use_sspi_as_gpio 1\nrun all\nexit\n', encoding='utf-8')
    launch = dict(started_at=datetime.now(timezone.utc).isoformat(), inputs=identities,
        tool=dict(path=str(executable), sha256=digest(executable)), wrapper_sha256=digest(output/'note_contact_timing_probe.v'),
        project_sha256=digest(project), script_sha256=digest(script), programming_allowed=False)
    with (output/'console.log').open('wb') as console:
        process = subprocess.Popen([str(executable), str(script)], cwd=output, stdout=console,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        launch['pid'] = process.pid
        (output/'launch.json').write_text(json.dumps(launch, indent=2)+'\n', encoding='utf-8')
        print('GOWIN PID '+str(process.pid), flush=True)
        try:
            code = process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.wait()
            code = 124
    console = (output/'console.log').read_text(encoding='utf-8', errors='replace')
    timing = output/'impl/pnr/contact_tr_content.html'
    slack = slacks(timing.read_text(encoding='utf-8')) if timing.is_file() else None
    changes = [name for name, sha in identities.items() if digest(PROJECT/name) != sha]
    passed = code == 0 and not changes and 'Bitstream generation completed' in console and not re.search(r'\bERROR\s*\(', console) and slack is not None and all(value is not None and value >= 0 for value in slack.values())
    reports = {path.relative_to(output).as_posix(): digest(path) for path in sorted((output/'impl').rglob('*')) if path.is_file() and path.suffix in ('.html', '.log', '.txt', '.fs')}
    result = dict(launch, returncode=code, completed_at=datetime.now(timezone.utc).isoformat(),
        source_changes=changes, console_sha256=digest(output/'console.log'), slack_ns=slack, reports=reports,
        status='PASS_CONTACT_UNIT_TIMING_ONLY' if passed else 'FAIL_OR_INCOMPLETE_TIMING',
        scope='Standalone contact transport in scan-register diagnostic shell; fixed diagnostic pins and27MHz envelope are NOT the physical PCB contract',
        full_product_pnr=False, full_product_sta=False, physical_source_integrated=False, product_acceptance=False)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], returncode=code, slack_ns=slack)))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
