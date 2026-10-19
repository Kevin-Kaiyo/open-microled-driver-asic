gds read $env(V3_GDS)
load startup_test_macro
select top cell
drc style drc(full)
drc style
drc check
drc catchup
puts "ROUNDTRIP_DRC_COUNT [drc list count total]"
puts "ROUNDTRIP_DRC_ERRORS [drc listall why]"
save startup_test_macro
extract all
ext2spice lvs
ext2spice
extract style ngspice()
extract do capacitance
extract do coupling
extresist threshold 0
extresist minres 0
extresist mindelay 0
extract do resistance
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o startup_test_macro_rc.spice
quit -noprompt
