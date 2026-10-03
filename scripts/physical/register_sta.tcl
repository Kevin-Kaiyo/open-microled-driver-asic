# Explicit register-to-register cross-check from implemented netlist and SPEF.
# The flow's endpoint-limited setup summary can show R2R=N/A when an input
# path is the worst path to every register. Keep the same final SDC.
set root $::env(ASICFLOW_ROOT)
set run_dir $::env(ASICFLOW_RUN)
set corner $::env(ASICFLOW_CORNER)
set rc [lindex [split $corner _] 0]
set pvt [join [lrange [split $corner _] 1 end] _]
read_lef $root/build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__$rc.tlef
read_lef $root/build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_liberty $root/build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__$pvt.lib
read_verilog $run_dir/final/nl/pixel_pwm.nl.v
link_design pixel_pwm
read_sdc $run_dir/final/sdc/pixel_pwm.sdc
read_spef $run_dir/final/spef/$rc/pixel_pwm.$rc.spef
puts "R2R_BEGIN_SETUP $corner"
report_checks -from [all_registers -output_pins] -to [all_registers -data_pins] -path_delay max -group_path_count 1000 -format full_clock_expanded -fields {slew cap fanout} -digits 6
puts "R2R_END_SETUP $corner"
puts "R2R_BEGIN_HOLD $corner"
report_checks -from [all_registers -output_pins] -to [all_registers -data_pins] -path_delay min -group_path_count 1000 -format full_clock_expanded -fields {slew cap fanout} -digits 6
puts "R2R_END_HOLD $corner"
report_check_types -max_slew -max_capacitance -max_fanout -violators -digits 6
check_setup -verbose -unconstrained_endpoints -multiple_clock -no_clock -no_input_delay -loops -generated_clocks
