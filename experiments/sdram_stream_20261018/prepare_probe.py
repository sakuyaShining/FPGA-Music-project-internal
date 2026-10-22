from common import *
old=(R/'rtl/sdram_storage_probe.v').read_text(encoding='utf-8')
ports='''
 output wire rec_clear_ready,play_clear_ready,rec_clear_done,play_clear_done,
 output wire rec_clearing,play_clearing,mem_busy,
 output wire [17:0] rec_ring_level,play_ring_level,
'''
top=old.replace('module sdram_storage_probe','module sdram_stream_probe',1).replace('(\n','(\n'+ports,1)
ref=top.replace('endmodule', '''
assign rec_clear_ready=1;assign play_clear_ready=1;assign rec_clear_done=0;assign play_clear_done=0;
assign rec_clearing=0;assign play_clearing=0;assign mem_busy=0;
assign rec_ring_level=0;assign play_ring_level=0;
endmodule''')
(R/'reference/sdram_stream_probe.v').write_text(ref,encoding='utf-8')
start=top.index('pcm_storage_buffers buffers(');end=top.index('));',start)+3
top=top[:start]+'''wire transport_req_valid,transport_req_write,transport_rsp_ready;
wire [21:0] transport_req_addr;wire [15:0] transport_req_data;
pcm_sdram_stream transport(.clk(clk),.rst_n(rst_n),
 .rec_clear(rec_clear),.play_clear(play_clear),
 .rec_clear_ready(rec_clear_ready),.play_clear_ready(play_clear_ready),
 .rec_clear_done(rec_clear_done),.play_clear_done(play_clear_done),
 .rec_clearing(rec_clearing),.play_clearing(play_clearing),
 .rec_enable(rec_enable),.pcm_valid(pcm_valid),.pcm_data(pcm[23:8]),
 .rec_valid(rec_valid),.rec_ready(rec_ready),.rec_data(rec_data),.rec_level(rec_level),.rec_overflow(rec_overflow),
 .play_enable(play_enable),.sample_tick(pcm_valid),.play_level(play_level),
 .feed_valid(feed_valid),.feed_ready(feed_ready),.feed_data(feed_data),
 .play_valid(play_valid),.play_data(play_data),.play_underflow(play_underflow),.play_miss(play_miss),
 .rec_ring_level(rec_ring_level),.play_ring_level(play_ring_level),
 .mem_req_valid(transport_req_valid),.mem_req_ready(sdram_req_ready),.mem_req_write(transport_req_write),
 .mem_req_addr(transport_req_addr),.mem_req_data(transport_req_data),
 .mem_rsp_valid(sdram_rsp_valid),.mem_rsp_ready(transport_rsp_ready),.mem_rsp_data(sdram_rsp_data),.mem_busy(mem_busy));'''+top[end:]
for a,b in [('req_valid','transport_req_valid'),('req_write','transport_req_write'),('req_addr','transport_req_addr'),('req_data','transport_req_data'),('rsp_ready','transport_rsp_ready')]:
 top=top.replace('.'+a+'(sdram_'+a+')','.'+a+'('+b+')')
top=top.replace('// Internal logical interfaces, not a physical GPIO allocation or shipping top.',
 '// Logical resource probe, not a GPIO allocation/shipping top. Historical external\n// sdram_req* inputs are unused here, retained only for same-port reference comparison.')
(R/'rtl/sdram_stream_probe.v').write_text(top,encoding='utf-8')
p=R/'synthesize.py';s=p.read_text().replace('sdram_storage_probe','sdram_stream_probe').replace("top='pcm_storage_buffers'","top='pcm_sdram_arbiter'")
p.write_text(s,encoding='utf-8')
print('Prepared same-source registered-controller reference and ring-transport joint probe')
