load smoke
box values 0 0 0 0
set p [dict merge [gf180mcu::nfet_06v0_defaults] {w 10 l 2}]
puts "DEVICE_BOX [gf180mcu::nfet_06v0_draw $p]"
select top cell
drc check
drc catchup
puts "DRC_COUNT [drc list count total]"
puts "DRC_ERRORS [drc listall why]"
save smoke
extract all
ext2spice lvs
ext2spice
gds write smoke.gds
quit -noprompt
