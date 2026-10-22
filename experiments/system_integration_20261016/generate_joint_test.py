"""Extend the previously verified music scenario with concurrent real modules."""
from pathlib import Path
R=Path(__file__).resolve().parent
source=R.parent/'right_hand_audio_20261016/tb_music.v'
s=source.read_text(encoding='utf-8')
(R/'tb_compat_music.v').write_text(s,encoding='utf-8')
s=s.replace('module tb_music;', 'module tb_joint;').replace('rh_music_probe dut(', 'instrument_joint_probe dut(').replace('dut.core.','dut.music.core.')
s=s.replace('    instrument_joint_probe dut(', '''    reg [5:0] sense_n=6'b111111;
    reg calibrate=0;
    wire scan_bus_request,scan_bus_sck,scan_bus_mosi,scan_latch;
    wire sensor_report_valid,sensor_report_calibration,sensor_protocol_error,sensor_grant_error;
    wire [25:0] sensor_contact,sensor_invalid;
    wire [233:0] sensor_position;
    wire [31:0] sensor_sequence,spectrum_sequence;
    wire lcd_reset_n;
    integer sensor_reports=0,model_cycle=0,charge_at=0,charge_frame=0,j,node,delay;
    integer fft_capture_count=0,fft_busy_left=0,expected_analysis_gaps=0,expected_fft_frames=0;
    // Independent schedule budget: 512 butterflies x10 stages x8 clocks,
    // drain1 + clear48 + bin scan512x3 + publication48. Audio keeps running.
    always @(posedge clk)if(rst_n)begin
        if(fft_busy_left>0)begin
            if(pcm_valid)expected_analysis_gaps=expected_analysis_gaps+1;
            if(fft_busy_left==1)expected_fft_frames=expected_fft_frames+1;
            fft_busy_left=fft_busy_left-1;
        end else if(pcm_valid)begin
            if(fft_capture_count==1023)begin fft_capture_count=0;fft_busy_left=42593;end
            else fft_capture_count=fft_capture_count+1;
        end
    end
    always @(negedge clk)if(rst_n)begin
        if(dut.analysis_gaps!==expected_analysis_gaps||spectrum_sequence!==expected_fft_frames)$fatal(1,"FFT schedule changed under concurrency gaps=%d expected=%d",dut.analysis_gaps,expected_analysis_gaps);
    end
    reg old_sck=0,old_latch=0;
    reg [7:0] shift=0,control=8'hff;
    always @(negedge clk)begin
        model_cycle=model_cycle+1;
        if(scan_bus_sck&&!old_sck)shift={shift[6:0],scan_bus_mosi};
        if(scan_latch&&!old_latch)begin
            control=shift;
            if(control[5]&&!control[4])begin charge_at=model_cycle;charge_frame=dut.sensor.scanner.scan_sequence;end
        end
        old_sck=scan_bus_sck;old_latch=scan_latch;
        for(j=0;j<6;j=j+1)begin
            node=control[3:0]*6+j;delay=15+node;
            if(charge_frame>=1&&node==2)delay=delay+40;
            sense_n[j]=!(!control[4]&&control[5]&&model_cycle-charge_at>=delay);
        end
    end
    always @(posedge clk)if(rst_n&&sensor_report_valid)begin
        if(sensor_protocol_error||sensor_grant_error||sensor_invalid)$fatal(1,"concurrent sensor fault");
        if(sensor_sequence!=sensor_reports)$fatal(1,"sensor frame lost");
        if(sensor_sequence>=1&&sensor_position[8:0]!=256)$fatal(1,"concurrent position");
        if(sensor_sequence>=2&&sensor_contact!=26'd1)$fatal(1,"concurrent contact");
        sensor_reports=sensor_reports+1;
    end
    initial begin wait(rst_n);@(negedge clk);calibrate=1;@(negedge clk);calibrate=0;end
    instrument_joint_probe dut(''')
s=s.replace('.pcm_valid(pcm_valid),.pcm(pcm));', '''.pcm_valid(pcm_valid),.pcm(pcm),
        .sense_n(sense_n),.calibrate(calibrate),.scan_bus_grant(1'b1),.sensor_report_ready(1'b1),
        .threshold_on(14'd20),.threshold_off(14'd10),.scan_bus_request(scan_bus_request),.scan_bus_sck(scan_bus_sck),.scan_bus_mosi(scan_bus_mosi),.scan_latch(scan_latch),
        .sensor_report_valid(sensor_report_valid),.sensor_report_calibration(sensor_report_calibration),.sensor_protocol_error(sensor_protocol_error),.sensor_grant_error(sensor_grant_error),
        .sensor_contact(sensor_contact),.sensor_invalid(sensor_invalid),.sensor_position(sensor_position),.sensor_sequence(sensor_sequence),
        .spectrum_sequence(spectrum_sequence),.lcd_reset_n(lcd_reset_n));''')
s=s.replace('        $display("PASS music', '''        repeat(512*1200)@(negedge clk);
        if(sensor_reports<10||spectrum_sequence==0||!lcd_reset_n)$fatal(1,"insufficient concurrent coverage");
        $display("PASS joint sensor_reports=%0d fft_frames=%0d analysis_gaps=%0d audio_pcm_exact_in_unity fft_schedule_exact display_reset_only",sensor_reports,spectrum_sequence,dut.analysis_gaps);
        $display("PASS music''')
(R/'tb_joint.v').write_text(s,encoding='utf-8')
print('Generated compatibility and concurrent music/sensor/FFT tests; no sensor-to-note bridge claimed')
