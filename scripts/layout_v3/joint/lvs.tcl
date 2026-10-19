set extracted [readnet spice $env(V3_JOINT_RUN)/extract/startup_integrated_v3.spice]
set reference [readnet verilog /dev/null]
readnet spice $env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice $reference
readnet spice $env(V3_ROOT)/layout/startup_v3/startup_test_macro.spice $reference
readnet verilog $env(V3_ROOT)/build/control-v3/physical/final/pnl/pixel_control_v3.pnl.v $reference
readnet verilog $env(V3_ROOT)/layout/startup_v3/joint/startup_integrated_v3.v $reference
lvs "$extracted startup_integrated_v3" "$reference startup_integrated_v3" $env(PDK_ROOT)/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl $env(V3_JOINT_RUN)/netgen-lvs.log -json
quit
