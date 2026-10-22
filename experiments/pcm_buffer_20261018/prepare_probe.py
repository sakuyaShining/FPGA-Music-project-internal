from common import *
original=(R/'engine/src/instrument_layer_probe.v').read_text(encoding='utf-8')
ports='''
    input wire rec_clear,rec_enable,rec_ready,play_clear,play_enable,
    input wire feed_valid,input wire [15:0] feed_data,
    output wire feed_ready,rec_valid,rec_overflow,play_valid,play_underflow,play_miss,
    output wire [15:0] rec_data,play_data,
    output wire [10:0] rec_level,play_level,
'''
text=original.replace('module instrument_layer_probe','module storage_probe',1).replace('(\n','(\n'+ports,1)
body='''
// Measurement tap only. The live PCM/I2S path is byte-for-byte unchanged.
// This truncation is a resource-probe input, not a frozen recording format.
pcm_storage_buffers buffers(.clk(clk),.rst_n(rst_n),
 .rec_clear(rec_clear),.rec_enable(rec_enable),.pcm_valid(pcm_valid),.pcm_data(pcm[23:8]),
 .rec_valid(rec_valid),.rec_ready(rec_ready),.rec_data(rec_data),.rec_level(rec_level),.rec_overflow(rec_overflow),
 .play_clear(play_clear),.play_enable(play_enable),.sample_tick(pcm_valid),
 .feed_valid(feed_valid),.feed_ready(feed_ready),.feed_data(feed_data),
 .play_valid(play_valid),.play_data(play_data),.play_level(play_level),.play_underflow(play_underflow),.play_miss(play_miss));
'''
stub='''
assign feed_ready=0;assign rec_valid=0;assign rec_overflow=0;assign play_valid=0;
assign play_underflow=0;assign play_miss=0;assign rec_data=0;assign play_data=0;
assign rec_level=0;assign play_level=0;
'''
(R/'reference').mkdir(exist_ok=True)
(R/'rtl/storage_probe.v').write_text(text.replace('endmodule',body+'\nendmodule'),encoding='utf-8')
(R/'reference/storage_probe.v').write_text(text.replace('endmodule',stub+'\nendmodule'),encoding='utf-8')
print('Prepared identical live-engine probes; only the added buffer branch differs')
