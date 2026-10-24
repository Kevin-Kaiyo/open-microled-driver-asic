gds read /Users/kimmy/Projects/open-microled-driver-asic/build/highspeed-nrz-robustness-layout/hv-r2/B/controls/input-gate-open/hs_steering_robust.gds
load hs_steering_robust
select top cell
box values -5.3999999999999995um -37.46um -5.2um -37.26um
label DATA center metal3
port make 1
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port make 2
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
box values 1.0999999999999999um 4.5um 1.3um 4.699999999999999um
label VSS center metal3
port make 4
box values 39.6um 5.7um 39.800000000000004um 5.8999999999999995um
label BIAS center metal3
port make 5
box values 32.99um 6.9um 33.190000000000005um 7.1um
label DUMMY center metal3
port make 6
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save hs_steering_robust
extract all
ext2spice lvs
ext2spice
quit -noprompt
