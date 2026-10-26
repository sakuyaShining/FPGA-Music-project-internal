from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import shutil

from frame_transport import ports, wrapper
from diagnose_timing import ROOT, PROJECT, digest, output_path
from verify_contact_rtl import run


FAULTS = {
    'mutable-position': ('current_position=position_q[index*9+:9]', 'current_position=position[index*9+:9]', 'ON'),
    'held-retrigger': ('else if(!seen[index])begin', 'else if(!seen[index]||query_groups==0)begin', 'HELD_RETRIGGER'),
    'ignore-sequence': ('sequence_known&&frame_sequence!=last_sequence+1\'b1', "1'b0", 'BOUNDARY'),
    'drop-watchdog': ('stale_pending<=1;watchdog_error<=1;', 'watchdog_error<=1;', 'BOUNDARY'),
    'ignore-pending-link': ('||link_pending', '', 'LINK'),
}


def mutate(text, fault):
    if fault == 'candidate':
        return text
    before, after, channel = FAULTS[fault]
    if text.count(before) != 1:
        raise ValueError('Frame mutation anchor changed: '+fault)
    return text.replace(before, after)


class FrameOracle:
    def __init__(self, nf):
        self.nf = nf
        self.seen = set()
        self.blocked = set()
        self.bad = [0]*nf
        self.generation = [0]*nf
        self.rows = {}
        self.serial = 0
        self.sequence = None
        self.channels = dict(ON=[], OFF=[], MOVE=[], EVENT=[], CANCEL=[], LINK=[], BOUNDARY=[], FLAGS=[])
        self.flags = 0

    def frame(self, sequence, touch, invalid, positions, velocity, glide, layers, calibration=0, force=False):
        if self.sequence is not None and sequence != (self.sequence+1) & 0xffffffff and not force:
            self.flags |= 1
            force = True
        if not force:
            self.sequence = sequence
        else:
            self.blocked |= self.seen
            touch, invalid = 0, 0
            self.sequence = sequence
        for contact in range(self.nf):
            expired = bool(invalid >> contact & 1 and self.bad[contact] >= 2)
            self.bad[contact] = min(3, self.bad[contact]+1) if invalid >> contact & 1 else 0
            if expired:
                self.flags |= 4
                self.blocked.add(contact)
            if force or calibration or expired or not (invalid >> contact & 1 or touch >> contact & 1):
                if (force or calibration or expired) and contact in self.seen:
                    self.blocked.add(contact)
                elif not (invalid >> contact & 1 or touch >> contact & 1):
                    self.blocked.discard(contact)
                row = self.rows.get(contact)
                if contact in self.seen and row and row['held']:
                    self.channels['OFF'].append([row['token']])
                    self.channels['EVENT'].append([0, row['token'], row['note'], 0, 0, 0])
                    row['held'] = False
                self.seen.discard(contact)
            elif invalid >> contact & 1 or contact in self.blocked:
                continue
            elif contact not in self.seen:
                self.seen.add(contact)
                if not layers:
                    self.flags |= 16
                    continue
                self.generation[contact] = (self.generation[contact]+1) % 256
                token = self.serial
                self.serial += 1
                note = 60+contact
                base = contact if layers == 1 else contact*4
                groups = sum(1 << ((base+layer) % 32) for layer in range(4) if layers >> layer & 1)
                self.rows[contact] = dict(token=token, note=note, held=True, groups=groups,
                    layers=layers, position=positions[contact])
                self.channels['ON'].append([contact, self.generation[contact], note, velocity, glide & 262143, layers, positions[contact]])
                self.channels['EVENT'].append([1, token, note, velocity, glide & 262143, layers])
            else:
                row = self.rows.get(contact)
                if row and row['held'] and row['groups'] and positions[contact] != row['position']:
                    self.channels['MOVE'].append([row['token'], row['groups'], row['layers'], positions[contact]])
                    row['position'] = positions[contact]
        self.channels['BOUNDARY'].append([sequence, sum(1 << contact for contact in self.seen), sum(1 << contact for contact in self.blocked)])


