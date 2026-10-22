"""Structural scan timing harness, deliberately not a playable board firmware."""
from common import *
import re
src=(R/'rtl/sdram_stream_probe.v').read_text(encoding='utf-8')
header=src.split(')(',1)[1].split(');',1)[0]
ports=[];direction=None;width='';signed=''
for chunk in header.replace('\n',' ').split(','):
    chunk=chunk.strip()
    m=re.match(r'(input|output|inout)\s+wire\s*(signed\s*)?(\[\d+:\d+\])?\s*(\w+)$',chunk)
    if m:direction,signed,width,name=m.groups();width=width or '';signed=signed or ''
    else:
        assert re.fullmatch(r'\w+',chunk) and direction,chunk
        name=chunk
    bits=1 if not width else abs(int(re.findall(r'\d+',width)[0])-int(re.findall(r'\d+',width)[1]))+1
    ports.append(dict(name=name,direction=direction,width=width,signed=signed,bits=bits))
special={'clk':'logic_clk','rst_n':'rst_n','pad':'unused_pad','led':'led',
    'sd_clk':'O_sdram_clk','sd_cke':'O_sdram_cke','sd_cs_n':'O_sdram_cs_n',
    'sd_ras_n':'O_sdram_ras_n','sd_cas_n':'O_sdram_cas_n','sd_we_n':'O_sdram_wen_n',
    'sd_addr':'O_sdram_addr','sd_bank':'O_sdram_ba','sd_dqm':'O_sdram_dqm','sd_dq':'IO_sdram_dq'}
unused={'sdram_req_valid', 'sdram_req_write', 'sdram_rsp_ready','sdram_req_addr','sdram_req_data'}
decl=[];connections=[];output_names=[];offset=0
for p in ports:
    n=p['name']
    if n in special:expression=special[n]
    elif n in unused:expression="%d'd0"%p['bits']
    elif p['direction']=='input':
        expression='controls[%d +: %d]'%(offset,p['bits']);p['scan_offset']=offset;offset+=p['bits']
    else:
        assert p['direction']=='output',p
        expression='probe_'+n;decl.append('wire %s%s %s;'%(p['signed'],p['width'],expression));output_names.append(expression)
    connections.append('.%s(%s)'%(n,expression))
outputs=sum(p['bits'] for p in ports if p['name'] not in special and p['direction']=='output')
chunks=(outputs+31)//32
clock=(R/'reference/clock-wrapper.v').read_text(encoding='utf-8').split(' wire logic_clk',1)[1].split(' // Synthetic data',1)[0]
body='''// Structural scan harness ONLY. All controls are independently reachable over
// serial history, but arbitrary bit shifts are not valid performance events.
// Never program this bitstream: no functional bench gate or user protocol.
module joint_timing_top(
 input wire clk,reset_button,scan_in,output wire probe_out,
 output wire [5:0] led,output wire dac_din,dac_ws,dac_bck,pa_en,
 output wire O_sdram_clk,O_sdram_cke,O_sdram_cs_n,
 output wire O_sdram_ras_n,O_sdram_cas_n,O_sdram_wen_n,
 output wire [10:0] O_sdram_addr,output wire [1:0] O_sdram_ba,
 output wire [3:0] O_sdram_dqm,inout wire [31:0] IO_sdram_dq
);
 wire logic_clk'''+clock+'''
 // External scan_in reaches only the first synchronizer stage.
 reg scan_meta,scan_sync;
 always @(posedge logic_clk)begin scan_meta<=scan_in;scan_sync<=scan_meta;end
 localparam INPUT_BITS=%d,OUTPUT_BITS=%d,OBS_CHUNKS=%d;
 reg [INPUT_BITS-1:0] controls;
 always @(posedge logic_clk)controls<={controls[INPUT_BITS-2:0],scan_sync};
 tri [15:0] unused_pad;
 %s
 sdram_stream_probe system(%s);
 wire [OUTPUT_BITS-1:0] observable={%s};
 wire [OBS_CHUNKS*32-1:0] padded={{(OBS_CHUNKS*32-OUTPUT_BITS){1'b0}},observable};
 reg [OBS_CHUNKS-1:0] observation;
 wire [OBS_CHUNKS-1:0] capture;
 genvar c;generate for(c=0;c<OBS_CHUNKS;c=c+1)begin: observer
  assign capture[c]=^padded[c*32+:32];
 end endgenerate
 reg [5:0] phase;
 always @(posedge logic_clk or negedge rst_n)
  if(!rst_n)begin phase<=0;observation<=0;end
  else begin
   phase<=phase+1'b1;
   if(phase==0)observation<=capture;
   else observation<={1'b0,observation[OBS_CHUNKS-1:1]};
  end
 assign probe_out=observation[0];
 // No acoustic output: internal DAC logic remains visible in observation.
 assign {dac_din,dac_ws,dac_bck,pa_en}=4'd0;
endmodule
'''%(offset,outputs,chunks,'\n '.join(decl),',\n '.join(connections),','.join(output_names))
(R/'rtl/joint_timing_top.v').write_text(body,encoding='utf-8')
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'));board_root=Path(up['board_root'])
for name in ('constraints/sdram_board.sdc','reference/stress.sdc'):
    p=R/name;original=board_root/name;assert sha(original)==up['board_files'][name]
    text=original.read_text().replace('uart_tx_pin','probe_out')
    text+='\n# scan_in has no destination except first synchronizer stage.\nset_false_path -from [get_ports {scan_in}]\n'
    p.write_text(text,encoding='utf-8')
p=R/'constraints/sdram_board.cst';original=board_root/'constraints/sdram_board.cst'
assert sha(original)==up['board_files']['constraints/sdram_board.cst']
text=original.read_text().replace('uart_tx_pin','probe_out')
text+='\nIO_LOC "scan_in" 70;\nIO_PORT "scan_in" IO_TYPE=LVCMOS33 PULL_MODE=UP;\n'
p.write_text(text,encoding='utf-8')
(R/'project/scan-map.json').write_text(json.dumps(dict(input_bits=offset,output_bits=outputs,observer_chunks=chunks,ports=ports,ignored_upstream_ports=sorted(unused),bench_gate=False),indent=2),encoding='utf-8')
print('Generated structural harness:',offset,'scan controls,',outputs,'observed bits;',chunks,'registered parity chunks; NOT PROGRAMMABLE')
