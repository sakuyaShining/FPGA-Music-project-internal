# Candidate timing envelope; exact embedded die/bin and package delays unbound.
create_clock -name sys_clk -period 37.037 -waveform {0 18.5185} [get_ports {clk}]
# Only asynchronous reset source and asynchronous human/UART status endpoints.
# No exceptions on the SDRAM interface or related clocks.
set_false_path -from [get_ports {reset_button}]
set_false_path -to [get_ports {led[*] uart_tx_pin}]
