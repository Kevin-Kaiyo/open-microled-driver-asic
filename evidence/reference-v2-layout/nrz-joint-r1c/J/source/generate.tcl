proc rect {layer x1 y1 x2 y2} {
box values ${x1}um ${y1}um ${x2}um ${y2}um
paint $layer
}
proc via3at {x y} {
rect metal3 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]
rect metal4 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]
rect via3 [expr {$x-.14}] [expr {$y-.14}] [expr {$x+.14}] [expr {$y+.14}]
}
proc via4at {x y} {
rect metal4 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]
rect metal5 [expr {$x-.5}] [expr {$y-.5}] [expr {$x+.5}] [expr {$y+.5}]
rect via4 [expr {$x-.14}] [expr {$y-.14}] [expr {$x+.14}] [expr {$y+.14}]
}
gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/nrz-joint-r1c/J/source/C.gds
gds read /Users/kimmy/Projects/open-microled-driver-asic/build/reference-v2-layout/nrz-joint-r1c/J/source/R.gds
load reference_joint_assembly
getcell hs_steering_robust child 0 0 parent 0um 0um
getcell nrz_vi_reference child 0 0 parent 100um 100um
select top cell
flatten -nolabels nrz_reference_integrated
load nrz_reference_integrated
rect metal3 39.2 5.609999999999999 40.8 5.99
rect metal4 39.2 5.609999999999999 40.8 60.19
via3at 39.4 5.8
via4at 39.4 60
via3at 40.0 5.8
via4at 40.0 60
via3at 40.6 5.8
via4at 40.6 60
rect metal3 293.64 108.81 295.24 109.19
rect metal4 293.64 59.81 295.24 109.19
via3at 293.84 109
via4at 293.84 60
via3at 294.44 109
via4at 294.44 60
via3at 295.04 109
via4at 295.04 60
rect metal5 37.0 57.0 297.44 63.0
rect metal3 0.3999999999999999 4.409999999999999 2.0 4.79
rect metal4 0.3999999999999999 4.409999999999999 2.0 80.19
via3at 0.6 4.6
via4at 0.6 80
via3at 1.2 4.6
via4at 1.2 80
via3at 1.7999999999999998 4.6
via4at 1.7999999999999998 80
rect metal3 185.39999999999998 102.81 187.0 103.19
rect metal4 185.39999999999998 79.81 187.0 103.19
via3at 185.6 103
via4at 185.6 80
via3at 186.2 103
via4at 186.2 80
via3at 186.79999999999998 103
via4at 186.79999999999998 80
rect metal5 -1.8 77.0 189.2 83.0
box values -5.3999999999999995um 22.4um -5.2um 22.6um
label DI center metal3
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port make 2
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
box values 186.1um 102.9um 186.29999999999998um 103.1um
label VSS center metal3
port make 4
box values 294.34um 108.9um 294.54um 109.1um
label BIAS center metal3
port make 5
box values 32.99um 6.9um 33.190000000000005um 7.1um
label DUMMY center metal3
port make 6
box values 2.99um 8.1um 3.1900000000000004um 8.299999999999999um
label GB center metal3
box values 14.99um 9.3um 15.19um 9.5um
label GP center metal3
box values 28.209999999999997um 10.5um 28.41um 10.7um
label VX center metal3
box values -5.3999999999999995um -37.46um -5.2um -37.26um
label DATA center metal3
port make 1
box values 109.10000000000001um 100.9um 109.3um 101.1um
label VIN center metal3
port make 7
box values 149.6um 104.9um 149.79999999999998um 105.1um
label VSET center metal3
port make 8
box values 171.6um 106.9um 171.79999999999998um 107.1um
label SENSE center metal3
port make 9
box values 111.34um 110.9um 111.53999999999999um 111.1um
label IPB center metal3
port make 10
box values 166.34um 112.9um 166.54um 113.1um
label IN2 center metal3
port make 11
box values 236.84um 114.9um 237.04um 115.1um
label ICTRL center metal3
port make 12
box values 321.59999999999997um 116.9um 321.8um 117.1um
label DISABLE center metal3
port make 13
box values 129.34um 118.9um 129.54um 119.1um
label ITAIL center metal3
box values 144.34um 120.9um 144.54um 121.1um
label IN1 center metal3
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_reference_integrated
extract all
ext2spice lvs
ext2spice
gds write nrz_reference_integrated.gds
quit -noprompt
