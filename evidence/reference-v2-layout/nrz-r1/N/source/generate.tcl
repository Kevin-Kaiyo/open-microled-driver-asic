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
 {LPBIAS pfet_06v0 20 4 222.0 110.0 LPB LPB VIN VIN}
 {LPTAIL pfet_06v0 20 4 240.0 110.0 LTAIL LPB VIN VIN}
 {LPD1 pfet_06v0 100 10 258.0 150.0 LN1 VSET LTAIL VIN}
 {LPD2 pfet_06v0 100 10 280.0 150.0 LN2 REGFB LTAIL VIN}
 {LND1 nfet_06v0 50 10 302.0 125.0 LN1 LN1 VSS VSS}
 {LND2 nfet_06v0 50 10 324.0 125.0 LN2 LN1 VSS VSS}
 {LNSTAGE nfet_06v0 20 1 346.0 110.0 LCTRL LN2 VSS VSS}
 {LPLOAD pfet_06v0 100 10 364.0 150.0 LCTRL LCTRL VIN VIN}
 {LPREG pfet_06v0 100 10 386.0 150.0 VREG LCTRL VIN VIN}
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
flatten -nolabels nrz_bias_power
load nrz_bias_power
rect metal3 9.0 0.8 391.76 1.2
box values 9.1um 0.9um 9.299999999999999um 1.1um
label VIN center metal3
port make 1
rect metal3 86.0 2.8 347.26 3.2
box values 86.10000000000001um 2.9um 86.3um 3.1um
label VSS center metal3
port make 2
rect metal3 49.5 4.8 258.5 5.2
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
rect metal3 279.5 10.8 280.5 11.2
box values 279.59999999999997um 10.9um 279.8um 11.1um
label REGFB center metal3
port make 6
rect metal3 380.24 12.8 381.24 13.2
box values 380.34um 12.9um 380.54um 13.1um
label VREG center metal3
port make 7
rect metal3 11.24 14.8 32.5 15.2
box values 11.34um 14.9um 11.54um 15.1um
label IPB center metal3
port make 8
rect metal3 66.24 16.8 138.5 17.2
box values 66.34um 16.9um 66.53999999999999um 17.1um
label IN2 center metal3
port make 9
rect metal3 136.74 18.8 200.5 19.2
box values 136.84um 18.9um 137.04um 19.1um
label ICTRL center metal3
port make 10
rect metal3 219.24 20.8 240.5 21.2
box values 219.34um 20.9um 219.54um 21.1um
label LPB center metal3
port make 11
rect metal3 274.24 22.8 346.5 23.2
box values 274.34um 22.9um 274.54um 23.1um
label LN2 center metal3
port make 12
rect metal3 344.74 24.8 386.5 25.2
box values 344.84um 24.9um 345.04um 25.1um
label LCTRL center metal3
port make 13
rect metal3 29.24 26.8 77.76 27.2
box values 29.34um 26.9um 29.540000000000003um 27.1um
label ITAIL center metal3
rect metal3 44.24 28.8 116.5 29.2
box values 44.34um 28.9um 44.540000000000006um 29.1um
label IN1 center metal3
rect metal3 237.24 30.8 285.76 31.2
box values 237.34um 30.9um 237.54um 31.1um
label LTAIL center metal3
rect metal3 252.24 32.8 324.5 33.2
box values 252.34um 32.9um 252.54um 33.1um
label LN1 center metal3
rect metal1 13.81 99.31 14.19 99.69
rect metal1 9.5 109.81 11.17 110.19
via metal1 metal2 via1 11.74 110.0
rect metal2 11.55 14.81 11.93 110.19
via metal2 metal3 via2 11.74 15
via metal1 metal2 via1 14.0 120.5
via metal2 metal3 via2 14.0 120.5
via metal3 metal4 via3 14.0 120.5
rect metal4 13.81 14.81 14.19 120.69
via metal3 metal4 via3 14.0 15
via metal1 metal2 via1 16.259999999999998 110.0
rect metal2 16.07 0.81 16.45 110.19
via metal2 metal3 via2 16.259999999999998 1
via metal1 metal2 via1 9.5 110.0
rect metal2 9.31 0.81 9.69 110.19
via metal2 metal3 via2 9.5 1
rect metal1 31.81 99.31 32.19 99.69
rect metal1 27.5 109.81 29.17 110.19
via metal1 metal2 via1 29.740000000000002 110.0
rect metal2 29.55 26.81 29.93 110.19
via metal2 metal3 via2 29.740000000000002 27
via metal1 metal2 via1 32.0 120.5
via metal2 metal3 via2 32.0 120.5
via metal3 metal4 via3 32.0 120.5
rect metal4 31.81 14.81 32.19 120.69
via metal3 metal4 via3 32.0 15
via metal1 metal2 via1 34.26 110.0
rect metal2 34.07 0.81 34.45 110.19
via metal2 metal3 via2 34.26 1
via metal1 metal2 via1 27.5 110.0
rect metal2 27.31 0.81 27.69 110.19
via metal2 metal3 via2 27.5 1
rect metal1 49.81 99.31 50.19 99.69
rect metal1 42.5 149.81 44.17 150.19
via metal1 metal2 via1 44.74 150.0
rect metal2 44.55 28.81 44.93 150.19
via metal2 metal3 via2 44.74 29
via metal1 metal2 via1 50.0 200.5
via metal2 metal3 via2 50.0 200.5
via metal3 metal4 via3 50.0 200.5
rect metal4 49.81 4.81 50.19 200.69
via metal3 metal4 via3 50.0 5
via metal1 metal2 via1 55.26 150.0
rect metal2 55.07 26.81 55.45 150.19
via metal2 metal3 via2 55.26 27
via metal1 metal2 via1 42.5 150.0
rect metal2 42.31 0.81 42.69 150.19
via metal2 metal3 via2 42.5 1
rect metal1 71.81 99.31 72.19 99.69
rect metal1 64.5 149.81 66.17 150.19
via metal1 metal2 via1 66.74 150.0
rect metal2 66.55 16.81 66.93 150.19
via metal2 metal3 via2 66.74 17
via metal1 metal2 via1 72.0 200.5
via metal2 metal3 via2 72.0 200.5
via metal3 metal4 via3 72.0 200.5
rect metal4 71.81 6.81 72.19 200.69
via metal3 metal4 via3 72.0 7
via metal1 metal2 via1 77.26 150.0
rect metal2 77.07 26.81 77.45 150.19
via metal2 metal3 via2 77.26 27
via metal1 metal2 via1 64.5 150.0
rect metal2 64.31 0.81 64.69 150.19
via metal2 metal3 via2 64.5 1
rect metal1 93.81 99.31 94.19 99.69
rect metal1 86.5 124.81 88.17 125.19
via metal1 metal2 via1 88.74 125.0
rect metal2 88.55 28.81 88.93 125.19
via metal2 metal3 via2 88.74 29
via metal1 metal2 via1 94.0 150.5
via metal2 metal3 via2 94.0 150.5
via metal3 metal4 via3 94.0 150.5
rect metal4 93.81 28.81 94.19 150.69
via metal3 metal4 via3 94.0 29
via metal1 metal2 via1 99.26 125.0
rect metal2 99.07 2.81 99.45 125.19
via metal2 metal3 via2 99.26 3
via metal1 metal2 via1 86.5 125.0
rect metal2 86.31 2.81 86.69 125.19
via metal2 metal3 via2 86.5 3
rect metal1 115.81 99.31 116.19 99.69
rect metal1 108.5 124.81 110.17 125.19
via metal1 metal2 via1 110.74 125.0
rect metal2 110.55 16.81 110.93 125.19
via metal2 metal3 via2 110.74 17
via metal1 metal2 via1 116.0 150.5
via metal2 metal3 via2 116.0 150.5
via metal3 metal4 via3 116.0 150.5
rect metal4 115.81 28.81 116.19 150.69
via metal3 metal4 via3 116.0 29
via metal1 metal2 via1 121.26 125.0
rect metal2 121.07 2.81 121.45 125.19
via metal2 metal3 via2 121.26 3
via metal1 metal2 via1 108.5 125.0
rect metal2 108.31 2.81 108.69 125.19
via metal2 metal3 via2 108.5 3
rect metal1 137.81 99.31 138.19 99.69
rect metal1 134.5 109.81 136.67 110.19
via metal1 metal2 via1 137.24 110.0
rect metal2 137.05 18.81 137.43 110.19
via metal2 metal3 via2 137.24 19
via metal1 metal2 via1 138.0 120.5
via metal2 metal3 via2 138.0 120.5
via metal3 metal4 via3 138.0 120.5
rect metal4 137.81 16.81 138.19 120.69
via metal3 metal4 via3 138.0 17
via metal1 metal2 via1 138.76 110.0
rect metal2 138.57 2.81 138.95 110.19
via metal2 metal3 via2 138.76 3
via metal1 metal2 via1 134.5 110.0
rect metal2 134.31 2.81 134.69 110.19
via metal2 metal3 via2 134.5 3
rect metal1 155.81 99.31 156.19 99.69
rect metal1 148.5 149.81 150.17 150.19
via metal1 metal2 via1 150.74 150.0
rect metal2 150.55 18.81 150.93 150.19
via metal2 metal3 via2 150.74 19
via metal1 metal2 via1 156.0 200.5
via metal2 metal3 via2 156.0 200.5
via metal3 metal4 via3 156.0 200.5
rect metal4 155.81 18.81 156.19 200.69
via metal3 metal4 via3 156.0 19
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
rect metal4 177.81 18.81 178.19 200.69
via metal3 metal4 via3 178.0 19
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
rect metal4 199.81 18.81 200.19 200.69
via metal3 metal4 via3 200.0 19
via metal1 metal2 via1 205.26 150.0
rect metal2 205.07 0.81 205.45 150.19
via metal2 metal3 via2 205.26 1
via metal1 metal2 via1 192.5 150.0
rect metal2 192.31 0.81 192.69 150.19
via metal2 metal3 via2 192.5 1
rect metal1 221.81 99.31 222.19 99.69
rect metal1 217.5 109.81 219.17 110.19
via metal1 metal2 via1 219.74 110.0
rect metal2 219.55 20.81 219.93 110.19
via metal2 metal3 via2 219.74 21
via metal1 metal2 via1 222.0 120.5
via metal2 metal3 via2 222.0 120.5
via metal3 metal4 via3 222.0 120.5
rect metal4 221.81 20.81 222.19 120.69
via metal3 metal4 via3 222.0 21
via metal1 metal2 via1 224.26 110.0
rect metal2 224.07 0.81 224.45 110.19
via metal2 metal3 via2 224.26 1
via metal1 metal2 via1 217.5 110.0
rect metal2 217.31 0.81 217.69 110.19
via metal2 metal3 via2 217.5 1
rect metal1 239.81 99.31 240.19 99.69
rect metal1 235.5 109.81 237.17 110.19
via metal1 metal2 via1 237.74 110.0
rect metal2 237.55 30.81 237.93 110.19
via metal2 metal3 via2 237.74 31
via metal1 metal2 via1 240.0 120.5
via metal2 metal3 via2 240.0 120.5
via metal3 metal4 via3 240.0 120.5
rect metal4 239.81 20.81 240.19 120.69
via metal3 metal4 via3 240.0 21
via metal1 metal2 via1 242.26 110.0
rect metal2 242.07 0.81 242.45 110.19
via metal2 metal3 via2 242.26 1
via metal1 metal2 via1 235.5 110.0
rect metal2 235.31 0.81 235.69 110.19
via metal2 metal3 via2 235.5 1
rect metal1 257.81 99.31 258.19 99.69
rect metal1 250.5 149.81 252.17 150.19
via metal1 metal2 via1 252.74 150.0
rect metal2 252.55 32.81 252.93 150.19
via metal2 metal3 via2 252.74 33
via metal1 metal2 via1 258.0 200.5
via metal2 metal3 via2 258.0 200.5
via metal3 metal4 via3 258.0 200.5
rect metal4 257.81 4.81 258.19 200.69
via metal3 metal4 via3 258.0 5
via metal1 metal2 via1 263.26 150.0
rect metal2 263.07 30.81 263.45 150.19
via metal2 metal3 via2 263.26 31
via metal1 metal2 via1 250.5 150.0
rect metal2 250.31 0.81 250.69 150.19
via metal2 metal3 via2 250.5 1
rect metal1 279.81 99.31 280.19 99.69
rect metal1 272.5 149.81 274.17 150.19
via metal1 metal2 via1 274.74 150.0
rect metal2 274.55 22.81 274.93 150.19
via metal2 metal3 via2 274.74 23
via metal1 metal2 via1 280.0 200.5
via metal2 metal3 via2 280.0 200.5
via metal3 metal4 via3 280.0 200.5
rect metal4 279.81 10.81 280.19 200.69
via metal3 metal4 via3 280.0 11
via metal1 metal2 via1 285.26 150.0
rect metal2 285.07 30.81 285.45 150.19
via metal2 metal3 via2 285.26 31
via metal1 metal2 via1 272.5 150.0
rect metal2 272.31 0.81 272.69 150.19
via metal2 metal3 via2 272.5 1
rect metal1 301.81 99.31 302.19 99.69
rect metal1 294.5 124.81 296.17 125.19
via metal1 metal2 via1 296.74 125.0
rect metal2 296.55 32.81 296.93 125.19
via metal2 metal3 via2 296.74 33
via metal1 metal2 via1 302.0 150.5
via metal2 metal3 via2 302.0 150.5
via metal3 metal4 via3 302.0 150.5
rect metal4 301.81 32.81 302.19 150.69
via metal3 metal4 via3 302.0 33
via metal1 metal2 via1 307.26 125.0
rect metal2 307.07 2.81 307.45 125.19
via metal2 metal3 via2 307.26 3
via metal1 metal2 via1 294.5 125.0
rect metal2 294.31 2.81 294.69 125.19
via metal2 metal3 via2 294.5 3
rect metal1 323.81 99.31 324.19 99.69
rect metal1 316.5 124.81 318.17 125.19
via metal1 metal2 via1 318.74 125.0
rect metal2 318.55 22.81 318.93 125.19
via metal2 metal3 via2 318.74 23
via metal1 metal2 via1 324.0 150.5
via metal2 metal3 via2 324.0 150.5
via metal3 metal4 via3 324.0 150.5
rect metal4 323.81 32.81 324.19 150.69
via metal3 metal4 via3 324.0 33
via metal1 metal2 via1 329.26 125.0
rect metal2 329.07 2.81 329.45 125.19
via metal2 metal3 via2 329.26 3
via metal1 metal2 via1 316.5 125.0
rect metal2 316.31 2.81 316.69 125.19
via metal2 metal3 via2 316.5 3
rect metal1 345.81 99.31 346.19 99.69
rect metal1 342.5 109.81 344.67 110.19
via metal1 metal2 via1 345.24 110.0
rect metal2 345.05 24.81 345.43 110.19
via metal2 metal3 via2 345.24 25
via metal1 metal2 via1 346.0 120.5
via metal2 metal3 via2 346.0 120.5
via metal3 metal4 via3 346.0 120.5
rect metal4 345.81 22.81 346.19 120.69
via metal3 metal4 via3 346.0 23
via metal1 metal2 via1 346.76 110.0
rect metal2 346.57 2.81 346.95 110.19
via metal2 metal3 via2 346.76 3
via metal1 metal2 via1 342.5 110.0
rect metal2 342.31 2.81 342.69 110.19
via metal2 metal3 via2 342.5 3
rect metal1 363.81 99.31 364.19 99.69
rect metal1 356.5 149.81 358.17 150.19
via metal1 metal2 via1 358.74 150.0
rect metal2 358.55 24.81 358.93 150.19
via metal2 metal3 via2 358.74 25
via metal1 metal2 via1 364.0 200.5
via metal2 metal3 via2 364.0 200.5
via metal3 metal4 via3 364.0 200.5
rect metal4 363.81 24.81 364.19 200.69
via metal3 metal4 via3 364.0 25
via metal1 metal2 via1 369.26 150.0
rect metal2 369.07 0.81 369.45 150.19
via metal2 metal3 via2 369.26 1
via metal1 metal2 via1 356.5 150.0
rect metal2 356.31 0.81 356.69 150.19
via metal2 metal3 via2 356.5 1
rect metal1 385.81 99.31 386.19 99.69
rect metal1 378.5 149.81 380.17 150.19
via metal1 metal2 via1 380.74 150.0
rect metal2 380.55 12.81 380.93 150.19
via metal2 metal3 via2 380.74 13
via metal1 metal2 via1 386.0 200.5
via metal2 metal3 via2 386.0 200.5
via metal3 metal4 via3 386.0 200.5
rect metal4 385.81 24.81 386.19 200.69
via metal3 metal4 via3 386.0 25
via metal1 metal2 via1 391.26 150.0
rect metal2 391.07 0.81 391.45 150.19
via metal2 metal3 via2 391.26 1
via metal1 metal2 via1 378.5 150.0
rect metal2 378.31 0.81 378.69 150.19
via metal2 metal3 via2 378.5 1
select top cell
drc style drc(full)
drc check
drc catchup
puts "NRZ_DRC_COUNT [drc list count total]"
puts "NRZ_DRC_ERRORS [drc listall why]"
save nrz_bias_power
extract all
ext2spice lvs
ext2spice
gds write nrz_bias_power.gds
quit -noprompt
