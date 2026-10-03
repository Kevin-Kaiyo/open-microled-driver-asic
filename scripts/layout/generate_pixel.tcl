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
    {MREF nfet_06v0 20 4 10 26 bias bias VSS VSS}
    {MOUT nfet_06v0 20 4 25 26 led_k gate VSS VSS}
    {MPASS nfet_06v0 2 1 40 20 bias pwm gate VSS}
    {MCLAMP nfet_06v0 2 1 55 20 gate pwm_b VSS VSS}
    {MINV_N nfet_06v0 2 1 70 20 pwm_b pwm VSS VSS}
    {MINV_P pfet_06v0 4 1 85 20 pwm_b pwm vlogic vlogic}
}
foreach device $devices {
    lassign $device name type w l cx cy d g s b
    load $name
    box values 0 0 0 0
    set defaults [gf180mcu::${type}_defaults]
    gf180mcu::${type}_draw [dict merge $defaults [dict create w $w l $l]]
    save $name
}
load pixel_assembly
foreach device $devices {
    lassign $device name type w l cx cy d g s b
    getcell $name child 0 0 parent ${cx}um ${cy}um
}
select top cell
flatten -nolabels pixel_driver_layout
load pixel_driver_layout

# Metal3 buses; every Metal2 column reaches exactly one bus via a via2.
# These deliberately spacious routes support teaching and connectivity review.
set buses [dict create VSS 0 bias 2 gate 4 pwm 6 pwm_b 8 led_k 10 vlogic 12]
foreach net [dict keys $buses] {
    set y [dict get $buses $net]
    rect metal3 0 [expr {$y-0.3}] 95 [expr {$y+0.3}]
    box values 0um [expr {$y-0.3}]um 3um [expr {$y+0.3}]um
    label $net center metal3
    port make
}
foreach device $devices {
    lassign $device name type w l cx cy d g s b
    set dx [expr {$l/2.0+0.26}]
    set gx $cx
    set gy [expr {$cy-$w/2.0-0.28}]
    # Wider channel length moves the guard contact left; retain >=0.23um
    # spacing between the bulk via landing and unconnected guard segments.
    set bx [expr {$cx-max(3.5,$l/2.0+2.5)}]
    set ringx [expr {$cx-$l/2.0-0.98}]
    # Left-hand contacted guard ring connects to a dedicated bulk column.
    rect metal1 $bx [expr {$cy-0.25}] [expr {$ringx+0.15}] [expr {$cy+0.25}]
    foreach pin [list [list $d [expr {$cx-$dx}] $cy] [list $s [expr {$cx+$dx}] $cy] [list $g $gx $gy] [list $b $bx $cy]] {
        lassign $pin net x y
        padvia metal1 metal2 via1 $x $y
        set by [dict get $buses $net]
        rect metal2 [expr {$x-0.2}] [expr {$by-0.2}] [expr {$x+0.2}] [expr {$y+0.2}]
        padvia metal2 metal3 via2 $x $by
    }
}
select top cell
drc style drc(full)
drc style
drc check
drc catchup
puts "PIXEL_DRC_COUNT [drc list count total]"
puts "PIXEL_DRC_ERRORS [drc listall why]"
save pixel_driver_layout
extract all
ext2spice lvs
ext2spice
gds write pixel_driver_layout.gds
quit -noprompt
