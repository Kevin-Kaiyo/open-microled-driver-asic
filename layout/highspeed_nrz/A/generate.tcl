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
 {N1 nfet_03v3 1 0.28 4 20 N1 DATA VSS VSS}
 {P1 pfet_03v3 2 0.28 10 20 N1 DATA VDD VDD}
 {N2 nfet_03v3 4 0.28 16 20 CTRL N1 VSS VSS}
 {P2 pfet_03v3 8 0.28 22 20 CTRL N1 VDD VDD}
 {NOUT nfet_03v3 4 0.28 28 20 OUT CTRL VL VSS}
 {POUT pfet_03v3 8 0.28 34 20 OUT CTRL VH VH}
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
select top cell
flatten -nolabels hs_nrz_voltage_core
load hs_nrz_voltage_core
rect metal3 3.5 0.8 10.5 1.2
box values 3.6um 0.9um 3.8000000000000003um 1.1um
label DATA center metal3
port make 1
rect metal3 27.1 2.0 34.1 2.4
box values 27.2um 2.1um 27.400000000000002um 2.3000000000000003um
label OUT center metal3
port make 2
rect metal3 7.0 3.2 22.9 3.6
box values 7.1000000000000005um 3.3um 7.3um 3.5um
label VDD center metal3
port make 3
rect metal3 31.0 4.4 34.9 4.8
box values 31.099999999999998um 4.5um 31.3um 4.699999999999999um
label VH center metal3
port make 4
rect metal3 27.9 5.6 28.9 6.0
box values 27.999999999999996um 5.7um 28.2um 5.8999999999999995um
label VL center metal3
port make 5
rect metal3 1.0 6.8 26.0 7.2
box values 1.0999999999999999um 6.9um 1.3um 7.1um
label VSS center metal3
port make 6
rect metal3 3.1 8.0 22.5 8.4
box values 3.2um 8.1um 3.4000000000000004um 8.299999999999999um
label N1 center metal3
rect metal3 15.1 9.2 34.5 9.6
box values 15.2um 9.3um 15.399999999999999um 9.5um
label CTRL center metal3
rect metal1 3.81 18.81 4.19 19.19
rect metal1 1.5 19.81 3.03 20.19
via metal1 metal2 via1 3.6 20
rect metal2 3.41 8.01 3.79 20.19
via metal2 metal3 via2 3.6 8.2
via metal1 metal2 via1 4 21.0
via metal2 metal3 via2 4 21.0
via metal3 metal4 via3 4 21.0
rect metal4 3.81 0.81 4.19 21.19
via metal3 metal4 via3 4 1.0
via metal1 metal2 via1 4.4 20
rect metal2 4.21 6.81 4.59 20.19
via metal2 metal3 via2 4.4 7.0
via metal1 metal2 via1 1.5 20
rect metal2 1.31 6.81 1.69 20.19
via metal2 metal3 via2 1.5 7.0
rect metal1 9.81 18.31 10.19 18.69
rect metal1 7.5 19.81 9.03 20.19
via metal1 metal2 via1 9.6 20
rect metal2 9.41 8.01 9.79 20.19
via metal2 metal3 via2 9.6 8.2
via metal1 metal2 via1 10 21.5
via metal2 metal3 via2 10 21.5
via metal3 metal4 via3 10 21.5
rect metal4 9.81 0.81 10.19 21.69
via metal3 metal4 via3 10 1.0
via metal1 metal2 via1 10.4 20
rect metal2 10.21 3.21 10.59 20.19
via metal2 metal3 via2 10.4 3.4
via metal1 metal2 via1 7.5 20
rect metal2 7.31 3.21 7.69 20.19
via metal2 metal3 via2 7.5 3.4
rect metal1 15.81 17.31 16.19 17.69
rect metal1 13.5 19.81 15.03 20.19
via metal1 metal2 via1 15.6 20
rect metal2 15.41 9.21 15.79 20.19
via metal2 metal3 via2 15.6 9.4
via metal1 metal2 via1 16 22.5
via metal2 metal3 via2 16 22.5
via metal3 metal4 via3 16 22.5
rect metal4 15.81 8.01 16.19 22.69
via metal3 metal4 via3 16 8.2
via metal1 metal2 via1 16.4 20
rect metal2 16.21 6.81 16.59 20.19
via metal2 metal3 via2 16.4 7.0
via metal1 metal2 via1 13.5 20
rect metal2 13.31 6.81 13.69 20.19
via metal2 metal3 via2 13.5 7.0
rect metal1 21.81 15.31 22.19 15.69
rect metal1 19.5 19.81 21.03 20.19
via metal1 metal2 via1 21.6 20
rect metal2 21.41 9.21 21.79 20.19
via metal2 metal3 via2 21.6 9.4
via metal1 metal2 via1 22 24.5
via metal2 metal3 via2 22 24.5
via metal3 metal4 via3 22 24.5
rect metal4 21.81 8.01 22.19 24.69
via metal3 metal4 via3 22 8.2
via metal1 metal2 via1 22.4 20
rect metal2 22.21 3.21 22.59 20.19
via metal2 metal3 via2 22.4 3.4
via metal1 metal2 via1 19.5 20
rect metal2 19.31 3.21 19.69 20.19
via metal2 metal3 via2 19.5 3.4
rect metal1 27.81 17.31 28.19 17.69
rect metal1 25.5 19.81 27.03 20.19
via metal1 metal2 via1 27.6 20
rect metal2 27.41 2.01 27.79 20.19
via metal2 metal3 via2 27.6 2.2
via metal1 metal2 via1 28 22.5
via metal2 metal3 via2 28 22.5
via metal3 metal4 via3 28 22.5
rect metal4 27.81 9.21 28.19 22.69
via metal3 metal4 via3 28 9.4
via metal1 metal2 via1 28.4 20
rect metal2 28.21 5.61 28.59 20.19
via metal2 metal3 via2 28.4 5.8
via metal1 metal2 via1 25.5 20
rect metal2 25.31 6.81 25.69 20.19
via metal2 metal3 via2 25.5 7.0
rect metal1 33.81 15.31 34.19 15.69
rect metal1 31.5 19.81 33.03 20.19
via metal1 metal2 via1 33.6 20
rect metal2 33.41 2.01 33.79 20.19
via metal2 metal3 via2 33.6 2.2
via metal1 metal2 via1 34 24.5
via metal2 metal3 via2 34 24.5
via metal3 metal4 via3 34 24.5
rect metal4 33.81 9.21 34.19 24.69
via metal3 metal4 via3 34 9.4
via metal1 metal2 via1 34.4 20
rect metal2 34.21 4.41 34.59 20.19
via metal2 metal3 via2 34.4 4.6
via metal1 metal2 via1 31.5 20
rect metal2 31.31 4.41 31.69 20.19
via metal2 metal3 via2 31.5 4.6
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save hs_nrz_voltage_core
extract all
ext2spice lvs
ext2spice
gds write hs_nrz_voltage_core.gds
quit -noprompt
