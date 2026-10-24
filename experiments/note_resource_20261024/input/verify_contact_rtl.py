from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import json
import os
import shutil
import subprocess

from contact_rtl_reference import INPUTS, OUTPUTS, generate, unpack
from diagnose_timing import ROOT, PROJECT, digest, output_path


FAULTS = {
    'legacy-token': ('{SOURCE[0],{(31-SERIAL_W){1\'b0}},next_serial}',
                     "{19'd0,on_generation,on_contact}", 2, {'event_token', 'query_token'}),
    'held-retrigger': ('!held[on_contact]', '(!held[on_contact]||groups[on_contact]==0)', 1, {'on_ready'}),
    'first-layer-only': ('assign expression_groups=surviving_groups;',
                         'assign expression_groups=surviving_groups&-surviving_groups;', 1, {'expression_groups'}),
    'cancel-race': ('allocation_valid&&!cancelled&&!cancel_now',
                    'allocation_valid&&!cancelled', 1, {'response_ready'}),
    'old-tail-new-on': ('!(on_valid&&on_ready&&row==on_contact)&&', '', 2, {'query_groups'}),
}


def mutate(text, fault):
    if fault == 'candidate':
        return text
    before, after, count, fields = FAULTS[fault]
    if text.count(before) != count:
        raise ValueError('Contact RTL mutation anchor changed: '+fault)
    return text.replace(before, after)


def bench(source, serial_bits, cycles):
    inputs_width = sum(width for name, width in INPUTS)
    outputs_width = sum(width for name, width in OUTPUTS)
    declarations = '\n'.join('wire '+('['+str(width-1)+':0] ' if width > 1 else '')+name+';' for name, width in INPUTS+OUTPUTS)
    return '''module tb_contact;
reg clk=0;
always #5 clk=~clk;
DECLARATIONS
reg [INPUT_WIDTH-1:0] stimulus[0:CYCLES-1];
reg [INPUT_WIDTH-1:0] controls=0;
assign {INPUT_NAMES}=controls;
wire [OUTPUT_WIDTH-1:0] observation={OUTPUT_NAMES};
note_contact_adapter #(.SOURCE(SOURCE_VALUE),.SERIAL_W(SERIAL_BITS),.INITIAL_SERIAL(INITIAL_VALUE)) dut(
.clk(clk),PORTS);
integer cycle,trace;
initial begin
    $readmemh("inputs.hex",stimulus);
    trace=$fopen("trace.hex","w");
    for(cycle=0;cycle<CYCLES;cycle=cycle+1)begin
        @(negedge clk);controls=stimulus[cycle];
        #1;$fdisplay(trace,"%h",observation);
        @(posedge clk);#1;
    end
    $fclose(trace);$display("PASS contact cycles=%0d",CYCLES);$finish;
end
endmodule
'''.replace('DECLARATIONS', declarations).replace('INPUT_WIDTH', str(inputs_width)).replace('OUTPUT_WIDTH', str(outputs_width)).replace('CYCLES', str(cycles)).replace('INPUT_NAMES', ','.join(name for name, width in INPUTS)).replace('OUTPUT_NAMES', ','.join(name for name, width in OUTPUTS)).replace('SOURCE_VALUE', str(source)).replace('SERIAL_BITS', str(serial_bits)).replace('INITIAL_VALUE', str((1 << serial_bits)-3)).replace('PORTS', ',\n'.join('.'+name+'('+name+')' for name, width in INPUTS+OUTPUTS))


def compare(path, expected, fields=None):
    if not path.is_file():
        return dict(field='missing-trace')
    lines = path.read_text(encoding='utf-8').splitlines()
    if len(lines) != len(expected):
        return dict(field='trace-length', expected=len(expected), actual=len(lines))
    for cycle, (text, wanted) in enumerate(zip(lines, expected)):
        try:
            actual = int(text, 16)
        except ValueError:
            return dict(cycle=cycle, field='unknown-state', actual=text)
        if actual != wanted:
            observed, target = unpack(OUTPUTS, actual), unpack(OUTPUTS, wanted)
            differences = [name for name, width in OUTPUTS if observed[name] != target[name] and (fields is None or name in fields)]
            if differences:
                field = differences[0]
                return dict(cycle=cycle, field=field, expected=target[field], actual=observed[field])
    return None


