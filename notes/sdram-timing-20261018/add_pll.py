from pathlib import Path
import shutil
R=Path(__file__).resolve().parents[2]/'experiments/sdram_timing_20261018'
shutil.copyfile(R/'rtl/sdram_board_top.v',R/'reference/sdram_board_top_direct_clock.v')
shutil.copyfile(R/'constraints/sdram_board.sdc',R/'reference/direct_clock.sdc')
s=(R/'rtl/sdram_board_top.v').read_text()
s=s.replace('reg [1:0] reset_release=0;', '''wire logic_clk,clock_locked;
`ifdef TIMING_RTL_SIM
 // Only for functional protocol simulation; not a model of PLL jitter/lock.
 assign logic_clk=clk;
 assign clock_locked=1'b1;
`else
 rPLL clocking(.CLKOUT(logic_clk),.LOCK(clock_locked),.CLKOUTP(),.CLKOUTD(),.CLKOUTD3(),
 .RESET(1'b0),.RESET_P(1'b0),.CLKIN(clk),.CLKFB(1'b0),
 .FBDSEL(6'd0),.IDSEL(6'd0),.ODSEL(6'd0),.PSDA(4'd0),.DUTYDA(4'd0),.FDLY(4'd0));
 defparam clocking.FCLKIN="27",clocking.DYN_IDIV_SEL="false",clocking.IDIV_SEL=0,
 clocking.DYN_FBDIV_SEL="false",clocking.FBDIV_SEL=0,clocking.DYN_ODIV_SEL="false",clocking.ODIV_SEL=32,
 clocking.PSDA_SEL="0000",clocking.DYN_DA_EN="true",clocking.DUTYDA_SEL="1000",
 clocking.CLKOUT_FT_DIR=1'b1,clocking.CLKOUTP_FT_DIR=1'b1,clocking.CLKOUT_DLY_STEP=0,
 clocking.CLKOUTP_DLY_STEP=0,clocking.CLKFB_SEL="internal",clocking.CLKOUT_BYPASS="false",
 clocking.CLKOUTP_BYPASS="false",clocking.CLKOUTD_BYPASS="false",clocking.DYN_SDIV_SEL=2,
 clocking.CLKOUTD_SRC="CLKOUT",clocking.CLKOUTD3_SRC="CLKOUT",clocking.DEVICE="GW2AR-18C";
`endif
 wire reset_assert=reset_button || !clock_locked;
 reg [1:0] reset_release=0;''')
s=s.replace('posedge clk','posedge logic_clk').replace('or posedge reset_button','or posedge reset_assert').replace('if(reset_button)','if(reset_assert)').replace('.clk(clk)','.clk(logic_clk)')
(R/'rtl/sdram_board_top.v').write_text(s)
p=R/'constraints/sdram_board.cst';s=p.read_text().replace('CLOCK_LOC "clk" BUFG;\n','');p.write_text(s)
p=R/'constraints/sdram_board.sdc';s=p.read_text();s=s.replace('create_generated_clock -name sdram_forward -source [get_ports {clk}]', 'create_generated_clock -name core_clk -source [get_ports {clk}] -divide_by 1 [get_pins {clocking/CLKOUT}]\ncreate_generated_clock -name sdram_forward -source [get_pins {clocking/CLKOUT}]').replace('get_clocks {sys_clk sdram_forward}','get_clocks {sys_clk core_clk sdram_forward}');p.write_text(s)
p=R/'check_board.py';s=p.read_text().replace("[IV,'-g2012'", "[IV,'-g2012','-DTIMING_RTL_SIM'");p.write_text(s)
print('Prepared 1:1 PLL candidate, VCO864MHz; requires tool/lock/STA checks')
