from common import *
T=R.parents[1]/'experiments/sdram_timing_20261018'
s=(T/'rtl/sdram_board_top.v').read_text()
header=s[s.index(' input wire clk,reset_button,'):s.index(' wire logic_clk,clock_locked;')]
clock=s[s.index(' wire logic_clk,clock_locked;'):s.index(' wire rst_n=reset_release[1];')+len(' wire rst_n=reset_release[1];')]
params='''// Volatile synthetic SDRAM stream bench. Audio outputs muted; no Flash/TF.
module sdram_board_top #(parameter FIFO_AW=10,RING_AW=17,
 NORMAL_SAMPLES=(1<<(RING_AW+1))+4096,RECOVERY_SAMPLES=4096,PREFILL=4096,HOLD_TICKS=4096,
 SAMPLE_DIV=512,FAST_DIV=32,HEARTBEAT=2700000,UART_BAUD=115200,WATCHDOG=810000000)(
'''
(R/'rtl/sdram_board_top.v').write_text(params+header+clock+'\n'+(R/'reference/board_body.vpart').read_text())
print('Generated muted stage83 board wrapper; unchanged stage82 transport and stage81 PLL')
