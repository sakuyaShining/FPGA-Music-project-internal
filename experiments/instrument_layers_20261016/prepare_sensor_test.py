from pathlib import Path
R=Path(__file__).resolve().parent;S=R.parent/'left_hand_events_20261016'
s=(S/'tb_sensor_music.v').read_text(encoding='utf-8').replace('module tb_sensor_music;','module tb_sensor_layers;').replace('instrument_owned_probe dut(',"instrument_layer_probe dut(.layer_selection(4'b0011),.cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(48'd0),")
s=s.replace('ons!=3','ons!=6').replace('offs==3','offs==6').replace('PASS sensor_music','PASS sensor_layers')
s=s.replace('0:g0=dut.music.result_group;12:g12=dut.music.result_group;13:g13=dut.music.result_group;', '0:g0=dut.music.layers.groups0[0];12:g12=dut.music.layers.groups0[12];13:g13=dut.music.layers.groups0[13];')
s=s.replace('            motion_checked=1;', '''            if(dut.music.core.finger_offsets[dut.music.layers.groups1[0]*18+:18]!=dut.music.core.finger_offsets[g0*18+:18])$fatal(1,"sensor slide did not reach second layer");
            motion_checked=1;''')
s=s.replace('    reg motion_checked=0;', '''    reg motion_checked=0;
    reg [31:0] pcm_hash=0;integer unknown_pcm=0;''')
s=s.replace('            last_sample=cycle;samples=samples+1;if(pcm!=0)nonzero=nonzero+1;', '''            last_sample=cycle;samples=samples+1;if(pcm!=0)nonzero=nonzero+1;
            if((^pcm)===1'bx)begin unknown_pcm=unknown_pcm+1;if(cycle>4096)$fatal(1,"unknown PCM after warmup");end
            else pcm_hash={pcm_hash[26:0],pcm_hash[31:27]}^{8'd0,pcm};''')
s=s.replace('moves=%0d physical_words', 'moves=%0d pcm_hash=%08x startup_unknown_pcm=%0d physical_words').replace('ons,offs,moves);$finish;', 'ons,offs,moves,pcm_hash,unknown_pcm);$finish;')
(R/'tb_sensor_layers.v').write_text(s,encoding='utf-8')
print('Prepared raw sensor to dual-layer music test')
