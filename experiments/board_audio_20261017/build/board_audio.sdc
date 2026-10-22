# Internal 27 MHz timing. External I2S receiver timing is not signed off here.
create_clock -name clk -period 37.037 [get_ports {clk}]
set_false_path -from [get_ports {reset_button}]
set_false_path -from [get_ports {uart_rx_pin}]
