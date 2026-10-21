"""Reconcile current carrier with frozen experiment 86 in an isolated candidate."""
import csv,difflib,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HW=ROOT.parent
BASE=Path('C:/Users/Sakuya/FPGA-Music-project/experiments/joint_probe_resources_20261019/engine/src')
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
IV=Path('D:/iverilog/bin/iverilog.exe');VVP=IV.with_name('vvp.exe')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pcb_before=h(PCB)
assert pcb_before=='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e'
original={n:h(BASE/n) for n in ['rc_mux_scan.v','scan_shift595.v','rc_strip_positions.v','instrument_sensor_probe.v','rc_delta_store.v']}
pads=json.loads((HW/'quality-r1-source-78.json').read_text(encoding='utf-8'))['pads']
pin=lambda ref,n:next(p['net'] for p in pads if p['ref']==ref and p['n']==str(n))
assert [pin('U8',n) for n in [15,1,2,3,4,5,6,7]]==['ADDR0','ADDR1','ADDR2','ADDR3','MUX_DISABLE','RC_DRIVE','LCD_RESET_N','TP_RESET_N']
src=(BASE/'rc_mux_scan.v').read_text(encoding='utf-8')
assert 'wire [7:0] word_data={2\'b00,' in src
patched=src.replace('module rc_mux_scan #(', 'module rc_mux_scan_hw #(')
patched=patched.replace('input wire clk,rst_n,','input wire clk,rst_n,\n    input wire [1:0] peripheral_reset_n, // Q7 touch reset, Q6 shared display reset; active low')
patched=patched.replace("wire [7:0] word_data={2'b00,",'wire [7:0] word_data={peripheral_reset_n,')
(ROOT/'rc_mux_scan_hw.v').write_text(patched,encoding='utf-8')
(ROOT/'scan-reset-adapter.diff').write_text(''.join(difflib.unified_diff(src.splitlines(True),patched.splitlines(True),fromfile='frozen86/rc_mux_scan.v',tofile='candidate/rc_mux_scan_hw.v')),encoding='utf-8')