def fixture(nf):
    oracle = FrameOracle(nf)
    commands = []
    sequence = 0
    layers = 15 if nf == 4 else 1
    positions = [100+index for index in range(nf)]
    def frame(mask=0, invalid=0, calibration=0, gap=1, selected=None):
        nonlocal sequence
        sequence = (sequence+gap) & 0xffffffff
        chosen = layers if selected is None else selected
        packed = sum(position << (9*index) for index, position in enumerate(positions))
        commands.append([0, sequence, mask, invalid, calibration, packed, 213, 255133, chosen])
        oracle.frame(sequence, mask, invalid, positions, 213, -7011, chosen, calibration)
    frame()
    frame((1 << nf)-1)
    positions[0] += 21
    frame((1 << nf)-1)
    token = oracle.rows[0]['token']
    commands.append([1, token, 0, 0, 0, 0, 0, 0, 0])
    oracle.rows[0].update(groups=0, layers=0)
    positions[0] += 30
    frame((1 << nf)-1)
    frame()
    frame(1)
    frame(1, invalid=1)
    frame(1, invalid=1)
    frame(1, invalid=1)
    frame(1)
    frame()
    frame(1)
    frame(1, calibration=1)
    frame(1)
    frame()
    frame(1)
    frame(1, gap=2)
    frame(1)
    frame()
    frame(1)
    commands.append([2, 0, 0, 0, 0, 0, 0, 0, 0])
    oracle.flags |= 8
    oracle.frame(sequence, 0, 0, positions, 213, -7011, layers, force=True)
    frame(1)
    frame()
    frame(1, selected=0)
    frame(1)
    frame()
    commands.append([3, 0, 0, 0, 0, 0, 0, 0, 0])
    frame(1)
    pending_token = oracle.rows[0]['token']
    frame()
    assert oracle.channels['EVENT'].pop()[0:2] == [0, pending_token]
    oracle.channels['CANCEL'].append([pending_token])
    oracle.rows[0].update(groups=0, layers=0)
    oracle.flags |= 2
    oracle.channels['LINK'].append([1])
    commands.append([4, 0, 0, 0, 0, 0, 0, 0, 0])
    commands.append([3, 0, 0, 0, 0, 0, 0, 0, 0])
    frame(3)
    frame()
    oracle.flags |= 2
    oracle.channels['LINK'].append([1])
    commands.append([4, 0, 0, 0, 0, 0, 0, 0, 0])
    for repeat in range(260 if nf == 4 else 2):
        frame(1)
        frame()
    sequence = (1 << 32)-3
    frame()
    frame(1)
    frame(1)
    frame()
    oracle.channels['FLAGS'] = [[oracle.flags]]
    return commands, oracle.channels


