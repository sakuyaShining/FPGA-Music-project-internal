# DFR0072: bounded current module review

[Domestic manufacturer product](https://www.dfrobot.com.cn/goods-123.html): exact SKU DFR0072, listed25CNY, official5V specification; actual current inventory, Qingyuan freight and dispatch not confirmed. One board would cover8shifted outputs if its exact3V3/timing/rail contract is verified. This is not an accepted purchase substitute.

[Manufacturer schematic](https://dfimg.dfrobot.com/wiki/17401/DFR0072_gravity-shiftout-module_schematics_V1.0.pdf), page1, visually reviewed:74HC595D, CLR10 tiedVCC, OE13 tiedGND, four104P decouplers; IDC6input1clock/2VCC/3latch/4GND/5data/6GND. J1/J3oddpins are outputs, their EVENpins areVCC, notGround. J2/J4 areGround. This matters for a safe harness. No assumption based on module photograph or a generic74HC595 label.

Native U8 uses3V3_IO and8outputsADDR0..3/MUX_DISABLE/RC_DRIVE/LCD_RESET_N/TP_RESET_N. DFRobot publishes thisSKUas5V. Exact populated IC and3V3 timing/offrail behavior are still unproved; powering it5V and directly connecting to the3V3front-end is not accepted. RegisteredprobeSPI_HALF_PERIOD8 is only a probe, not wholeproduct acceptance. The board does not cover165 inputchain, sharedreadback, I2Coffrail isolation, interruptconditioning, screenbuffer or protectedpower.

Keep module candidate and exact wiring evidence; do not call bareDIP chips/preweld footprint library a qualifiedmodule. No purchase/order/inquiry/RTL/flash actions.
