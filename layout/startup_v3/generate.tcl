# Independent educational layout, using the pinned GF180MCU Magic PCells.
# All coordinates are um; mirror W/L use the reviewed v0.2 20/4 sizing.
proc rect {layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    paint $layer
}
proc padvia {lo hi via x y} {
    set lowidth [expr {$lo eq "metal2" ? 0.22 : 0.30}]
    set hiwidth [expr {$hi eq "metal2" ? 0.22 : 0.30}]
    set cut [expr {$via eq "via2" ? 0.14 : 0.13}]
    rect $lo [expr {$x-$lowidth}] [expr {$y-$lowidth}] [expr {$x+$lowidth}] [expr {$y+$lowidth}]
    rect $hi [expr {$x-$hiwidth}] [expr {$y-$hiwidth}] [expr {$x+$hiwidth}] [expr {$y+$hiwidth}]
    rect $via [expr {$x-$cut}] [expr {$y-$cut}] [expr {$x+$cut}] [expr {$y+$cut}]
}

set devices {
 {R_PBIAS pfet_06v0 20.0 4.0 14 145 PB PB VREF VREF}
 {R_PTAIL pfet_06v0 20.0 4.0 32 145 R_TAIL PB VREF VREF}
 {R_PD1 pfet_06v0 100.0 10.0 50 145 R_N1 VSET R_TAIL VREF}
 {R_PD2 pfet_06v0 100.0 10.0 72.0 145 N2 SENSE R_TAIL VREF}
 {R_ND1 nfet_06v0 50.0 10.0 94.0 145 R_N1 R_N1 VSS VSS}
 {R_ND2 nfet_06v0 50.0 10.0 116.0 145 N2 R_N1 VSS VSS}
 {R_NSTAGE nfet_06v0 20.0 1.0 138.0 145 CTRL N2 VSS VSS}
 {R_PLOAD pfet_06v0 100.0 10.0 156.0 145 CTRL CTRL VREF VREF}
 {R_PREG pfet_06v0 100.0 10.0 178.0 145 SENSE CTRL VREF VREF}
 {R_POUT pfet_06v0 100.0 10.0 200.0 145 REFOUT CTRL VREF VREF}
 {I_FN nfet_06v0 2.0 1.0 222.0 100 I_FAULT_B FAULT VSS VSS}
 {I_FP pfet_06v0 4.0 1.0 240.0 100 I_FAULT_B FAULT VSAFE VSAFE}
 {I_ISO nfet_06v0 20.0 1.0 258.0 145 REFOUT I_FAULT_B BIAS VSS}
 {I_PISO pfet_06v0 20.0 1.0 276.0 145 BIAS FAULT REFOUT VSAFE}
 {I_DIS nfet_06v0 2.0 1.0 294.0 100 BIAS FAULT VSS VSS}
 {F_FN nfet_06v0 2.0 1.0 312.0 100 F_FAULT_B FAULT VSS VSS}
 {F_FP pfet_06v0 4.0 1.0 330.0 100 F_FAULT_B FAULT VSAFE VSAFE}
 {F_NP0 pfet_06v0 4.0 1.0 348.0 100 F_NAND_N RAW_PWM VSAFE VSAFE}
 {F_NP1 pfet_06v0 4.0 1.0 366.0 100 F_NAND_N PERMIT VSAFE VSAFE}
 {F_NP2 pfet_06v0 4.0 1.0 384.0 100 F_NAND_N F_FAULT_B VSAFE VSAFE}
 {F_NN0 nfet_06v0 6.0 1.0 402.0 100 F_NAND_N RAW_PWM F_STACK1 VSS}
 {F_NN1 nfet_06v0 6.0 1.0 420.0 100 F_STACK1 PERMIT F_STACK2 VSS}
 {F_NN2 nfet_06v0 6.0 1.0 438.0 100 F_STACK2 F_FAULT_B VSS VSS}
 {F_ON nfet_06v0 4.0 1.0 456.0 100 SAFE_OUT F_NAND_N VSS VSS}
 {F_OP pfet_06v0 8.0 1.0 474.0 100 SAFE_OUT F_NAND_N VSAFE VSAFE}
 {C_LN0 nfet_06v0 2.0 1.0 492.0 100 FAULT_HB FAULT VSS VSS}
 {C_CP pfet_06v0 2.0 1.0 510.0 100 LED_K FAULT_HB LED_A LED_A}
 {P_REF nfet_06v0 20.0 4.0 528.0 145 BIAS BIAS VSS VSS}
 {P_OUT nfet_06v0 20.0 4.0 546.0 145 LED_K GATE VSS VSS}
 {P_PASS nfet_06v0 2.0 1.0 564.0 100 BIAS PWM_DRIVE GATE VSS}
 {P_CLAMP nfet_06v0 2.0 1.0 582.0 100 GATE PWM_B VSS VSS}
 {P_INV_N nfet_06v0 2.0 1.0 600.0 100 PWM_B PWM_DRIVE VSS VSS}
 {P_INV_P pfet_06v0 4.0 1.0 618.0 100 PWM_B PWM_DRIVE VBUF VBUF}
}
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 load $name
 box values 0 0 0 0
 gf180mcu::${type}_draw [dict merge [gf180mcu::${type}_defaults] [dict create w $w l $l]]
 save $name
}
gds read /Users/kimmy/Projects/open-microled-driver-asic/layout/startup_v3/official_buf_2.gds
load startup_assembly
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 getcell $name child 0 0 parent ${cx}um ${cy}um
}
getcell gf180mcu_fd_sc_mcu7t5v0__buf_2 child 0 0 parent 640.0um 100um
getcell gf180mcu_fd_sc_mcu7t5v0__filltie child 0 0 parent 644.48um 100um
select top cell
flatten -nolabels startup_test_macro
load startup_test_macro
set buses [dict create VSS 0 VREF 8 VSAFE 11 VBUF 14 LED_A 17 RAW_PWM 20 FAULT 23 PERMIT 26 VSET 29 SENSE 32 PB 35 N2 38 CTRL 41 FAULT_HB 44 LED_K 47 REFOUT 50 BIAS 53 GATE 56 PWM_B 59 SAFE_OUT 62 PWM_DRIVE 65 R_TAIL 68 R_N1 71 I_FAULT_B 74 F_FAULT_B 77 F_NAND_N 80 F_STACK1 83 F_STACK2 86]
rect metal3 86.0 -4 640.8 4
box values 363.2um -0.2um 363.59999999999997um 0.2um
label VSS center metal3
port make
rect metal3 9.0 7.7 205.76 8.3
box values 107.17999999999999um 7.8um 107.58um 8.2um
label VREF center metal3
port make
rect metal3 236.0 10.7 475.26 11.3
box values 355.43um 10.8um 355.83um 11.2um
label VSAFE center metal3
port make
rect metal3 614.0 13.7 644.9 14.3
box values 629.25um 13.8um 629.6500000000001um 14.2um
label VBUF center metal3
port make
rect metal3 506.0 16.7 511.26 17.3
box values 508.43um 16.8um 508.83um 17.2um
label LED_A center metal3
port make
rect metal3 347.5 19.7 402.5 20.3
box values 347.6um 19.8um 348.0um 20.2um
label RAW_PWM center metal3
port make
rect metal3 221.5 22.7 492.5 23.3
box values 221.60000000000002um 22.8um 222.0um 23.2um
label FAULT center metal3
port make
rect metal3 365.5 25.7 420.5 26.3
box values 365.6um 25.8um 366.0um 26.2um
label PERMIT center metal3
port make
rect metal3 49.5 28.7 50.5 29.3
box values 49.599999999999994um 28.8um 50.0um 29.2um
label VSET center metal3
port make
rect metal3 71.5 31.7 173.24 32.3
box values 71.6um 31.8um 72.0um 32.2um
label SENSE center metal3
port make
rect metal3 11.24 34.7 32.5 35.3
box values 11.340000000000002um 34.8um 11.74um 35.2um
label PB center metal3
port make
rect metal3 66.24 37.7 138.5 38.3
box values 66.33999999999999um 37.8um 66.74um 38.2um
label N2 center metal3
port make
rect metal3 136.74 40.7 200.5 41.3
box values 136.84000000000003um 40.8um 137.24um 41.2um
label CTRL center metal3
port make
rect metal3 490.74 43.7 510.5 44.3
box values 490.84000000000003um 43.8um 491.24um 44.2um
label FAULT_HB center metal3
port make
rect metal3 508.74 46.7 544.24 47.3
box values 508.84000000000003um 46.8um 509.24um 47.2um
label LED_K center metal3
port make
rect metal3 194.24 49.7 277.26 50.3
box values 194.34000000000003um 49.8um 194.74um 50.2um
label REFOUT center metal3
port make
rect metal3 258.26 52.7 563.74 53.3
box values 258.36um 52.8um 258.76um 53.2um
label BIAS center metal3
port make
rect metal3 545.5 55.7 581.74 56.3
box values 545.5999999999999um 55.8um 546.0um 56.2um
label GATE center metal3
port make
rect metal3 581.5 58.7 617.74 59.3
box values 581.5999999999999um 58.8um 582.0um 59.2um
label PWM_B center metal3
port make
rect metal3 454.74 61.7 641.7 62.3
box values 454.84000000000003um 61.8um 455.24um 62.2um
label SAFE_OUT center metal3
port make
rect metal3 563.5 64.7 644.0 65.3
box values 563.5999999999999um 64.8um 564.0um 65.2um
label PWM_DRIVE center metal3
port make
rect metal3 29.240000000000002 67.7 77.76 68.3
box values 29.340000000000003um 67.8um 29.740000000000002um 68.2um
label R_TAIL center metal3
rect metal3 44.24 70.7 116.5 71.3
box values 44.339999999999996um 70.8um 44.74um 71.2um
label R_N1 center metal3
rect metal3 220.74 73.7 258.5 74.3
box values 220.84000000000003um 73.8um 221.24um 74.2um
label I_FAULT_B center metal3
rect metal3 310.74 76.7 438.5 77.3
box values 310.84000000000003um 76.8um 311.24um 77.2um
label F_FAULT_B center metal3
rect metal3 346.74 79.7 474.5 80.3
box values 346.84000000000003um 79.8um 347.24um 80.2um
label F_NAND_N center metal3
rect metal3 402.26 82.7 419.74 83.3
box values 402.36um 82.8um 402.76um 83.2um
label F_STACK1 center metal3
rect metal3 420.26 85.7 437.74 86.3
box values 420.36um 85.8um 420.76um 86.2um
label F_STACK2 center metal3
foreach device $devices {
 lassign $device name type w l cx cy d g s b
 set dx [expr {$l/2.0+0.26}]
 set gx $cx
 set gy [expr {$cy-$w/2.0-0.28}]
 set bx [expr {$cx-max(3.5,$l/2.0+2.5)}]
 set ringx [expr {$cx-$l/2.0-0.98}]
 rect metal1 $bx [expr {$cy-0.25}] [expr {$ringx+0.15}] [expr {$cy+0.25}]
 foreach pin [list [list $d [expr {$cx-$dx}] $cy] [list $s [expr {$cx+$dx}] $cy] [list $g $gx $gy] [list $b $bx $cy]] {
  lassign $pin net x y
  padvia metal1 metal2 via1 $x $y
  set by [dict get $buses $net]
  rect metal2 [expr {$x-0.2}] [expr {$by-0.2}] [expr {$x+0.2}] [expr {$y+0.2}]
  padvia metal2 metal3 via2 $x $by
 }
}
padvia metal1 metal2 via1 641.2 101.85
rect metal2 641.0 61.8 641.4000000000001 102.05
padvia metal2 metal3 via2 641.2 62
padvia metal1 metal2 via1 643.5 102.45
rect metal2 643.3 64.8 643.7 102.65
padvia metal2 metal3 via2 643.5 65
padvia metal1 metal2 via1 644.4 103.92
rect metal2 644.1999999999999 13.8 644.6 104.12
padvia metal2 metal3 via2 644.4 14
padvia metal1 metal2 via1 640.3 100
rect metal2 640.0999999999999 -0.2 640.5 100.2
padvia metal2 metal3 via2 640.3 0
select top cell
drc style drc(full)
drc style
drc check
drc catchup
puts "V3_DRC_COUNT [drc list count total]"
puts "V3_DRC_ERRORS [drc listall why]"
save startup_test_macro
extract all
ext2spice lvs
ext2spice
gds write startup_test_macro.gds
quit -noprompt
