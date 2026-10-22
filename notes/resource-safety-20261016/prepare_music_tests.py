from pathlib import Path
P=Path(__file__).resolve().parents[2];R=P/'experiments/resource_safety_20261016';U=P/'experiments/instrument_layers_20261016'
for name,core in [('tb_compat_music.v','dut.core'),('tb_layers.v','dut.core'),('tb_sensor_layers.v','dut.music.core')]:
    s=(U/name).read_text(encoding='utf-8')
    trace='''
    integer trace_fd,trace_cycle=0;
    reg [2047:0] trace_path;
    initial begin
        if(!$value$plusargs("trace=%s",trace_path))$fatal(1,"trace path missing");
        trace_fd=$fopen(trace_path,"w");if(!trace_fd)$fatal(1,"trace open");
    end
    always @(posedge clk)begin
        trace_cycle=trace_cycle+1;
        $fdisplay(trace_fd,"%0d %b %b %b %b %h %b %b %h %h %b %b %h %b %h %h",trace_cycle,
            CORE.dac_din,CORE.dac_ws,CORE.dac_bck,CORE.monitor_valid,
            CORE.monitor_valid?CORE.monitor_pcm:24'd0,CORE.voice_valid,CORE.voice_on,
            CORE.voice_group,CORE.voice_note,CORE.own_ready,CORE.result_valid,
            CORE.result_valid?CORE.result_instance:15'd0,CORE.finger_valid,
            CORE.finger_active,CORE.finger_offsets);
    end
'''.replace('CORE',core)
    assert s.count('endmodule')==1
    (R/name).write_text(s.replace('endmodule',trace+'endmodule'),encoding='utf-8')
print('Prepared full music traces: all I2S clocks, PCM samples, events and expression outputs')
