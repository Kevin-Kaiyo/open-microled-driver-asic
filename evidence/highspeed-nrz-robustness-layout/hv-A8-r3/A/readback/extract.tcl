gds read /Users/kimmy/Projects/open-microled-driver-asic/build/highspeed-nrz-robustness-layout/hv-A8-r3/A/generate/hs_voltage_robust.gds
load hs_voltage_robust
select top cell
box values -5.3999999999999995um 12.540000000000001um -5.2um 12.74um
label DATA center metal3
port make 1
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port make 2
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
box values 31.099999999999998um 4.5um 31.3um 4.699999999999999um
label VH center metal3
port make 4
box values 28.209999999999997um 5.7um 28.41um 5.8999999999999995um
label VL center metal3
port make 5
box values 1.0999999999999999um 6.9um 1.3um 7.1um
label VSS center metal3
port make 6
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save hs_voltage_robust
extract all
ext2spice lvs
ext2spice
extract style ngspice()
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist off
ext2spice -o hs_voltage_robust_c.spice
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice extresist on
ext2spice -o hs_voltage_robust_rc.spice
quit -noprompt
