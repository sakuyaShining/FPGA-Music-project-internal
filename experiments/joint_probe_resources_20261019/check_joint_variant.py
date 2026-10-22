"""Forced-control RTL integration test, not a usable scan or board protocol."""
from common import *
mapping=json.loads((R/'project/scan-map.json').read_text(encoding='utf-8'))
ports={p['name']:p for p in mapping['ports']}
def setp(name,value):
    p=ports[name];return 'vector[%d+:%d]=%s;'%(p['scan_offset'],p['bits'],value)
defaults={'uart_rx_pin':"1'b1",'layer_selection':"4'd1",'sense_n':"6'h3f",'scan_bus_grant':"1'b1",'left_velocity':"4'd10",'threshold_on':"14'd8",'threshold_off':"14'd4",'ev_note':"7'd60",'ev_vel':"4'd10",'radius':"10'd50",'slew_step':"10'd16",'voice_mask':"32'hffffffff"}
initial='\n'.join(setp(k,v) for k,v in defaults.items())
initial+='\n'+setp('left_note_map',"182'd0")
for i in range(26):initial+='\nvector[%d+:7]=%d;'%(ports['left_note_map']['scan_offset']+i*7,48+i)
for i in range(16):initial+='\nvector[%d+:3]=%d;'%(ports['part_to_control']['scan_offset']+i*3,i//2)
wiring='\n'.join('if(dut.system.%s!==dut.controls[%d+:%d])$fatal(1,"scan port %s");'%(p['name'],p['scan_offset'],p['bits'],p['name']) for p in mapping['ports'] if 'scan_offset' in p)
tb='''`timescale 1ns/1ps
module tb_joint;
reg gsr_n=0;GSR GSR(.GSRI(gsr_n));
parameter ACCESS_DELAY=10;
reg clk=0;always #18.5185 clk=~clk;
reg reset_button=1,scan_in=0;wire probe_out;wire [5:0]led;
wire di,ws,bck,pa,sc,cke,cs,ras,cas,we;wire[10:0]addr;wire[1:0]ba;wire[3:0]dqm;tri[31:0]dq;
joint_timing_top dut(.clk(clk),.reset_button(reset_button),.scan_in(scan_in),.probe_out(probe_out),.led(led),
 .dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.O_sdram_clk(sc),.O_sdram_cke(cke),.O_sdram_cs_n(cs),
 .O_sdram_ras_n(ras),.O_sdram_cas_n(cas),.O_sdram_wen_n(we),.O_sdram_addr(addr),.O_sdram_ba(ba),.O_sdram_dqm(dqm),.IO_sdram_dq(dq));
wire [31:0]refreshes,reads,writes,max_gap;
sdram_timing_model #(.ACCESS_DELAY(ACCESS_DELAY)) memory(.clk(sc),.cke(cke),.cs_n(cs),.ras_n(ras),.cas_n(cas),.we_n(we),.addr(addr),.ba(ba),.dqm(dqm),.dq(dq),.operational(dut.probe_sdram_init_done),.refreshes(refreshes),.reads(reads),.writes(writes),.max_refresh_gap(max_gap));
reg [%d:0]vector=0,expected_shift=0;
reg [29:0]expected_observation;
reg [31:0]random_state=32'h841985;
integer i,cycles=0,recorded=0,drained=0,fed=0,played=0,nonzero=0,pcm_seen=0,previous_pcm=-1;
reg active=0,observe_check=0;reg[15:0]queue[0:1023];
function[15:0]pattern;input integer n;begin pattern=(n*173)^16'h6a53;end endfunction
always @(posedge clk)begin
 cycles=cycles+1;
 if(dut.rst_n)begin
  if(dut.phase==0)expected_observation=dut.capture;else expected_observation={1'b0,dut.observation[29:1]};
  observe_check=1;
 end else begin expected_observation=0;observe_check=0;end
 if(active)begin
  if(dut.probe_pcm_valid)begin
   if(previous_pcm>=0&&cycles-previous_pcm!=512)$fatal(1,"sample period");previous_pcm=cycles;pcm_seen=pcm_seen+1;
  end
  if(dut.probe_pcm_valid&&dut.system.rec_enable)begin
   if((^dut.probe_pcm)===1'bx)$fatal(1,"unknown music PCM");
   queue[recorded]=dut.probe_pcm[23:8];recorded=recorded+1;if(dut.probe_pcm!=0)nonzero=nonzero+1;
  end
  if(dut.probe_rec_valid&&dut.system.rec_ready)begin
   if(drained>=recorded||dut.probe_rec_data!==queue[drained])$fatal(1,"live record mismatch at %%0d",drained);drained=drained+1;
  end
  if(dut.system.feed_valid&&dut.probe_feed_ready)fed=fed+1;
  if(dut.probe_play_valid)begin
   if(played>=fed||dut.probe_play_data!==pattern(played))$fatal(1,"playback mismatch");played=played+1;
  end
  if(dut.probe_rec_overflow||dut.probe_play_underflow)$fatal(1,"unexpected transport fault");
 end
 #1;
 if(observe_check&&dut.observation!==expected_observation)$fatal(1,"registered observation mismatch");
 if({di,ws,bck,pa}!==4'd0)$fatal(1,"acoustic isolation");
 %s
end
initial begin
 // Check actual shift transport before forcing the internal integration controls.
 repeat(3)@(negedge clk);gsr_n=1;
 for(i=0;i<700;i=i+1)begin
  @(negedge clk);random_state=random_state*1664525+1013904223;scan_in=random_state[31];
  @(posedge clk);expected_shift={expected_shift[%d:0],dut.scan_sync};#1;
  if(i>=%d&&dut.controls!==expected_shift)begin
   $fatal(1,"input scan shift i=%%0d xor=%%h",i,dut.controls^expected_shift);
  end
 end
 @(negedge clk);vector=0;%s
 force dut.controls=vector;
 @(negedge clk);reset_button=0;
 wait(dut.probe_sdram_init_done);repeat(5000)@(negedge clk);active=1;
 %s
 @(negedge clk);%s %s
 @(negedge clk);%s
 // Feed more than the eventual consumption count, allowing bounded prefill.
 for(i=0;i<256;i=i+1)begin
  @(negedge clk);%s %s
  while(!dut.probe_feed_ready)@(negedge clk);
 end
 @(negedge clk);%s
 repeat(5000)@(negedge clk);%s
 wait(recorded>=200);@(negedge clk);%s
 wait(played>=200);@(negedge clk);%s
 wait(drained==recorded);repeat(200)@(negedge clk);
 if(recorded<200||drained!=recorded||played<200||nonzero<50||refreshes<100||reads<400||writes<400)$fatal(1,"coverage rec%%0d drain%%0d play%%0d nz%%0d reads%%0d writes%%0d",recorded,drained,played,nonzero,reads,writes);
 $display("PASS forced joint RTL cycles=%%0d PCM=%%0d recorded=%%0d drained=%%0d played=%%0d nonzero=%%0d refresh=%%0d max_gap=%%0d scan700 observer audio_muted; NOT hardware protocol",cycles,pcm_seen,recorded,drained,played,nonzero,refreshes,max_gap);$finish;
end
initial begin #12000000;$fatal(1,"joint watchdog");end
endmodule
'''%(mapping['input_bits']-1,wiring,mapping['input_bits']-2,mapping['input_bits'],initial,
setp('rec_ready',"1'b1"),setp('ev_on',"1'b1"),setp('ev_valid',"1'b1"),setp('ev_valid',"1'b0"),
setp('feed_valid',"1'b1"),setp('feed_data','pattern(i)'),setp('feed_valid',"1'b0"),setp('rec_enable',"1'b1")+' '+setp('play_enable',"1'b1"),
setp('rec_enable',"1'b0"),setp('play_enable',"1'b0"))
p=R/'tb/tb_mac_joint.v';p.write_text(tb,encoding='utf-8')
files=[R/'reference/probe_scan_store_mac.v' if f.name=='probe_scan_store.v' else f for f in sources()]+[R/'tb/vendor_ram16sdp4.v',R/'tb/vendor_alu54d.v',R/'tb/vendor_mac18.v',R/'tb/sdram_timing_model.v',p]
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py',R/'project/scan-map.json']}
results={}
for delay in (3,16):
    name='mac-joint-delay%d'%delay
    run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s','tb_joint','-Ptb_joint.ACCESS_DELAY='+str(delay),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[str(delay)]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,R/'engine/src')
original=R/'rtl/sdram_stream_probe.v';text=original.read_text(encoding='utf-8')
assert text.count('.pcm_data(pcm[23:8])')==1
fault=E/'wrong-mac-live-record.v';fault.write_text(text.replace('.pcm_data(pcm[23:8])',".pcm_data(pcm[23:8]^16'h1)"),encoding='utf-8')
ff=[fault if p==original else p for p in files]
run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s','tb_joint','-o',str(E/'wrong-mac-live-record.vvp'),*map(str,ff)],'compile-mac-live-fault')
out=subprocess.run([VVP,str(E/'wrong-mac-live-record.vvp')],cwd=R/'engine/src',capture_output=True,text=True,timeout=120)
(E/'mac-live-fault.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and 'live record mismatch' in out.stdout,out.stdout+out.stderr
fixture=E/'missing-mac-powerup-reset.v'
assert tb.count('reg gsr_n=0;GSR GSR')==1
fixture.write_text(tb.replace('reg gsr_n=0;GSR GSR','reg gsr_n=1;GSR GSR'),encoding='utf-8')
bad=[fixture if f==p else f for f in files]
run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s','tb_joint','-o',str(E/'missing-mac-powerup-reset.vvp'),*map(str,bad)],'compile-mac-reset-fixture-fault')
startup=subprocess.run([VVP,str(E/'missing-mac-powerup-reset.vvp')],cwd=R/'engine/src',capture_output=True,text=True,timeout=120)
(E/'mac-reset-fixture-fault.log').write_text(startup.stdout+startup.stderr,encoding='utf-8')
assert startup.returncode!=0 and 'input scan shift' in startup.stdout,startup.stdout+startup.stderr
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'mac-joint-model.json').write_text(json.dumps(dict(status='PASS scoped forced-control joint RTL integration; no playable protocol or hardware qualification',results=results,detected_fault=out.stdout,reproduced_bad_startup_fixture=startup.stdout,inputs=inputs,pll_simulated=False,bench_gate=False),indent=2),encoding='utf-8')
