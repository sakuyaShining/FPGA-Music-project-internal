from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

from build import slacks


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
TOP = 'note_router_timing_probe'
MINIMAL = '''module note_router_timing_probe(
    input wire clk,load,shift,capture,
    input wire [3:0] data_in,
    output wire [3:0] data_out);
    reg [3:0] held=0,observed=0;
    assign data_out=observed;
    always @(posedge clk)begin
        if(load)held<=data_in;
        else if(shift)held<={held[2:0],held[3]};
        if(capture)observed<=held;
    end
endmodule
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_wrapper(original):
    changes = [
        ('    reg [235:0] staging=0,controls=0;',
         '    reg load_q=0,shift_q=0,capture_q=0;\n'
         '    reg [3:0] data_in_q=0;\n'
         '    always @(posedge clk)begin\n'
         '        load_q<=load;shift_q<=shift;capture_q<=capture;data_in_q<=data_in;\n'
         '    end\n'
         '    reg [235:0] staging=0,controls=0;'),
        ('if(shift)staging<={staging[231:0],data_in};', 'if(shift_q)staging<={staging[231:0],data_in_q};'),
        ('if(load)controls<=staging;', 'if(load_q)controls<=staging;'),
        ('if(capture)observation<=', 'if(capture_q)observation<='),
        ('else if(shift)observation<=', 'else if(shift_q)observation<='),
    ]
    for before, after in changes:
        if original.count(before) != 1:
            raise ValueError('Diagnostic wrapper anchor changed')
        original = original.replace(before, after)
    return original


def constraint_text(original, mode, input_ports='all'):
    if input_ports not in ('all', 'controls', 'data', 'load', 'shift', 'capture'):
        raise ValueError('Unknown diagnostic input selection')
    if mode in ('full', 'full-explicit'):
        if input_ports != 'all':
            raise ValueError('Full constraints must keep every original input')
        if mode == 'full-explicit':
            before = '[get_ports {load shift capture data_in[*]}]'
            if original.count(before) != 2:
                raise ValueError('Full input collection changed')
            return original.replace(before, '[get_ports {load shift capture data_in[0] data_in[1] data_in[2] data_in[3]}]')
        return original
    prefixes = {
        'clock': ('create_clock ',),
        'uncertainty': ('create_clock ', 'set_clock_uncertainty '),
        'io': ('create_clock ', 'set_input_delay ', 'set_output_delay '),
        'input': ('create_clock ', 'set_input_delay '),
        'input-max': ('create_clock ', 'set_input_delay '),
        'input-min': ('create_clock ', 'set_input_delay '),
        'output': ('create_clock ', 'set_output_delay '),
    }
    if mode not in prefixes:
        raise ValueError('Unknown diagnostic constraint mode')
    lines = original.splitlines(keepends=True)
    if any(line.strip() and not line.startswith(('create_clock ', 'set_clock_uncertainty ',
                                               'set_input_delay ', 'set_output_delay ')) for line in lines):
        raise ValueError('Unexpected constraint command; review before reducing')
    selected = [line for line in lines if line.startswith(prefixes[mode])]
    if mode in ('input-max', 'input-min'):
        excluded = ' -min ' if mode == 'input-max' else ' -max '
        selected = [line for line in selected if not (line.startswith('set_input_delay ') and excluded in line)]
    if input_ports != 'all':
        original_ports = '[get_ports {load shift capture data_in[*]}]'
        ports = {'controls': 'load shift capture', 'data': 'data_in[*]',
                 'load': 'load', 'shift': 'shift', 'capture': 'capture'}[input_ports]
        replaced = []
        for line in selected:
            if line.startswith('set_input_delay '):
                if line.count(original_ports) != 1:
                    raise ValueError('Input collection changed; review before selecting ports')
                line = line.replace(original_ports, '[get_ports {'+ports+'}]')
            replaced.append(line)
        selected = replaced
    return ''.join(selected)


def output_path(path):
    resolved = path.resolve()
    if resolved.exists() or resolved == PROJECT or PROJECT in resolved.parents:
        raise ValueError('Use a fresh diagnostic output outside repository')
    if os.name == 'nt' and resolved.drive.lower() == 'c:':
        raise ValueError('Diagnostic outputs must not use the space-constrained system drive')
    return resolved


def outcome(code, console, report_exists, image_exists, changed):
    if changed:
        return 'SOURCE_CHANGED_REJECTED'
    if code == 0 and not re.search(r'\bERROR\s*\(', console) and 'Bitstream generation completed' in console and report_exists and image_exists:
        return 'ROUTE_COMPLETED_DIAGNOSTIC_ONLY'
    return 'FAILED_OR_INCOMPLETE_DIAGNOSTIC'


def main():
    parser = argparse.ArgumentParser(description='Isolate router PnR crashes; never qualify or program a product')
    parser.add_argument('--logic', choices=('minimal', 'router', 'router-registered'), required=True)
    parser.add_argument('--constraints', choices=('full', 'full-explicit', 'clock', 'uncertainty', 'io', 'input', 'output', 'input-max', 'input-min'), required=True)
    parser.add_argument('--input-ports', choices=('all', 'controls', 'data', 'load', 'shift', 'capture'), default='all')
    parser.add_argument('--hold-correction', choices=('on', 'off'), default='on')
    parser.add_argument('--strategy', choices=('default', 'alternate'), default='default')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    executable = Path(os.environ.get('FPGA_GOWIN_GW_SH',
        'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'))
    if not executable.is_file():
        raise ValueError('Missing Gowin shell')
    originals = [Path(__file__).resolve(), ROOT/'build.py', ROOT/'rtl/note_event_router.v',
                 ROOT/'rtl/note_router_timing_probe.v', ROOT/'constraints/router_probe.cst',
                 ROOT/'constraints/router_probe.sdc']
    inputs = {path.relative_to(PROJECT).as_posix(): digest(path) for path in originals}
    tool = {path.name: digest(path) for path in (executable, executable.parent/'gowin.dll') if path.is_file()}
    original_sdc = (ROOT/'constraints/router_probe.sdc').read_text(encoding='utf-8')
    selected_sdc = constraint_text(original_sdc, arguments.constraints, arguments.input_ports)
    original_wrapper = (ROOT/'rtl/note_router_timing_probe.v').read_text(encoding='utf-8')
    wrapper = (MINIMAL if arguments.logic == 'minimal' else
               registered_wrapper(original_wrapper) if arguments.logic == 'router-registered' else original_wrapper).encode('utf-8')
    output.mkdir(parents=True)
    snapshot = output/'original-inputs'
    snapshot.mkdir()
    for original in originals:
        shutil.copyfile(original, snapshot/original.name)
    shutil.copyfile(ROOT/'rtl/note_event_router.v', output/'note_event_router.v')
    shutil.copyfile(ROOT/'constraints/router_probe.cst', output/'router_probe.cst')
    (output/'note_router_timing_probe.v').write_bytes(wrapper)
    (output/'router_probe.sdc').write_bytes(selected_sdc.encode('utf-8'))
    filenames = [('note_router_timing_probe.v', 'file.verilog'), ('router_probe.cst', 'file.cst'),
                 ('router_probe.sdc', 'file.sdc')]
    if arguments.logic != 'minimal':
        filenames.insert(0, ('note_event_router.v', 'file.verilog'))
    entries = ''.join('<File path="'+name+'" type="'+kind+'" enable="1"/>' for name, kind in filenames)
    project = output/'router.gprj'
    project.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
        '<Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">'
        'gw2ar18c-000</Device><FileList>'+entries+'</FileList></Project>', encoding='utf-8')
    script = output/'build.tcl'
    script.write_text('open_project "'+project.as_posix()+'"\nset_option -top_module '+TOP+
        '\nset_option -use_sspi_as_gpio 1\nset_option -correct_hold_violation '+
        ('1' if arguments.hold_correction == 'on' else '0')+'\n'+
        ('set_option -place_option 1\nset_option -route_option 1\n' if arguments.strategy == 'alternate' else '')+
        'run all\nexit\n', encoding='utf-8')
    exports = {path.name: digest(path) for path in output.iterdir() if path.is_file()}
    temporary = output/'temporary'
    temporary.mkdir()
    environment = dict(os.environ, TEMP=str(temporary), TMP=str(temporary))
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    started = time.monotonic()
    receipt = dict(schema=1, started_at=datetime.now(timezone.utc).isoformat(),
        logic=arguments.logic, constraints=arguments.constraints, input_ports=arguments.input_ports,
        hold_correction=arguments.hold_correction,
        strategy=arguments.strategy,
        inputs=inputs, exported_inputs=exports,
        tool=dict(path=str(executable), sha256=tool), command=[str(executable), str(script)],
        temporary_directory=str(temporary), system_free_before=shutil.disk_usage('C:/').free,
        scope='Diagnostic fixed-pin shell only; reduced constraints intentionally remove coverage',
        product_acceptance=False, full_product_pnr=False, full_product_sta=False,
        hardware_accessed=False, programming_allowed=False)
    (output/'started.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    termination = None
    with (output/'console.log').open('wb') as console:
        process = subprocess.Popen(receipt['command'], cwd=output, env=environment, stdout=console,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        receipt['pid'] = process.pid
        (output/'started.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        print('GOWIN PID '+str(process.pid), flush=True)
        try:
            code = process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            try:
                killed = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
                termination = dict(returncode=killed.returncode, text=killed.stdout.decode('utf-8', errors='replace'))
            except subprocess.TimeoutExpired:
                termination = dict(status='TASKKILL_TIMEOUT')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                termination['vendor_handle_unsignalled'] = True
            code = 124
    changed = [name for name, expected in inputs.items() if digest(PROJECT/name) != expected]
    changed_exports = [name for name, expected in exports.items() if digest(output/name) != expected]
    changed_tools = [name for name, expected in tool.items() if digest(executable.parent/name) != expected]
    console = (output/'console.log').read_text(encoding='utf-8', errors='replace')
    timing_file = output/'impl/pnr/router_tr_content.html'
    image_file = output/'impl/pnr/router.fs'
    status = outcome(code, console, timing_file.is_file(), image_file.is_file(), changed+changed_exports+changed_tools)
    reports = {path.relative_to(output).as_posix(): digest(path) for path in sorted((output/'impl').rglob('*'))
               if path.is_file() and path.suffix in ('.html', '.txt', '.fs', '.log', '.do', '.cfg')}
    receipt.update(finished_at=datetime.now(timezone.utc).isoformat(), returncode=code, status=status,
        termination=termination,
        elapsed_seconds=round(time.monotonic()-started, 2), source_changes=changed,
        export_changes=changed_exports, tool_changes=changed_tools,
        console_sha256=digest(output/'console.log'), reports=reports,
        slack_ns=slacks(timing_file.read_text(encoding='utf-8')) if timing_file.is_file() else None,
        system_free_after=shutil.disk_usage('C:/').free)
    (output/'results.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=status, returncode=code, slack_ns=receipt['slack_ns'], output=str(output))))
    return 0 if status == 'ROUTE_COMPLETED_DIAGNOSTIC_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
