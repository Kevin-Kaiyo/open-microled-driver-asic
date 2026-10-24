gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/vi-pg-r2d/V/generate/nrz_vi_reference.gds
load nrz_vi_reference
select top cell
foreach name {VIN VSS VSET SENSE IOUT IPB IN2 ICTRL} {
 while {[port $name exists -quiet]} {port $name remove -quiet}
}
box values 9.1um 0.9um 9.299999999999999um 1.1um
label VIN center metal3
port VIN make 1
box values 86.10000000000001um 2.9um 86.3um 3.1um
label VSS center metal3
port VSS make 2
box values 49.6um 4.9um 49.800000000000004um 5.1um
label VSET center metal3
port VSET make 3
box values 71.60000000000001um 6.9um 71.8um 7.1um
label SENSE center metal3
port SENSE make 4
box values 194.34um 8.9um 194.54um 9.1um
label IOUT center metal3
port IOUT make 5
box values 11.34um 10.9um 11.54um 11.1um
label IPB center metal3
port IPB make 6
box values 66.34um 12.9um 66.53999999999999um 13.1um
label IN2 center metal3
port IN2 make 7
box values 136.84um 14.9um 137.04um 15.1um
label ICTRL center metal3
port ICTRL make 8
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_vi_reference
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
ext2spice -o nrz_vi_reference_c.spice
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice extresist on
ext2spice -o nrz_vi_reference_rc.spice
quit -noprompt
