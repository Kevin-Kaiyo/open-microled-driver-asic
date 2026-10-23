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
 {INV1N nfet_03v3 1 0.28 4 20 GB DI VSS VSS}
 {INV1P pfet_03v3 2 0.28 10 20 GB DI VDD VDD}
 {INV2N nfet_03v3 1 0.28 16 20 GP GB VSS VSS}
 {INV2P pfet_03v3 2 0.28 22 20 GP GB VDD VDD}
 {LED nfet_03v3 1 0.28 28 20 OUT GP VX VSS}
 {DUMMY nfet_03v3 1 0.28 34 20 DUMMY GB VX VSS}
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
flatten -nolabels hs_steering_pvt
load hs_steering_pvt
rect metal3 3.5 22.3 10.5 22.7
rect metal3 27.1 2.0 45.74 2.4
box values 27.2um 2.1um 27.400000000000002um 2.3000000000000003um
label OUT center metal3
port make 2
rect metal3 7.0 3.2 22.9 3.6
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
rect metal3 33.1 6.8 34.1 7.2
box values 33.2um 6.9um 33.400000000000006um 7.1um
label DUMMY center metal3
port make 6
rect metal3 3.1 8.0 34.5 8.4
box values 3.2um 8.1um 3.4000000000000004um 8.299999999999999um
label GB center metal3
rect metal3 15.1 9.2 28.5 9.6
box values 15.2um 9.3um 15.399999999999999um 9.5um
label GP center metal3
rect metal3 27.9 10.4 39.74 10.8
box values 27.999999999999996um 10.5um 28.2um 10.7um
label VX center metal3
rect metal1 3.81 18.81 4.19 19.19
rect metal1 1.5 19.81 3.03 20.19
via metal1 metal2 via1 3.6 20
rect metal2 3.41 8.01 3.79 20.19
via metal2 metal3 via2 3.6 8.2
via metal1 metal2 via1 4 21.0
via metal2 metal3 via2 4 21.0
via metal3 metal4 via3 4 21.0
rect metal4 3.81 20.81 4.19 22.69
via metal3 metal4 via3 4 22.5
via metal1 metal2 via1 4.4 20
rect metal2 4.21 4.41 4.59 20.19
via metal2 metal3 via2 4.4 4.6
via metal1 metal2 via1 1.5 20
rect metal2 1.31 4.41 1.69 20.19
via metal2 metal3 via2 1.5 4.6
rect metal1 9.81 18.31 10.19 18.69
rect metal1 7.5 19.81 9.03 20.19
via metal1 metal2 via1 9.6 20
rect metal2 9.41 8.01 9.79 20.19
via metal2 metal3 via2 9.6 8.2
via metal1 metal2 via1 10 21.5
via metal2 metal3 via2 10 21.5
via metal3 metal4 via3 10 21.5
rect metal4 9.81 21.31 10.19 22.69
via metal3 metal4 via3 10 22.5
via metal1 metal2 via1 10.4 20
rect metal2 10.21 3.21 10.59 20.19
via metal2 metal3 via2 10.4 3.4
via metal1 metal2 via1 7.5 20
rect metal2 7.31 3.21 7.69 20.19
via metal2 metal3 via2 7.5 3.4
rect metal1 15.81 18.81 16.19 19.19
rect metal1 13.5 19.81 15.03 20.19
via metal1 metal2 via1 15.6 20
rect metal2 15.41 9.21 15.79 20.19
via metal2 metal3 via2 15.6 9.4
via metal1 metal2 via1 16 21.0
via metal2 metal3 via2 16 21.0
via metal3 metal4 via3 16 21.0
rect metal4 15.81 8.01 16.19 21.19
via metal3 metal4 via3 16 8.2
via metal1 metal2 via1 16.4 20
rect metal2 16.21 4.41 16.59 20.19
via metal2 metal3 via2 16.4 4.6
via metal1 metal2 via1 13.5 20
rect metal2 13.31 4.41 13.69 20.19
via metal2 metal3 via2 13.5 4.6
rect metal1 21.81 18.31 22.19 18.69
rect metal1 19.5 19.81 21.03 20.19
via metal1 metal2 via1 21.6 20
rect metal2 21.41 9.21 21.79 20.19
via metal2 metal3 via2 21.6 9.4
via metal1 metal2 via1 22 21.5
via metal2 metal3 via2 22 21.5
via metal3 metal4 via3 22 21.5
rect metal4 21.81 8.01 22.19 21.69
via metal3 metal4 via3 22 8.2
via metal1 metal2 via1 22.4 20
rect metal2 22.21 3.21 22.59 20.19
via metal2 metal3 via2 22.4 3.4
via metal1 metal2 via1 19.5 20
rect metal2 19.31 3.21 19.69 20.19
via metal2 metal3 via2 19.5 3.4
rect metal1 27.81 18.81 28.19 19.19
rect metal1 25.5 19.81 27.03 20.19
via metal1 metal2 via1 27.6 20
rect metal2 27.41 2.01 27.79 20.19
via metal2 metal3 via2 27.6 2.2
via metal1 metal2 via1 28 21.0
via metal2 metal3 via2 28 21.0
via metal3 metal4 via3 28 21.0
rect metal4 27.81 9.21 28.19 21.19
via metal3 metal4 via3 28 9.4
via metal1 metal2 via1 28.4 20
rect metal2 28.21 10.41 28.59 20.19
via metal2 metal3 via2 28.4 10.6
via metal1 metal2 via1 25.5 20
rect metal2 25.31 4.41 25.69 20.19
via metal2 metal3 via2 25.5 4.6
rect metal1 33.81 18.81 34.19 19.19
rect metal1 31.5 19.81 33.03 20.19
via metal1 metal2 via1 33.6 20
rect metal2 33.41 6.81 33.79 20.19
via metal2 metal3 via2 33.6 7.0
via metal1 metal2 via1 34 21.0
via metal2 metal3 via2 34 21.0
via metal3 metal4 via3 34 21.0
rect metal4 33.81 8.01 34.19 21.19
via metal3 metal4 via3 34 8.2
via metal1 metal2 via1 34.4 20
rect metal2 34.21 10.41 34.59 20.19
via metal2 metal3 via2 34.4 10.6
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
save hs_steering_pvt
extract all
ext2spice lvs
ext2spice
gds write hs_steering_pvt.gds
quit -noprompt
