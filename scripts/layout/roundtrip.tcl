gds read $env(LAYOUT_GDS)
load pixel_driver_layout
select top cell
drc style drc(full)
drc style
drc check
drc catchup
puts "ROUNDTRIP_DRC_COUNT [drc list count total]"
puts "ROUNDTRIP_DRC_ERRORS [drc listall why]"
save pixel_driver_layout
extract all
ext2spice lvs
ext2spice
quit -noprompt