def run(command, directory, name):
    try:
        process = subprocess.run(command, cwd=directory, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=90, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        raw, code = process.stdout, process.returncode
    except subprocess.TimeoutExpired as error:
        raw, code = (error.stdout or b'')+b'\nTIMEOUT\n', 124
    path = directory/name
    path.write_bytes(raw)
    return dict(command=command, returncode=code, log_sha256=digest(path)), raw.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description='Contact lifecycle RTL transport against the committed transaction oracle; not physical integration')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    sources = [Path(__file__).resolve(), ROOT/'contact_contract.py', ROOT/'contact_rtl_reference.py',
               ROOT/'rtl/note_contact_adapter.v', ROOT/'CONTACT-ADAPTER-CONTRACT.md']
    identities = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    output.mkdir(parents=True)
    snapshots = output/'original-inputs'
    snapshots.mkdir()
    for path in sources:
        shutil.copyfile(path, snapshots/path.name)
    reports = []
    cases = [('candidate', 0, 31), ('candidate', 1, 31), ('candidate', 0, 3)]
    if arguments.fault_checks:
        cases += [(fault, 0, 31) for fault in FAULTS]
    for fault, source, serial_bits in cases:
        directory = output/(fault+'-s'+str(source)+'-w'+str(serial_bits))
        directory.mkdir()
        vectors, expected, coverage = generate(source, serial_bits)
        (directory/'inputs.hex').write_text(''.join(format(value, 'x')+'\n' for value in vectors), encoding='utf-8')
        (directory/'expected.hex').write_text(''.join(format(value, 'x')+'\n' for value in expected), encoding='utf-8')
        rtl = directory/'note_contact_adapter.v'
        rtl.write_bytes(mutate((ROOT/'rtl/note_contact_adapter.v').read_text(encoding='utf-8'), fault).encode('utf-8'))
        testbench = directory/'tb_contact.v'
        testbench.write_bytes(bench(source, serial_bits, len(vectors)).encode('utf-8'))
        binary = directory/'contact.vvp'
        compilation, text = run([str(compiler), '-g2012', '-s', 'tb_contact', '-o', str(binary), str(rtl), str(testbench)], directory, 'compile.log')
        report = dict(case=fault, source=source, serial_bits=serial_bits, coverage=coverage,
            compilation=compilation, passed=False, rtl_sha256=digest(rtl), bench_sha256=digest(testbench),
            inputs_sha256=digest(directory/'inputs.hex'), expected_sha256=digest(directory/'expected.hex'))
        if compilation['returncode'] == 0:
            simulation, text = run([str(simulator), str(binary)], directory, 'run.log')
            difference = compare(directory/'trace.hex', expected)
            designated = compare(directory/'trace.hex', expected, FAULTS[fault][3]) if fault in FAULTS else None
            valid = simulation['returncode'] == 0 and 'PASS contact cycles='+str(len(vectors)) in text
            report.update(simulation=simulation, first_difference=difference, designated_difference=designated,
                passed=valid and (difference is None if fault == 'candidate' else designated is not None and designated['field'] in FAULTS[fault][3]))
            trace = directory/'trace.hex'
            if trace.is_file():
                report['trace_sha256'] = digest(trace)
                (directory/'trace.hex.gz').write_bytes(gzip.compress(trace.read_bytes(), mtime=0))
        reports.append(report)
        print(directory.name+': '+('PASS' if report['passed'] else 'FAIL'), flush=True)
    changes = [name for name, sha in identities.items() if digest(PROJECT/name) != sha]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=identities,
        source_changes=changes, tools={str(path): digest(path) for path in (compiler, simulator)}, reports=reports,
        status='PASS' if all(report['passed'] for report in reports) and not changes else 'FAIL',
        scope='Contact command transport RTL and transaction oracle with stub allocation replies; not actual scanner/score/renderer integration',
        product_acceptance=False, physical_source_integrated=False, full_product_pnr=False, full_product_sta=False)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