maps={};mapping_rows=[]
for count in [25,26]:
    rows=list(csv.DictReader((HW/f'electrode-map-{count}-OPTION.csv').open(encoding='utf-8-sig')))
    assert len(rows)==84
    mapped=[]
    for row in rows:
        if row['role'].startswith('NOTE_SLOT_'):
            logical=int(row['logical_node']);lane=int(row['lane']);addr=int(row['mux_address'])
            assert pin(row['connector'],int(row['connector_pin']))==row['net']
            assert pin(f'U{lane+1}',[9,8,7,6,5,4,3,2,23,22,21,20,19,18][addr])==f'L{lane}_M{addr:02d}'
            # Frozen rc_delta_store explicitly uses address-major node IDs.
            raw=addr*6+lane
            mapped.append(raw)
            mapping_rows.append(dict(slots=count,logical_node=logical,role=row['role'],lane=lane,mux_address=addr,
                raw_store_node=raw,legacy_identity_node=logical,legacy_matches=raw==logical,net=row['net']))
    assert len(mapped)==count*3 and len(set(mapped))==len(mapped)
    assert all(x<84 for x in mapped) and all(x//6<14 for x in mapped)
    maps[count]=mapped
    packed=sum(x<<(7*i) for i,x in enumerate(mapped))
    (ROOT/f'board-map-{count}.vh').write_text(f"localparam [{count*21-1}:0] BOARD_NODE_MAP = {count*21}'h{packed:x};\n",encoding='ascii')
with (ROOT/'node-map-audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(mapping_rows[0]));writer.writeheader();writer.writerows(mapping_rows)

tb=r'''`timescale 1ns/1ps
module tb_scan;
reg clk=0;always #5 clk=~clk;
reg rst_n=0;reg [1:0] resets=3;reg grant=1,ready=1;
wire sck,mosi,latch,request,row_valid,grant_error;
wire [3:0] addr;wire [71:0] counts;wire [5:0] faults;wire [31:0] seq;
reg [7:0] shift=0,q=0;integer bits=0,latches=0,rows=0,errors=0,k;reg [3:0] expected_addr=0;
integer charge_age=0;reg [5:0] sense=6'b111111;reg [7:0] q_prev=0;
`ifdef PATCHED
rc_mux_scan_hw #(.DISCHARGE_CYCLES(12),.TIMEOUT_CYCLES(40),.SPI_HALF_PERIOD(2)) dut(
 .peripheral_reset_n(resets),
`else
rc_mux_scan #(.DISCHARGE_CYCLES(12),.TIMEOUT_CYCLES(40),.SPI_HALF_PERIOD(2)) dut(
`endif
 .clk(clk),.rst_n(rst_n),.sense_n(sense),.bus_request(request),.bus_grant(grant),
 .bus_sck(sck),.bus_mosi(mosi),.scan_latch(latch),.row_valid(row_valid),.row_ready(ready),
 .row_address(addr),.row_count(counts),.row_fault(faults),.row_sequence(seq),.grant_error(grant_error));
always @(posedge sck)begin shift={shift[6:0],mosi};bits=bits+1;end
always @(posedge latch)begin
 q=shift;
 if(bits!=8)begin $display("BAD_WORD_LENGTH %0d",bits);errors=errors+1;end
 bits=0;
 if(q[7:6]!==resets)begin $display("RESET_COLLISION q=%h expected=%b",q,resets);errors=errors+1;end
 case(latches%4)
 0,1:if(q[5:4]!==2'b01)errors=errors+1;
 2:if(q[5:4]!==2'b00)errors=errors+1;
 3:if(q[5:4]!==2'b10)errors=errors+1;
 endcase
 latches=latches+1;
end
always @(posedge clk)begin
 if(!q[5]||q[4])charge_age<=0;else charge_age<=charge_age+1;
 for(k=0;k<6;k=k+1)begin
  if(!q[5]||q[4])sense[k]<=1;
  else if(k==5&&rows>=16)sense[k]<=1; // deliberate stuck-untransitioned input
  else sense[k]<=charge_age<(4+k);
 end
 q_prev<=q;
end
always @(posedge clk)if(rst_n&&row_valid&&ready)begin
 if(addr!==expected_addr)begin $display("ADDRESS_ORDER %d != %d",addr,expected_addr);errors=errors+1;end
 if(seq!==rows/16)begin $display("SEQUENCE_ORDER");errors=errors+1;end
 expected_addr=expected_addr+1'b1;
 for(k=0;k<6;k=k+1)begin
  if(rows>=16&&k==5)begin
   if(!faults[k]||counts[k*12+:12]!=40)begin $display("MISSING_TIMEOUT");errors=errors+1;end
  end else if(faults[k]||counts[k*12+:12]==0||counts[k*12+:12]>20)begin
   $display("BAD_MEASURE lane=%d count=%d fault=%b",k,counts[k*12+:12],faults[k]);errors=errors+1;
  end
 end
 rows=rows+1;
 // At a quiet word boundary, exercise independent reset states.
 if(rows==8)resets=2'b10;
 if(rows==16)resets=2'b01;
 if(rows==24)resets=2'b11;
 if(rows==32)begin
  if(grant_error)errors=errors+1;
  if(errors)$fatal(1,"SCAN_CONTRACT_FAIL errors=%0d rows=%0d words=%0d",errors,rows,latches);
  $display("SCAN_CONTRACT_PASS rows=%0d words=%0d reset_states=3 timeout=detected",rows,latches);$finish;
 end
end
initial begin repeat(8)@(negedge clk);rst_n=1;end
// Grant stalls only before a word begins; report backpressure does not relatch.
initial begin wait(rst_n);repeat(12)begin wait(!request);@(negedge clk);grant=0;repeat(7)@(negedge clk);grant=1;wait(request);wait(!request);end end
initial begin wait(rst_n);repeat(5)begin wait(row_valid);@(negedge clk);ready=0;repeat(9)@(negedge clk);ready=1;wait(!row_valid);end end
initial begin #1000000;$fatal(1,"SCAN_TIMEOUT");end
endmodule
'''
(ROOT/'tb_scan.v').write_text(tb,encoding='ascii')

def execute(label,sources,defines=(),expect_success=True):
    dest=ROOT/label;dest.mkdir(exist_ok=True)
    cmd=[str(IV),'-g2012',*['-D'+x for x in defines],'-s','tb_scan' if label.startswith('scan') else 'tb_map','-o',str(dest/'sim.vvp'),*[str(x) for x in sources]]
    cp=subprocess.run(cmd,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    (dest/'compile.log').write_bytes(cp.stdout+cp.stderr);assert cp.returncode==0,(label,cp.stderr)
    sp=subprocess.run([str(VVP),str(dest/'sim.vvp')],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    (dest/'run.log').write_bytes(sp.stdout+sp.stderr)
    accepted=(sp.returncode==0)==expect_success
    assert accepted,(label,sp.stdout.decode(errors='replace')[-1200:])
    log=sp.stdout.decode(errors='replace')
    if not expect_success:
        assert ('RESET_COLLISION' if label.startswith('scan') else 'MAP_MISMATCH') in log
        assert 'TIMEOUT' not in log
        if label.startswith('scan'):assert all(x not in log for x in ['BAD_MEASURE','MISSING_TIMEOUT','ADDRESS_ORDER','SEQUENCE_ORDER','BAD_WORD_LENGTH'])
    return dict(case=label,command=cmd,compile_rc=cp.returncode,simulation_rc=sp.returncode,
                expected_success=expect_success,expectation_matched=accepted,
                sources={str(p):h(p) for p in sources})

runs=[execute('scan_original_negative',[ROOT/'tb_scan.v',BASE/'rc_mux_scan.v',BASE/'scan_shift595.v'],expect_success=False),
      execute('scan_candidate',[ROOT/'tb_scan.v',ROOT/'rc_mux_scan_hw.v',BASE/'scan_shift595.v'],defines=['PATCHED'])]

for count,mapped in maps.items():
    for candidate in [False,True]:
        chosen=mapped if candidate else list(range(count*3))
        packed=sum(x<<(7*i) for i,x in enumerate(chosen))
        rom=[0]*96;expected=[]
        for strip in range(count):
            ds=[13+strip,5+2*strip,3+strip]
            for el in range(3):rom[mapped[strip*3+el]]=ds[el]
            expected.append((ds[1]+2*ds[2])*128//sum(ds))
        init='\n'.join(f'rom[{i}]={v};valid_rom[{i}]={int(i in mapped)};' for i,v in enumerate(rom))
        exp='\n'.join(f'expected[{i}]={v};' for i,v in enumerate(expected))
        text=f'''`timescale 1ns/1ps
module tb_map;
reg clk=0;always #5 clk=~clk;reg rst_n=0,frame=0;
wire frame_ready,report;wire [6:0] address;wire [{count-1}:0] contact,invalid;
wire [{count*9-1}:0] position;wire [31:0] sequence_out;wire calibration;
reg [11:0] delta=0;reg valid=0;reg [11:0] rom[0:95];reg valid_rom[0:95];integer expected[0:{count-1}];integer k,errors=0;
rc_strip_positions #(.STRIPS({count}),.CONFIRM_FRAMES(1),.NODE_MAP({count*21}'h{packed:x})) dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame),.frame_ready(frame_ready),.frame_sequence(32'd17),.frame_calibration(1'b0),
 .read_address(address),.read_delta(delta),.read_valid(valid),.threshold_on(14'd1),.threshold_off(14'd0),
 .report_valid(report),.report_ready(1'b1),.contact(contact),.invalid(invalid),.position(position),
 .report_sequence(sequence_out),.report_calibration(calibration));
always @(posedge clk)begin delta<=rom[address];valid<=valid_rom[address];end
initial begin
{init}
{exp}
repeat(5)@(negedge clk);rst_n=1;@(negedge clk);frame=1;wait(report);#1;
if(sequence_out!=17||calibration)errors=errors+1;
for(k=0;k<{count};k=k+1)if(invalid[k]||!contact[k]||position[k*9+:9]!==expected[k])begin
 $display("MAP_MISMATCH strip=%d expected=%d actual=%d invalid=%b",k,expected[k],position[k*9+:9],invalid[k]);errors=errors+1;end
if(errors)$fatal(1,"NODE_MAP_FAIL errors=%d",errors);
$display("NODE_MAP_PASS strips={count} positions=all contacts=all");$finish;
end
initial begin #1000000;$fatal(1,"MAP_TIMEOUT");end
endmodule
'''
        label=f'map_{count}_'+('candidate' if candidate else 'original_negative')
        file=ROOT/(label+'.v');file.write_text(text,encoding='ascii')
        runs.append(execute(label,[file,BASE/'rc_strip_positions.v'],expect_success=candidate))

assert all(h(BASE/n)==sha for n,sha in original.items()) and h(PCB)==pcb_before
result={'pcb_unchanged':True,'frozen86_sources_unchanged':original,
        'reset_bits_conflict_confirmed':True,'legacy_map_matches_physical_26':sum(x==i for i,x in enumerate(maps[26])),
        'physical_nodes_26':78,'physical_nodes_25':75,'runs':runs,
        'candidate_has_runtime_reset_input':True,'candidate_node_maps_derived_from_native_pads':True,
        'limits':['digital isolated contract tests only','no analog RC validation','no final shared-bus/reset controller integration','no joint PnR/STA or bitstream','not deployed to frozen product'],
        'manufacturing_release':False}
(ROOT/'contract-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Hardware contract: reset collision and lane/address mismatch reproduced; isolated candidates verified; native PCB and frozen sources unchanged.',flush=True)
for r in runs:print(r['case'],r['simulation_rc'],'expected',r['expected_success'])
