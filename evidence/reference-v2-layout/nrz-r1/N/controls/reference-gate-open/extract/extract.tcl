gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/nrz-r1/N/controls/reference-gate-open/nrz_bias_power.gds
load nrz_bias_power
select top cell
box values 9.1um 0.9um 9.299999999999999um 1.1um
label VIN center metal3
port make 1
box values 86.10000000000001um 2.9um 86.3um 3.1um
label VSS center metal3
port make 2
box values 49.6um 4.9um 49.800000000000004um 5.1um
label VSET center metal3
port make 3
box values 71.60000000000001um 6.9um 71.8um 7.1um
label SENSE center metal3
port make 4
box values 194.34um 8.9um 194.54um 9.1um
label IOUT center metal3
port make 5
box values 279.59999999999997um 10.9um 279.8um 11.1um
label REGFB center metal3
port make 6
box values 380.34um 12.9um 380.54um 13.1um
label VREG center metal3
port make 7
box values 11.34um 14.9um 11.54um 15.1um
label IPB center metal3
port make 8
box values 66.34um 16.9um 66.53999999999999um 17.1um
label IN2 center metal3
port make 9
box values 136.84um 18.9um 137.04um 19.1um
label ICTRL center metal3
port make 10
box values 219.34um 20.9um 219.54um 21.1um
label LPB center metal3
port make 11
box values 274.34um 22.9um 274.54um 23.1um
label LN2 center metal3
port make 12
box values 344.84um 24.9um 345.04um 25.1um
label LCTRL center metal3
port make 13
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_bias_power
extract all
ext2spice lvs
ext2spice
quit -noprompt
