load nrz_reference_integrated
select top cell
extract style ngspice()
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist ignore {a_n1100_n7186#}
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o nrz_reference_integrated_rc.spice
quit -noprompt
