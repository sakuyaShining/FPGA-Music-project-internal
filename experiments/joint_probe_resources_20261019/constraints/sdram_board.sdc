# Candidate timing envelope; exact embedded die/bin and package delays unbound.
create_clock -name sys_clk -period 37.037 -waveform {0 18.5185} [get_ports {clk}]
create_generated_clock -name core_clk -source [get_ports {clk}] -divide_by 1 [get_pins {clocking/CLKOUT}]
create_generated_clock -name sdram_forward -source [get_pins {clocking/CLKOUT}] -divide_by 1 -invert [get_ports {O_sdram_clk}]
set_clock_uncertainty -setup 0.5 -from [get_clocks {sys_clk core_clk sdram_forward}]
set_clock_uncertainty -hold 0.2 -from [get_clocks {sys_clk core_clk sdram_forward}]
set_input_delay -clock sdram_forward -max 6.5 [get_ports {IO_sdram_dq[*]}]
set_input_delay -clock sdram_forward -min 1.0 [get_ports {IO_sdram_dq[*]}]
set_output_delay -clock sdram_forward -max 3.0 [get_ports {O_sdram_addr[*] O_sdram_ba[*] O_sdram_dqm[*] O_sdram_ras_n O_sdram_cas_n O_sdram_wen_n IO_sdram_dq[*]}]
set_output_delay -clock sdram_forward -min -2.0 [get_ports {O_sdram_addr[*] O_sdram_ba[*] O_sdram_dqm[*] O_sdram_ras_n O_sdram_cas_n O_sdram_wen_n IO_sdram_dq[*]}]
# Only asynchronous reset source and asynchronous human/UART status endpoints.
# No exceptions on the SDRAM interface or related clocks.
set_false_path -from [get_ports {reset_button}]
set_false_path -to [get_ports {led[*] probe_out}]

# scan_in has no destination except first synchronizer stage.
set_false_path -from [get_ports {scan_in}]
