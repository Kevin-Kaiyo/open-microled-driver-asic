load hs_voltage_robust
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist off
ext2spice -o flat-c.spice
quit -noprompt