def bench(nf, stalled=False):
    inputs, outputs = ports(nf)
    declarations = ['reg clk=0;always #5 clk=~clk;']
    for name, width in inputs:
        declarations.append('reg '+('['+str(width-1)+':0] ' if width > 1 else '')+name+'=0;')
    for name, width in outputs:
        declarations.append('wire '+('['+str(width-1)+':0] ' if width > 1 else '')+name+';')
    connections = ','.join('.'+name+'('+name+')' for name, width in inputs+outputs)
    return r'''module tb_frames;
DECLARATIONS
note_frame_transport #(.NF(NF_VALUE),.BAD_FRAMES(3),.FRAME_TIMEOUT(2000),.LINK_TIMEOUT(300)) dut(.clk(clk),CONNECTIONS);
integer trace,script,status,kind,seq,mask,bad,cal,vel,delta,selected,timeout,countdown=0,delay_mode=DELAY_VALUE;
reg [NF_VALUE*9-1:0] positions;
reg pending=0,latched_on,cancel_seen=0;
reg [31:0] latched_token;
reg [6:0] latched_note;
reg [3:0] latched_layers;
integer layer,base,index;
integer stall_cycle=0;
always @(negedge clk)if(rst_n&&STALLED_VALUE)begin
    stall_cycle=stall_cycle+1;event_ready=stall_cycle%5!=0;reply_ready=stall_cycle%11>=4;
end
always @(posedge clk)if(rst_n)begin
    if(dut.on_valid&&dut.query_held)$fatal(1,"HELD_RETRIGGER");
    if(anchor_valid)begin
        $fdisplay(trace,"ON %0d %0d %0d %0d %0d %0d %0d",anchor_contact,dut.on_generation,dut.on_note,dut.on_velocity,dut.on_glide,dut.on_layers,anchor_position);
    end
    if(dut.release_valid&&dut.release_ready)$fdisplay(trace,"OFF %0d",dut.release_token);
    if(expression_valid)$fdisplay(trace,"MOVE %0d %0d %0d %0d",expression_token,expression_groups,expression_layers,expression_position);
    if(event_valid&&event_ready)begin
        $fdisplay(trace,"EVENT %0d %0d %0d %0d %0d %0d",event_on,event_token,event_note,event_velocity,event_glide,event_layers);
        pending<=1;countdown<=delay_mode;latched_on<=event_on;latched_token<=event_token;latched_note<=event_note;latched_layers<=event_layers;
        cancel_seen<=cancel_valid&&cancel_token==event_token;
    end
    if(pending&&cancel_valid&&cancel_token==latched_token)begin
        if(!cancel_seen)$fdisplay(trace,"CANCEL %0d",cancel_token);
        cancel_seen<=1;
        if(response_valid&&response_code==0)begin response_code<=6;response_groups<=0;response_layers<=0;response_map<=0;end
    end
    if(pending&&countdown>0)countdown<=countdown-1;
    if(response_valid&&response_ready)begin response_valid<=0;pending<=0;end
    if(pending&&countdown==1)begin
        response_valid<=1;response_token<=latched_token;
        response_code<=latched_on?((cancel_seen||(cancel_valid&&cancel_token==latched_token))?6:0):1;
        response_groups<=0;response_map<=0;response_layers<=latched_on&&!cancel_seen&&!(cancel_valid&&cancel_token==latched_token)?latched_layers:0;
        base=latched_layers==1?latched_note-60:(latched_note-60)*4;
        if(latched_on&&!cancel_seen&&!(cancel_valid&&cancel_token==latched_token))for(layer=0;layer<4;layer=layer+1)if(latched_layers[layer])begin
            response_groups[(base+layer)%32]<=1;response_map[layer*5+:5]<=(base+layer)%32;
        end
    end
end
task wait_ready;
begin
    timeout=0;
    while(!frame_ready)begin @(negedge clk);timeout=timeout+1;if(timeout>20000)$fatal(1,"FRAME_TIMEOUT");end
end
endtask
initial begin
    trace=$fopen("trace.txt","w");script=$fopen("commands.txt","r");
    repeat(3)@(negedge clk);rst_n=1;event_ready=1;reply_ready=1;
    while(!$feof(script))begin
        status=$fscanf(script,"%d %d %d %d %d %h %d %d %d\n",kind,seq,mask,bad,cal,positions,vel,delta,selected);
        if(status!=9)$fatal(1,"BAD_SCRIPT");
        if(kind==0)begin
            wait_ready();frame_valid=1;contact=mask;invalid=bad;position=positions;
            frame_sequence=seq;frame_calibration=cal;velocity=vel;glide=delta;layer_selection=selected;
            for(index=0;index<NF_VALUE;index=index+1)note_map[index*7+:7]=60+index;
            @(negedge clk);frame_valid=0;contact=0;position=0;note_map=0;velocity=0;glide=0;layer_selection=0;frame_calibration=0;invalid=0;
            wait_ready();repeat(40)@(negedge clk);
            $fdisplay(trace,"BOUNDARY %0d %0d %0d",frame_sequence,seen_contacts,blocked_contacts);
        end else if(kind==1)begin
            retire_valid=1;retire_token=seq;@(negedge clk);retire_valid=0;
        end else if(kind==2)begin
            repeat(2050)@(negedge clk);wait_ready();repeat(40)@(negedge clk);
            $fdisplay(trace,"BOUNDARY %0d %0d %0d",frame_sequence,seen_contacts,blocked_contacts);
        end else if(kind==3)delay_mode=500;
        else if(kind==4)begin repeat(600)@(negedge clk);delay_mode=DELAY_VALUE;$fdisplay(trace,"LINK %0d",link_error);end
    end
    $fdisplay(trace,"FLAGS %0d",{admission_error,watchdog_error,sensor_error,link_error,frame_error});
    if(protocol_error)$fatal(1,"ENDPOINT_PROTOCOL_ERROR");
    $fclose(script);$fclose(trace);$display("PASS frames NF=%0d",NF_VALUE);$finish;
end
endmodule
'''.replace('DECLARATIONS', '\n'.join(declarations)).replace('CONNECTIONS', connections).replace('NF_VALUE', str(nf)).replace('STALLED_VALUE', '1' if stalled else '0').replace('DELAY_VALUE', '17' if stalled else '3')


def compare(trace, expected, only=None):
    if not trace.is_file():
        return dict(channel='missing-trace')
    actual = {key: [] for key in expected}
    for line in trace.read_text(encoding='utf-8').splitlines():
        words = line.split()
        if not words or words[0] not in actual:
            return dict(channel='invalid-trace')
        try:
            actual[words[0]].append([int(word) for word in words[1:]])
        except ValueError:
            return dict(channel='unknown-state')
    for channel in expected:
        if (only is None or channel in only) and actual[channel] != expected[channel]:
            mismatch = next((index for index, (left, right) in enumerate(zip(actual[channel], expected[channel])) if left != right), min(len(actual[channel]), len(expected[channel])))
            return dict(channel=channel, index=mismatch, actual=actual[channel][mismatch:mismatch+1], expected=expected[channel][mismatch:mismatch+1])
    return None


