set extracted [readnet spice $env(INTEGRATION_RUN)/pixel_integrated.spice]
set reference [readnet verilog /dev/null]
readnet spice $env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice $reference
readnet spice $env(INTEGRATION_ROOT)/layout/pixel_driver_schematic.spice $reference
readnet verilog $env(INTEGRATION_ROOT)/evidence/physical/digital/pnl/pixel_pwm.pnl.v $reference
readnet verilog $env(INTEGRATION_ROOT)/layout/integration/pixel_integrated.v $reference
lvs "$extracted pixel_integrated" "$reference pixel_integrated" $env(PDK_ROOT)/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl $env(INTEGRATION_RUN)/netgen-lvs.log -json
quit
