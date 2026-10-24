gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/nrz-joint-r1c/J/controls/reference-gate-open/nrz_reference_integrated.gds
load nrz_reference_integrated
select top cell
foreach name {DATA OUT VDD VSS BIAS DUMMY VIN VSET SENSE IPB IN2 ICTRL DISABLE} {
 while {[port $name exists -quiet]} {port $name remove -quiet}
}
box values -5.3999999999999995um -37.46um -5.2um -37.26um
label DATA center metal3
port DATA make 1
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port OUT make 2
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port VDD make 3
box values 186.1um 102.9um 186.29999999999998um 103.1um
label VSS center metal3
port VSS make 4
box values 294.34um 108.9um 294.54um 109.1um
label BIAS center metal3
port BIAS make 5
box values 32.99um 6.9um 33.190000000000005um 7.1um
label DUMMY center metal3
port DUMMY make 6
box values 109.10000000000001um 100.9um 109.3um 101.1um
label VIN center metal3
port VIN make 7
box values 149.6um 104.9um 149.79999999999998um 105.1um
label VSET center metal3
port VSET make 8
box values 171.6um 106.9um 171.79999999999998um 107.1um
label SENSE center metal3
port SENSE make 9
box values 111.34um 110.9um 111.53999999999999um 111.1um
label IPB center metal3
port IPB make 10
box values 166.34um 112.9um 166.54um 113.1um
label IN2 center metal3
port IN2 make 11
box values 236.84um 114.9um 237.04um 115.1um
label ICTRL center metal3
port ICTRL make 12
box values 321.59999999999997um 116.9um 321.8um 117.1um
label DISABLE center metal3
port DISABLE make 13
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_reference_integrated
extract all
ext2spice lvs
ext2spice
quit -noprompt
