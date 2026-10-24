gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/vi-clamped-pg-r1b/V/controls/supply-vss-short/nrz_vi_reference.gds
load nrz_vi_reference
select top cell
foreach name {VIN VSS VSET SENSE IOUT IPB IN2 ICTRL DISABLE} {
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
box values 221.6um 16.9um 221.79999999999998um 17.1um
label DISABLE center metal3
port DISABLE make 9
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_vi_reference
extract all
ext2spice lvs
ext2spice
quit -noprompt
