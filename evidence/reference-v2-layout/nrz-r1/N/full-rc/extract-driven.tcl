load nrz_bias_power
select top cell
extract style ngspice()
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o nrz_bias_power_rc.spice
quit -noprompt