def main():
    parser = argparse.ArgumentParser(description='Actual immutable frame-format producer plus contact ledger; allocator replies remain stubs')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fault-checks', action='store_true')
    arguments = parser.parse_args()
    output = output_path(arguments.output)
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    sources = [Path(__file__).resolve(), ROOT/'frame_transport.py', ROOT/'contact_rtl_reference.py', ROOT/'contact_contract.py', ROOT/'verify_contact_rtl.py', ROOT/'diagnose_timing.py', ROOT/'build.py']
    sources += [ROOT/'rtl'/name for name in ('contact_frame_source.v', 'note_frame_transport.v', 'note_contact_adapter.v')]
    identities = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    if (ROOT/'rtl/note_frame_transport.v').read_bytes() != wrapper().encode('utf-8'):
        raise ValueError('Frame wrapper differs from declared port mapping')
    output.mkdir(parents=True)
    snapshots = output/'original-inputs'
    snapshots.mkdir()
    for path in sources:
        shutil.copyfile(path, snapshots/path.name)
    reports = []
    for fault, nf, stalled in [('candidate', 4, False), ('candidate', 26, False), ('candidate', 4, True)]+([(fault, 4, False) for fault in FAULTS] if arguments.fault_checks else []):
        directory = output/(fault+'-nf'+str(nf)+('-stalled' if stalled else ''))
        directory.mkdir()
        commands, expected = fixture(nf)
        (directory/'commands.txt').write_text(''.join(' '.join(format(value, 'x') if index == 5 else str(value) for index, value in enumerate(command))+'\n' for command in commands), encoding='utf-8')
        (directory/'expected.json').write_text(json.dumps(expected, indent=2)+'\n', encoding='utf-8')
        source = directory/'contact_frame_source.v'
        source.write_bytes(mutate((ROOT/'rtl/contact_frame_source.v').read_text(encoding='utf-8'), fault).encode('utf-8'))
        testbench = directory/'tb_frames.v'
        testbench.write_bytes(bench(nf, stalled).encode('utf-8'))
        binary = directory/'frames.vvp'
        compilation, text = run([str(compiler), '-g2012', '-s', 'tb_frames', '-o', str(binary), str(source), str(ROOT/'rtl/note_frame_transport.v'), str(ROOT/'rtl/note_contact_adapter.v'), str(testbench)], directory, 'compile.log')
        report = dict(case=fault, nf=nf, stalled=stalled, passed=False, compilation=compilation,
            source_sha256=digest(source), bench_sha256=digest(testbench), commands_sha256=digest(directory/'commands.txt'),
            expected_sha256=digest(directory/'expected.json'), frames=sum(command[0] == 0 for command in commands))
        if compilation['returncode'] == 0:
            simulation, text = run([str(simulator), str(binary)], directory, 'run.log')
            difference = compare(directory/'trace.txt', expected)
            designated = compare(directory/'trace.txt', expected, [FAULTS[fault][2]]) if fault in FAULTS else None
            valid = simulation['returncode'] == 0 and 'PASS frames NF='+str(nf) in text
            held_fault = fault == 'held-retrigger' and simulation['returncode'] not in (0, 124) and 'HELD_RETRIGGER' in text
            qualified = valid and (difference is None if fault == 'candidate' else designated is not None and designated['channel'] == FAULTS[fault][2])
            report.update(simulation=simulation, first_difference=difference, designated_difference=designated, passed=held_fault or qualified)
            if (directory/'trace.txt').is_file():
                report['trace_sha256'] = digest(directory/'trace.txt')
        reports.append(report)
        print(directory.name+': '+('PASS' if report['passed'] else 'FAIL'), flush=True)
    changes = [name for name, sha in identities.items() if digest(PROJECT/name) != sha]
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=identities, source_changes=changes,
        tools={str(path): digest(path) for path in (compiler, simulator)}, reports=reports,
        status='PASS' if all(report['passed'] for report in reports) and not changes else 'FAIL',
        scope='Captured frame-format producer and contact RTL ledger; no analog scan, finger_pitch consumer, real allocator/renderer/score or physical qualification',
        physical_source_integrated=False, real_allocator_integrated=False, product_acceptance=False)
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
