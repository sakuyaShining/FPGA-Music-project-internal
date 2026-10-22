"""Read-only product audit diagnostics for source baseline 90e891d.
Runs counterexamples; exit 0 means the diagnostic runner finished, not product acceptance.
Outputs go to ignored sim_build/audit_20261006. No Git mutation or hardware access.
Requires D:/iverilog/bin (same as existing project scripts).
"""
from pathlib import Path
import subprocess, shutil, json
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'sim_build' / 'audit_20261006'
OUT.mkdir(parents=True, exist_ok=True)
IV = Path('D:/iverilog/bin')
results = {}
def probe(name, body, sources):
    d = OUT / name
    d.mkdir(exist_ok=True)
    for h in (ROOT/'src/gowin/tdm_synth').glob('*.hex'):
        shutil.copy(h, d)
    (d/'probe.v').write_text(body, encoding='utf-8')
    c = subprocess.run([str(IV/'iverilog.exe'), '-g2005', '-DSIM_INIT', '-s', 'probe', '-o', str(d/'probe.vvp'), str(d/'probe.v')] + [str(ROOT/'src/rtl'/s) for s in sources], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if c.returncode:
        results[name] = c.stderr
    else:
        r = subprocess.run([str(IV/'vvp.exe'), 'probe.vvp'], cwd=d, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        results[name] = r.stdout + r.stderr
    print(name, results[name], flush=True)
# In 16-bit slots the final bit of the previous word coincides with WS transition.
# Collect it first, then start the new word on the following rising edge.
probe('i2s_standard', '''`timescale 1ns/1ps
module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0;
wire be,bck,lr,se,sd,ws;
audio_clk_en #(.DIV_BCK(16),.BCK_PER_LRCK(32)) c(clk,rst_n,be,bck,lr,se);
i2s_tx t(clk,rst_n,be,lr,se,24'h123400,sd,ws);
reg last_ws=0; integer n=0; reg [15:0] word=0; integer count=0;
always @(posedge bck) if(rst_n) begin
  word={word[14:0],sd}; n=n+1;
  if(ws!=last_ws) begin
    if(count>2) $display("standard_I2S expected=1234 received=%h bits=%0d",word,n);
    count=count+1; last_ws=ws; n=0;
  end
end
initial begin #23 rst_n=1; #30000 $finish; end
endmodule''', ['audio_clk_en.v','i2s_tx.v'])
probe('strip_switch', '''module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0; reg[4:0] cells=0; wire[2:0] pos; wire[4:0] led;
strip_ctrl #(.CLK_HZ(1000),.HOLD_MS(10)) d(clk,rst_n,cells,pos,led);
initial begin #22 rst_n=1; @(negedge clk) cells=1; repeat(9) @(negedge clk); cells=16; repeat(2) @(negedge clk);
$display("switch_after_9_of_10: pos=%0d expected=1 (new cell held only 2 clocks)",pos);
repeat(15) @(negedge clk); cells=4; repeat(15) @(negedge clk);
$display("switch_without_gap: pos=%0d expected=2 after full hold",pos); $finish; end
endmodule''', ['strip_ctrl.v'])
probe('note_map', '''module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0,valid=0,on=0,refresh=0;
reg[6:0] note=60; reg[7:0] vel=64; wire busy,le; wire[8:0] slot; wire[23:0] inc; wire[7:0] amp; wire gate; wire[22:0] ep; wire signed[17:0] gq; wire[31:0] active;
note_map d(.clk(clk),.rst_n(rst_n),.ev_valid(valid),.ev_on(on),.ev_note(note),.ev_vel(vel),.preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd32),.load_en(le),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),.load_epar(ep),.load_gq(gq),.busy(busy),.active(active));
task event_note; input[6:0] nn; input oo; input[7:0] vv; begin
@(negedge clk); valid=1; note=nn; on=oo; vel=vv; @(negedge clk); valid=0; end endtask
task idle; begin repeat(5) @(negedge clk); wait(!busy); repeat(3) @(negedge clk); end endtask
always @(negedge clk) if(le && slot[3:0]==0) $display("load slot=%0d amp=%0d gate=%0d vel_cur=%0d",slot,amp,gate,d.vel_cur);
initial begin #22 rst_n=1;
event_note(60,1,64); event_note(64,1,240); idle;
$display("busy_collision active=%h expected_two_notes=00000003",active);
event_note(64,1,240); idle;
@(negedge clk) refresh=1; @(negedge clk) refresh=0; idle;
$display("refresh_complete (compare slot0 amplitude with original)");
event_note(60,0,0); idle;
$display("note_off_complete (compare slot0 amplitude with original)");
event_note(108,1,240); idle;
$display("nyquist_overflow note108 part15 ratio=%0d full_inc=%0d truncated=%0d kill=%0d",d.ratio_q8,d.inc_mul>>8,d.inc_cal,d.nyq_kill);
$finish; end
endmodule''', ['note_map.v','vel_shape.v'])
nm = (OUT/'note_map/probe.v').read_text()
start = nm.index('initial begin #22')
nm = nm[:start] + '''integer j;
initial begin #22 rst_n=1;
event_note(60,1,240); idle;
for(j=61;j<=91;j=j+1) begin event_note(j,1,240); idle; event_note(j,0,0); idle; end
$display("allocator_before active=%h held_note60=%0d",active,d.gtab[0]);
event_note(92,1,240); idle;
$display("allocator_after active=%h slot0_note=%0d expected_60_with_idle_voices",active,d.gtab[0]);
$finish; end
endmodule'''
probe('allocator', nm, ['note_map.v','vel_shape.v'])
import xml.etree.ElementTree as ET
prj=ROOT/'src/gowin/tdm_synth/tdm_synth.gprj'
top_sources=[Path(x.attrib['path']).name for x in ET.parse(prj).findall('.//File') if x.attrib['path'].endswith('.v')]
probe('pad_chord', '''module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0;
wire[5:0] led; wire tx,di,ws,bck,pa; wire[15:0] pad;
tdm_ship d(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(tx),.led(led),.dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.pad(pad));
initial begin #22 rst_n=1; repeat(500) @(negedge clk);
force d.u_top.pad_state=16'h00ff; repeat(500) @(negedge clk);
$display("8_pad_chord active=%h expected=000000ff seen=%h",d.u_top.nm_active,d.u_top.u_pitch.seen);
$finish; end
endmodule''',top_sources)
probe('group_boundary', '''module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0; reg le=0; reg[8:0] ls=0;
wire[5:0] led; wire tx,di,ws,bck,pa; wire[15:0] pad;
tdm_ship d(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(tx),.led(led),.dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.pad(pad));
integer epoch=0; integer j;
always @(posedge clk) if(rst_n) begin
 if(d.u_top.u_tdm.sc==511) epoch=epoch+1;
 if(d.u_top.u_tdm.consume && d.u_top.u_tdm.sl1<16) $display("consume slot=%0d epoch=%0d ppr1=%0d pp1=%0d",d.u_top.u_tdm.sl1,epoch,d.u_top.u_tdm.ppr1,d.u_top.u_tdm.pp1);
end
initial begin
force d.u_top.nm_load_en=le; force d.u_top.nm_load_slot=ls;
force d.u_top.nm_load_inc=24'd100000; force d.u_top.nm_load_amp=8'd200;
force d.u_top.nm_load_gate=1'b1; force d.u_top.nm_load_epar=23'd3831924;
#22 rst_n=1; repeat(600) @(negedge clk); wait(d.u_top.u_tdm.sc==504);
@(negedge clk); le=1; for(j=0;j<16;j=j+1) begin ls=j; @(negedge clk); end le=0;
repeat(1200) @(negedge clk); $finish; end
endmodule''',top_sources)
warm=(OUT/'note_map/probe.v').read_text()
warm=warm[:warm.index('initial begin #22')]+'''initial begin #22 rst_n=1;
event_note(60,1,240); idle; @(negedge clk) rst_n=0; repeat(3) @(negedge clk);
rst_n=1; repeat(5) @(negedge clk);
$display("warm_reset active=%h expected=00000000",active); $finish; end
endmodule'''
probe('warm_reset',warm,['note_map.v','vel_shape.v'])
(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
