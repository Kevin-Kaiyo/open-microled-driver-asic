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
 {IPBIAS pfet_06v0 20 4 14.0 110.0 IPB IPB VIN VIN}
 {IPTAIL pfet_06v0 20 4 32.0 110.0 ITAIL IPB VIN VIN}
 {IPD1 pfet_06v0 100 10 50.0 150.0 IN1 VSET ITAIL VIN}
 {IPD2 pfet_06v0 100 10 72.0 150.0 IN2 SENSE ITAIL VIN}
 {IND1 nfet_06v0 50 10 94.0 125.0 IN1 IN1 VSS VSS}
 {IND2 nfet_06v0 50 10 116.0 125.0 IN2 IN1 VSS VSS}
 {INSTAGE nfet_06v0 20 1 138.0 110.0 ICTRL IN2 VSS VSS}
 {IPLOAD pfet_06v0 100 10 156.0 150.0 ICTRL ICTRL VIN VIN}
 {IPREG pfet_06v0 100 10 178.0 150.0 SENSE ICTRL VIN VIN}
 {IPOUT pfet_06v0 100 10 200.0 150.0 IOUT ICTRL VIN VIN}
}
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 load pcell_$name
 box values 0 0 0 0
 gf180mcu::${type}_draw [dict merge [gf180mcu::${type}_defaults] [dict create w $w l $l full_metal 0 gate_to_polycont .5 gtc [expr {$type eq "nfet_06v0" ? 1 : 0}] gbc [expr {$type eq "nfet_06v0" ? 1 : 0}]]]
 save pcell_$name
}
load assembly
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 getcell pcell_$name child 0 0 parent ${cx}um ${cy}um
}
select top cell
flatten -nolabels nrz_vi_reference
load nrz_vi_reference
rect metal3 9.0 0.8 205.76 1.2
box values 9.1um 0.9um 9.299999999999999um 1.1um
label VIN center metal3
port make 1
rect metal3 86.0 2.8 139.26 3.2
box values 86.10000000000001um 2.9um 86.3um 3.1um
label VSS center metal3
port make 2
rect metal3 49.5 4.8 50.5 5.2
box values 49.6um 4.9um 49.800000000000004um 5.1um
label VSET center metal3
port make 3
rect metal3 71.5 6.8 173.24 7.2
box values 71.60000000000001um 6.9um 71.8um 7.1um
label SENSE center metal3
port make 4
rect metal3 194.24 8.8 195.24 9.2
box values 194.34um 8.9um 194.54um 9.1um
label IOUT center metal3
port make 5
rect metal3 11.24 10.8 32.5 11.2
box values 11.34um 10.9um 11.54um 11.1um
label IPB center metal3
port make 6
rect metal3 66.24 12.8 138.5 13.2
box values 66.34um 12.9um 66.53999999999999um 13.1um
label IN2 center metal3
port make 7
rect metal3 136.74 14.8 200.5 15.2
box values 136.84um 14.9um 137.04um 15.1um
label ICTRL center metal3
port make 8
rect metal3 29.24 16.8 77.76 17.2
box values 29.34um 16.9um 29.540000000000003um 17.1um
label ITAIL center metal3
rect metal3 44.24 18.8 116.5 19.2
box values 44.34um 18.9um 44.540000000000006um 19.1um
label IN1 center metal3
rect metal1 13.81 99.31 14.19 99.69
rect metal1 9.5 109.81 11.17 110.19
via metal1 metal2 via1 11.74 110.0
rect metal2 11.55 10.81 11.93 110.19
via metal2 metal3 via2 11.74 11
via metal1 metal2 via1 14.0 120.5
via metal2 metal3 via2 14.0 120.5
via metal3 metal4 via3 14.0 120.5
rect metal4 13.81 10.81 14.19 120.69
via metal3 metal4 via3 14.0 11
via metal1 metal2 via1 16.259999999999998 110.0
rect metal2 16.07 0.81 16.45 110.19
via metal2 metal3 via2 16.259999999999998 1
via metal1 metal2 via1 9.5 110.0
rect metal2 9.31 0.81 9.69 110.19
via metal2 metal3 via2 9.5 1
rect metal1 31.81 99.31 32.19 99.69
rect metal1 27.5 109.81 29.17 110.19
via metal1 metal2 via1 29.740000000000002 110.0
rect metal2 29.55 16.81 29.93 110.19
via metal2 metal3 via2 29.740000000000002 17
via metal1 metal2 via1 32.0 120.5
via metal2 metal3 via2 32.0 120.5
via metal3 metal4 via3 32.0 120.5
rect metal4 31.81 10.81 32.19 120.69
via metal3 metal4 via3 32.0 11
via metal1 metal2 via1 34.26 110.0
rect metal2 34.07 0.81 34.45 110.19
via metal2 metal3 via2 34.26 1
via metal1 metal2 via1 27.5 110.0
rect metal2 27.31 0.81 27.69 110.19
via metal2 metal3 via2 27.5 1
rect metal1 49.81 99.31 50.19 99.69
rect metal1 42.5 149.81 44.17 150.19
via metal1 metal2 via1 44.74 150.0
rect metal2 44.55 18.81 44.93 150.19
via metal2 metal3 via2 44.74 19
via metal1 metal2 via1 50.0 200.5
via metal2 metal3 via2 50.0 200.5
via metal3 metal4 via3 50.0 200.5
rect metal4 49.81 4.81 50.19 200.69
via metal3 metal4 via3 50.0 5
via metal1 metal2 via1 55.26 150.0
rect metal2 55.07 16.81 55.45 150.19
via metal2 metal3 via2 55.26 17
via metal1 metal2 via1 42.5 150.0
rect metal2 42.31 0.81 42.69 150.19
via metal2 metal3 via2 42.5 1
rect metal1 71.81 99.31 72.19 99.69
rect metal1 64.5 149.81 66.17 150.19
via metal1 metal2 via1 66.74 150.0
rect metal2 66.55 12.81 66.93 150.19
via metal2 metal3 via2 66.74 13
via metal1 metal2 via1 72.0 200.5
via metal2 metal3 via2 72.0 200.5
via metal3 metal4 via3 72.0 200.5
rect metal4 71.81 6.81 72.19 200.69
via metal3 metal4 via3 72.0 7
via metal1 metal2 via1 77.26 150.0
rect metal2 77.07 16.81 77.45 150.19
via metal2 metal3 via2 77.26 17
via metal1 metal2 via1 64.5 150.0
rect metal2 64.31 0.81 64.69 150.19
via metal2 metal3 via2 64.5 1
rect metal1 93.81 99.31 94.19 99.69
rect metal1 86.5 124.81 88.17 125.19
via metal1 metal2 via1 88.74 125.0
rect metal2 88.55 18.81 88.93 125.19
via metal2 metal3 via2 88.74 19
via metal1 metal2 via1 94.0 150.5
via metal2 metal3 via2 94.0 150.5
via metal3 metal4 via3 94.0 150.5
rect metal4 93.81 18.81 94.19 150.69
via metal3 metal4 via3 94.0 19
via metal1 metal2 via1 99.26 125.0
rect metal2 99.07 2.81 99.45 125.19
via metal2 metal3 via2 99.26 3
via metal1 metal2 via1 86.5 125.0
rect metal2 86.31 2.81 86.69 125.19
via metal2 metal3 via2 86.5 3
rect metal1 115.81 99.31 116.19 99.69
rect metal1 108.5 124.81 110.17 125.19
via metal1 metal2 via1 110.74 125.0
rect metal2 110.55 12.81 110.93 125.19
via metal2 metal3 via2 110.74 13
via metal1 metal2 via1 116.0 150.5
via metal2 metal3 via2 116.0 150.5
via metal3 metal4 via3 116.0 150.5
rect metal4 115.81 18.81 116.19 150.69
via metal3 metal4 via3 116.0 19
via metal1 metal2 via1 121.26 125.0
rect metal2 121.07 2.81 121.45 125.19
via metal2 metal3 via2 121.26 3
via metal1 metal2 via1 108.5 125.0
rect metal2 108.31 2.81 108.69 125.19
via metal2 metal3 via2 108.5 3
rect metal1 137.81 99.31 138.19 99.69
rect metal1 134.5 109.81 136.67 110.19
via metal1 metal2 via1 137.24 110.0
rect metal2 137.05 14.81 137.43 110.19
via metal2 metal3 via2 137.24 15
via metal1 metal2 via1 138.0 120.5
via metal2 metal3 via2 138.0 120.5
via metal3 metal4 via3 138.0 120.5
rect metal4 137.81 12.81 138.19 120.69
via metal3 metal4 via3 138.0 13
via metal1 metal2 via1 138.76 110.0
rect metal2 138.57 2.81 138.95 110.19
via metal2 metal3 via2 138.76 3
via metal1 metal2 via1 134.5 110.0
rect metal2 134.31 2.81 134.69 110.19
via metal2 metal3 via2 134.5 3
rect metal1 155.81 99.31 156.19 99.69
rect metal1 148.5 149.81 150.17 150.19
via metal1 metal2 via1 150.74 150.0
rect metal2 150.55 14.81 150.93 150.19
via metal2 metal3 via2 150.74 15
via metal1 metal2 via1 156.0 200.5
via metal2 metal3 via2 156.0 200.5
via metal3 metal4 via3 156.0 200.5
rect metal4 155.81 14.81 156.19 200.69
via metal3 metal4 via3 156.0 15
via metal1 metal2 via1 161.26 150.0
rect metal2 161.07 0.81 161.45 150.19
via metal2 metal3 via2 161.26 1
via metal1 metal2 via1 148.5 150.0
rect metal2 148.31 0.81 148.69 150.19
via metal2 metal3 via2 148.5 1
rect metal1 177.81 99.31 178.19 99.69
rect metal1 170.5 149.81 172.17 150.19
via metal1 metal2 via1 172.74 150.0
rect metal2 172.55 6.81 172.93 150.19
via metal2 metal3 via2 172.74 7
via metal1 metal2 via1 178.0 200.5
via metal2 metal3 via2 178.0 200.5
via metal3 metal4 via3 178.0 200.5
rect metal4 177.81 14.81 178.19 200.69
via metal3 metal4 via3 178.0 15
via metal1 metal2 via1 183.26 150.0
rect metal2 183.07 0.81 183.45 150.19
via metal2 metal3 via2 183.26 1
via metal1 metal2 via1 170.5 150.0
rect metal2 170.31 0.81 170.69 150.19
via metal2 metal3 via2 170.5 1
rect metal1 199.81 99.31 200.19 99.69
rect metal1 192.5 149.81 194.17 150.19
via metal1 metal2 via1 194.74 150.0
rect metal2 194.55 8.81 194.93 150.19
via metal2 metal3 via2 194.74 9
via metal1 metal2 via1 200.0 200.5
via metal2 metal3 via2 200.0 200.5
via metal3 metal4 via3 200.0 200.5
rect metal4 199.81 14.81 200.19 200.69
via metal3 metal4 via3 200.0 15
via metal1 metal2 via1 205.26 150.0
rect metal2 205.07 0.81 205.45 150.19
via metal2 metal3 via2 205.26 1
via metal1 metal2 via1 192.5 150.0
rect metal2 192.31 0.81 192.69 150.19
via metal2 metal3 via2 192.5 1
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_vi_reference
extract all
ext2spice lvs
ext2spice
gds write nrz_vi_reference.gds
quit -noprompt
