load pixel_driver_layout
select top cell
extract style ngspice()
extract do capacitance
extract do coupling
extresist threshold 0
extresist minres 0
extresist mindelay 0
extract do resistance
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o pixel_driver_rc.spice
quit -noprompt
