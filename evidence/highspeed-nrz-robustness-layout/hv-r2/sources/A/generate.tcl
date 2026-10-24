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
 {N1 nfet_06v0 2.5 0.7 4 20 N1 DI VSS VSS}
 {P1 pfet_06v0 3.93 0.55 10 20 N1 DI VDD VDD}
 {N2 nfet_06v0 10 0.7 16 20 CTRL N1 VSS VSS}
 {P2 pfet_06v0 15.72 0.55 22 20 CTRL N1 VDD VDD}
 {NOUT nfet_06v0 10 0.7 28 20 OUT CTRL VL VSS}
 {POUT pfet_06v0 15.72 0.55 34 20 OUT CTRL VH VH}
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
gf180mcu::ppolyf_u_1k_6p0_draw [dict merge [gf180mcu::ppolyf_u_1k_6p0_defaults] [dict create w 1 l 48 full_metal 1 gtc 1 gbc 1]]
save pcell_RIN
load assembly
getcell pcell_RIN child 0 0 parent -5.0um -1.93um
select top cell
flatten -nolabels hs_voltage_robust
load hs_voltage_robust
rect metal3 3.5 22.3 10.5 22.7
rect metal3 26.89 2.0 33.965 2.4
box values 26.99um 2.1um 27.19um 2.3000000000000003um
label OUT center metal3
port make 2
rect metal3 7.0 3.2 23.035 3.6
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
rect metal3 31.0 4.4 35.035 4.8
box values 31.099999999999998um 4.5um 31.3um 4.699999999999999um
label VH center metal3
port make 4
rect metal3 28.11 5.6 29.11 6.0
box values 28.209999999999997um 5.7um 28.41um 5.8999999999999995um
label VL center metal3
port make 5
rect metal3 1.0 6.8 26.0 7.2
box values 1.0999999999999999um 6.9um 1.3um 7.1um
label VSS center metal3
port make 6
rect metal3 2.89 8.0 22.5 8.4
box values 2.99um 8.1um 3.1900000000000004um 8.299999999999999um
label N1 center metal3
rect metal3 14.89 9.2 34.5 9.6
box values 14.99um 9.3um 15.19um 9.5um
label CTRL center metal3
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
rect metal2 4.42 6.81 4.8 20.19
via metal2 metal3 via2 4.61 7.0
via metal1 metal2 via1 1.5 20
rect metal2 1.31 6.81 1.69 20.19
via metal2 metal3 via2 1.5 7.0
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
rect metal1 15.81 14.31 16.19 14.69
rect metal1 13.5 19.81 14.82 20.19
via metal1 metal2 via1 15.39 20
rect metal2 15.2 9.21 15.58 20.19
via metal2 metal3 via2 15.39 9.4
via metal1 metal2 via1 16 25.5
via metal2 metal3 via2 16 25.5
via metal3 metal4 via3 16 25.5
rect metal4 15.81 8.01 16.19 25.69
via metal3 metal4 via3 16 8.2
via metal1 metal2 via1 16.61 20
rect metal2 16.42 6.81 16.8 20.19
via metal2 metal3 via2 16.61 7.0
via metal1 metal2 via1 13.5 20
rect metal2 13.31 6.81 13.69 20.19
via metal2 metal3 via2 13.5 7.0
rect metal1 21.81 11.45 22.19 11.83
rect metal1 19.5 19.81 20.895 20.19
via metal1 metal2 via1 21.465 20
rect metal2 21.275 9.21 21.655 20.19
via metal2 metal3 via2 21.465 9.4
via metal1 metal2 via1 22 28.36
via metal2 metal3 via2 22 28.36
via metal3 metal4 via3 22 28.36
rect metal4 21.81 8.01 22.19 28.55
via metal3 metal4 via3 22 8.2
via metal1 metal2 via1 22.535 20
rect metal2 22.345 3.21 22.725 20.19
via metal2 metal3 via2 22.535 3.4
via metal1 metal2 via1 19.5 20
rect metal2 19.31 3.21 19.69 20.19
via metal2 metal3 via2 19.5 3.4
rect metal1 27.81 14.31 28.19 14.69
rect metal1 25.5 19.81 26.82 20.19
via metal1 metal2 via1 27.39 20
rect metal2 27.2 2.01 27.58 20.19
via metal2 metal3 via2 27.39 2.2
via metal1 metal2 via1 28 25.5
via metal2 metal3 via2 28 25.5
via metal3 metal4 via3 28 25.5
rect metal4 27.81 9.21 28.19 25.69
via metal3 metal4 via3 28 9.4
via metal1 metal2 via1 28.61 20
rect metal2 28.42 5.61 28.8 20.19
via metal2 metal3 via2 28.61 5.8
via metal1 metal2 via1 25.5 20
rect metal2 25.31 6.81 25.69 20.19
via metal2 metal3 via2 25.5 7.0
rect metal1 33.81 11.45 34.19 11.83
rect metal1 31.5 19.81 32.895 20.19
via metal1 metal2 via1 33.465 20
rect metal2 33.275 2.01 33.655 20.19
via metal2 metal3 via2 33.465 2.2
via metal1 metal2 via1 34 28.36
via metal2 metal3 via2 34 28.36
via metal3 metal4 via3 34 28.36
rect metal4 33.81 9.21 34.19 28.55
via metal3 metal4 via3 34 9.4
via metal1 metal2 via1 34.535 20
rect metal2 34.345 4.41 34.725 20.19
via metal2 metal3 via2 34.535 4.6
via metal1 metal2 via1 31.5 20
rect metal2 31.31 4.41 31.69 20.19
via metal2 metal3 via2 31.5 4.6
rect metal3 -5.5 22.3 10.5 22.7
rect metal3 -6.88 6.8 26.0 7.2
rect metal3 -5.5 -27.56 -4.5 -27.16
box values -5.4um -27.46um -5.2um -27.259999999999998um
label DATA center metal3
port make 1
box values 3.6um 22.4um 3.8um 22.6um
label DI center metal3
via metal1 metal2 via1 -5.0 -26.36
rect metal2 -5.19 -27.55 -4.81 -26.17
via metal2 metal3 via2 -5.0 -27.36
via metal1 metal2 via1 -5.0 22.5
rect metal2 -5.19 22.31 -4.81 22.69
via metal2 metal3 via2 -5.0 22.5
via metal1 metal2 via1 -6.38 -1.93
rect metal2 -6.57 -2.12 -6.19 7.19
via metal2 metal3 via2 -6.38 7.0
rect pwell -0.3 -28.48 0.3 29.12
rect psd -0.18 -28.36 0.18 29
rect psc -0.115 -28.295 0.115 28.935
rect metal1 -0.19 -28.295 0.19 28.935
rect metal2 -0.19 -28.295 0.19 28.935
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
via metal2 metal3 via2 0.0 7.0
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save hs_voltage_robust
extract all
ext2spice lvs
ext2spice
gds write hs_voltage_robust.gds
quit -noprompt
