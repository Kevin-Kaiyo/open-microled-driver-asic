# Public GF180 PCells retained unchanged; independent project routing.
proc rect {layer x1 y1 x2 y2} {
 box values ${x1}um ${y1}um ${x2}um ${y2}um
 paint $layer
}
proc via {lo hi cut x y} {
 foreach layer [list $lo $hi] {
  rect $layer [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]
 }
 set h [expr {$cut eq "via1" ? .13 : .14}]
 rect $cut [expr {$x-$h}] [expr {$y-$h}] [expr {$x+$h}] [expr {$y+$h}]
}
set devices {
 {INV1N nfet_06v0 2.5 0.7 4 20 GB DI VSS VSS}
 {INV1P pfet_06v0 3.93 0.55 10 20 GB DI VDD VDD}
 {INV2N nfet_06v0 2.5 0.7 16 20 GP GB VSS VSS}
 {INV2P pfet_06v0 3.93 0.55 22 20 GP GB VDD VDD}
 {LED nfet_06v0 2.5 0.7 28 20 OUT GP VX VSS}
 {DUMMY nfet_06v0 2.5 0.7 34 20 DUMMY GB VX VSS}
 {TAIL nfet_03v3 5.76 1 40 20 VX BIAS VSS VSS}
 {BASE nfet_03v3 2 1 46 20 OUT BIAS VSS VSS}
 {REF nfet_03v3 2 1 52 20 BIAS BIAS VSS VSS}
}
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 load pcell_$name
 box values 0 0 0 0
 gf180mcu::${type}_draw [dict merge [gf180mcu::${type}_defaults] [dict create w $w l $l full_metal 0 gate_to_polycont .5]]
 save pcell_$name
}
load assembly
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 getcell pcell_$name child 0 0 parent ${cx}um ${cy}um
}
load pcell_RIN
box values 0 0 0 0
gf180mcu::ppolyf_u_1k_6p0_draw [dict merge [gf180mcu::ppolyf_u_1k_6p0_defaults] [dict create w 1 l 58 full_metal 1 gtc 1 gbc 1]]
save pcell_RIN
load assembly
getcell pcell_RIN child 0 0 parent -5.0um -6.93um
select top cell
flatten -nolabels hs_steering_robust
load hs_steering_robust
rect metal3 3.5 22.3 10.5 22.7
rect metal3 26.89 2.0 45.74 2.4
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port make 2
rect metal3 7.0 3.2 23.035 3.6
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
rect metal3 1.0 4.4 53.26 4.8
box values 1.0999999999999999um 4.5um 1.3um 4.699999999999999um
label VSS center metal3
port make 4
rect metal3 39.5 5.6 52.5 6.0
box values 39.6um 5.7um 39.800000000000004um 5.8999999999999995um
label BIAS center metal3
port make 5
rect metal3 32.89 6.8 33.89 7.2
box values 32.99um 6.9um 33.190000000000005um 7.1um
label DUMMY center metal3
port make 6
rect metal3 2.89 8.0 34.5 8.4
box values 2.99um 8.1um 3.1900000000000004um 8.299999999999999um
label GB center metal3
rect metal3 14.89 9.2 28.5 9.6
box values 14.99um 9.3um 15.19um 9.5um
label GP center metal3
rect metal3 28.11 10.4 39.74 10.8
box values 28.209999999999997um 10.5um 28.41um 10.7um
label VX center metal3
rect metal1 3.81 18.06 4.19 18.44
rect metal1 1.5 19.81 2.82 20.19
via metal1 metal2 via1 3.39 20
rect metal2 3.2 8.01 3.58 20.19
via metal2 metal3 via2 3.39 8.2
via metal1 metal2 via1 4 21.75
via metal2 metal3 via2 4 21.75
via metal3 metal4 via3 4 21.75
rect metal4 3.81 21.56 4.19 22.69
via metal3 metal4 via3 4 22.5
via metal1 metal2 via1 4.61 20
rect metal2 4.42 4.41 4.8 20.19
via metal2 metal3 via2 4.61 4.6
via metal1 metal2 via1 1.5 20
rect metal2 1.31 4.41 1.69 20.19
via metal2 metal3 via2 1.5 4.6
rect metal1 9.81 17.345 10.19 17.725
rect metal1 7.5 19.81 8.895 20.19
via metal1 metal2 via1 9.465 20
rect metal2 9.275 8.01 9.655 20.19
via metal2 metal3 via2 9.465 8.2
via metal1 metal2 via1 10 22.465
via metal2 metal3 via2 10 22.465
via metal3 metal4 via3 10 22.465
rect metal4 9.81 22.275 10.19 22.69
via metal3 metal4 via3 10 22.5
via metal1 metal2 via1 10.535 20
rect metal2 10.345 3.21 10.725 20.19
via metal2 metal3 via2 10.535 3.4
via metal1 metal2 via1 7.5 20
rect metal2 7.31 3.21 7.69 20.19
via metal2 metal3 via2 7.5 3.4
rect metal1 15.81 18.06 16.19 18.44
rect metal1 13.5 19.81 14.82 20.19
via metal1 metal2 via1 15.39 20
rect metal2 15.2 9.21 15.58 20.19
via metal2 metal3 via2 15.39 9.4
via metal1 metal2 via1 16 21.75
via metal2 metal3 via2 16 21.75
via metal3 metal4 via3 16 21.75
rect metal4 15.81 8.01 16.19 21.94
via metal3 metal4 via3 16 8.2
via metal1 metal2 via1 16.61 20
rect metal2 16.42 4.41 16.8 20.19
via metal2 metal3 via2 16.61 4.6
via metal1 metal2 via1 13.5 20
rect metal2 13.31 4.41 13.69 20.19
via metal2 metal3 via2 13.5 4.6
rect metal1 21.81 17.345 22.19 17.725
rect metal1 19.5 19.81 20.895 20.19
via metal1 metal2 via1 21.465 20
rect metal2 21.275 9.21 21.655 20.19
via metal2 metal3 via2 21.465 9.4
via metal1 metal2 via1 22 22.465
via metal2 metal3 via2 22 22.465
via metal3 metal4 via3 22 22.465
rect metal4 21.81 8.01 22.19 22.655
via metal3 metal4 via3 22 8.2
via metal1 metal2 via1 22.535 20
rect metal2 22.345 3.21 22.725 20.19
via metal2 metal3 via2 22.535 3.4
via metal1 metal2 via1 19.5 20
rect metal2 19.31 3.21 19.69 20.19
via metal2 metal3 via2 19.5 3.4
rect metal1 27.81 18.06 28.19 18.44
rect metal1 25.5 19.81 26.82 20.19
via metal1 metal2 via1 27.39 20
rect metal2 27.2 2.01 27.58 20.19
via metal2 metal3 via2 27.39 2.2
via metal1 metal2 via1 28 21.75
via metal2 metal3 via2 28 21.75
via metal3 metal4 via3 28 21.75
rect metal4 27.81 9.21 28.19 21.94
via metal3 metal4 via3 28 9.4
via metal1 metal2 via1 28.61 20
rect metal2 28.42 10.41 28.8 20.19
via metal2 metal3 via2 28.61 10.6
via metal1 metal2 via1 25.5 20
rect metal2 25.31 4.41 25.69 20.19
via metal2 metal3 via2 25.5 4.6
rect metal1 33.81 18.06 34.19 18.44
rect metal1 31.5 19.81 32.82 20.19
via metal1 metal2 via1 33.39 20
rect metal2 33.2 6.81 33.58 20.19
via metal2 metal3 via2 33.39 7.0
via metal1 metal2 via1 34 21.75
via metal2 metal3 via2 34 21.75
via metal3 metal4 via3 34 21.75
rect metal4 33.81 8.01 34.19 21.94
via metal3 metal4 via3 34 8.2
via metal1 metal2 via1 34.61 20
rect metal2 34.42 10.41 34.8 20.19
via metal2 metal3 via2 34.61 10.6
via metal1 metal2 via1 31.5 20
rect metal2 31.31 4.41 31.69 20.19
via metal2 metal3 via2 31.5 4.6
rect metal1 39.81 16.43 40.19 16.81
rect metal1 37.5 19.81 38.67 20.19
via metal1 metal2 via1 39.24 20
rect metal2 39.05 10.41 39.43 20.19
via metal2 metal3 via2 39.24 10.6
via metal1 metal2 via1 40 23.38
via metal2 metal3 via2 40 23.38
via metal3 metal4 via3 40 23.38
rect metal4 39.81 5.61 40.19 23.57
via metal3 metal4 via3 40 5.8
via metal1 metal2 via1 40.76 20
rect metal2 40.57 4.41 40.95 20.19
via metal2 metal3 via2 40.76 4.6
via metal1 metal2 via1 37.5 20
rect metal2 37.31 4.41 37.69 20.19
via metal2 metal3 via2 37.5 4.6
rect metal1 45.81 18.31 46.19 18.69
rect metal1 43.5 19.81 44.67 20.19
via metal1 metal2 via1 45.24 20
rect metal2 45.05 2.01 45.43 20.19
via metal2 metal3 via2 45.24 2.2
via metal1 metal2 via1 46 21.5
via metal2 metal3 via2 46 21.5
via metal3 metal4 via3 46 21.5
rect metal4 45.81 5.61 46.19 21.69
via metal3 metal4 via3 46 5.8
via metal1 metal2 via1 46.76 20
rect metal2 46.57 4.41 46.95 20.19
via metal2 metal3 via2 46.76 4.6
via metal1 metal2 via1 43.5 20
rect metal2 43.31 4.41 43.69 20.19
via metal2 metal3 via2 43.5 4.6
rect metal1 51.81 18.31 52.19 18.69
rect metal1 49.5 19.81 50.67 20.19
via metal1 metal2 via1 51.24 20
rect metal2 51.05 5.61 51.43 20.19
via metal2 metal3 via2 51.24 5.8
via metal1 metal2 via1 52 21.5
via metal2 metal3 via2 52 21.5
via metal3 metal4 via3 52 21.5
rect metal4 51.81 5.61 52.19 21.69
via metal3 metal4 via3 52 5.8
via metal1 metal2 via1 52.76 20
rect metal2 52.57 4.41 52.95 20.19
via metal2 metal3 via2 52.76 4.6
via metal1 metal2 via1 49.5 20
rect metal2 49.31 4.41 49.69 20.19
via metal2 metal3 via2 49.5 4.6
rect metal3 -5.5 22.3 10.5 22.7
rect metal3 -6.88 4.4 53.26 4.8
rect metal3 -5.5 -37.56 -4.5 -37.16
box values -5.4um -37.46um -5.2um -37.26um
label DATA center metal3
port make 1
box values 3.6um 22.4um 3.8um 22.6um
label DI center metal3
via metal1 metal2 via1 -5.0 -36.36
rect metal2 -5.19 -37.55 -4.81 -36.17
via metal2 metal3 via2 -5.0 -37.36
via metal1 metal2 via1 -5.0 22.5
rect metal2 -5.19 22.31 -4.81 22.69
via metal2 metal3 via2 -5.0 22.5
via metal1 metal2 via1 -6.38 -6.93
rect metal2 -6.57 -7.12 -6.19 4.79
via metal2 metal3 via2 -6.38 4.6
rect pwell -0.3 -38.48 0.3 29.12
rect psd -0.18 -38.36 0.18 29
rect psc -0.115 -38.295 0.115 28.935
rect metal1 -0.19 -38.295 0.19 28.935
rect metal2 -0.19 -38.295 0.19 28.935
via metal1 metal2 via1 0.0 -37.36
via metal1 metal2 via1 0.0 -32.36
via metal1 metal2 via1 0.0 -27.36
via metal1 metal2 via1 0.0 -22.36
via metal1 metal2 via1 0.0 -17.36
via metal1 metal2 via1 0.0 -12.36
via metal1 metal2 via1 0.0 -7.36
via metal1 metal2 via1 0.0 -2.36
via metal1 metal2 via1 0.0 2.64
via metal1 metal2 via1 0.0 7.64
via metal1 metal2 via1 0.0 12.64
via metal1 metal2 via1 0.0 17.64
via metal1 metal2 via1 0.0 22.64
via metal1 metal2 via1 0.0 27.64
via metal2 metal3 via2 0.0 4.6
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save hs_steering_robust
extract all
ext2spice lvs
ext2spice
gds write hs_steering_robust.gds
quit -noprompt
