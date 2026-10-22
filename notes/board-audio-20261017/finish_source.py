from pathlib import Path
import re
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017';S=R/'src'
p=S/'left_layer_music_probe.v';s=p.read_text(encoding='utf-8').replace('LINK_TIMEOUT=8192,BOARD_DIAG=0)(', 'LINK_TIMEOUT=8192,BOARD_DIAG=0,UART_BAUD=115200)(')
if '.UART_BAUD(UART_BAUD)' not in s:s=s.replace('.BOARD_DIAG(BOARD_DIAG),.DIAG_FINGER(0)', '.BOARD_DIAG(BOARD_DIAG),.DIAG_FINGER(0),.UART_BAUD(UART_BAUD)')
s=s.replace('.UART_BAUD(UART_BAUD),.UART_BAUD(UART_BAUD)', '.UART_BAUD(UART_BAUD)');p.write_text(s,encoding='utf-8')
if 'DIAG_CAPTURE_SAMPLES' not in s:
    s=s.replace('UART_BAUD=115200)(', 'UART_BAUD=115200,DIAG_CAPTURE_SAMPLES=2048)(').replace('.UART_BAUD(UART_BAUD)', '.UART_BAUD(UART_BAUD),.DIAG_CAPTURE_SAMPLES(DIAG_CAPTURE_SAMPLES)');p.write_text(s,encoding='utf-8')
s=re.sub(r'(\.DIAG_FINGER\(0\))(?:,\.(?:UART_BAUD|DIAG_CAPTURE_SAMPLES)\([^)]*\))*',r'\1,.UART_BAUD(UART_BAUD),.DIAG_CAPTURE_SAMPLES(DIAG_CAPTURE_SAMPLES)',s);p.write_text(s,encoding='utf-8')
p=S/'tdm_top_owned.v';s=p.read_text(encoding='utf-8')
if 'DIAG_CAPTURE_SAMPLES' not in s:
    s=s.replace('parameter integer DIAG_FINGER=1,','parameter integer DIAG_FINGER=1,DIAG_CAPTURE_SAMPLES=2048,').replace("diag_stream_count<13'd6143",'diag_stream_count<DIAG_CAPTURE_SAMPLES*3-1').replace('board_diag #(.FINGER_SCOPE(32))','board_diag #(.FINGER_SCOPE(32),.CAPTURE_SAMPLES(DIAG_CAPTURE_SAMPLES))');p.write_text(s,encoding='utf-8')
s=s.replace("diag_stream_byte <= diag_stream_byte==2 ? 0 : diag_stream_byte+1'b1;", "diag_stream_byte <= diag_stream_byte==2'd0 ? 2'd1 : diag_stream_byte==2'd1 ? 2'd2 : 2'd0;");p.write_text(s,encoding='utf-8')
U=P/'experiments/resource_safety_20261016'
(S/'board_slots.hex').write_text((U/'sustain.hex').read_text(encoding='ascii')+(U/'strike.hex').read_text(encoding='ascii'),encoding='ascii')
C=R/'constraints';C.mkdir(exist_ok=True)
pins={'clk':4,'reset_button':87,'uart_rx_pin':70,'uart_tx_pin':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
(C/'board_audio.cst').write_text('// Board-only audio test. No external header or physical touch pins.\n'+''.join('IO_LOC "'+name+'" '+str(pin)+';\nIO_PORT "'+name+'" IO_TYPE=LVCMOS33 PULL_MODE='+('DOWN' if name=='reset_button' else 'UP')+(' DRIVE=8' if name not in ('clk','reset_button','uart_rx_pin') else '')+';\n' for name,pin in pins.items()),encoding='ascii')
(C/'board_audio.sdc').write_text('''# Internal 27 MHz timing. External I2S receiver timing is not signed off here.
create_clock -name clk -period 37.037 [get_ports {clk}]
set_false_path -from [get_ports {reset_button}]
set_false_path -from [get_ports {uart_rx_pin}]
''',encoding='ascii')
print('Prepared builtin-only pins and 27 MHz internal timing constraints')
