gds read $env(INTEGRATION_GDS)
load pixel_integrated
select top cell
box values 150.000um 144.840um 150.560um 145.400um
label {clk} center metal3
port make
box values 150.000um 97.800um 150.560um 98.360um
label {duty[0]} center metal3
port make
box values 150.000um 100.040um 150.560um 100.600um
label {duty[1]} center metal3
port make
box values 150.000um 98.920um 150.560um 99.480um
label {duty[2]} center metal3
port make
box values 150.000um 112.360um 150.560um 112.920um
label {duty[3]} center metal3
port make
box values 150.000um 103.400um 150.560um 103.960um
label {duty[4]} center metal3
port make
box values 150.000um 116.840um 150.560um 117.400um
label {duty[5]} center metal3
port make
box values 150.000um 130.280um 150.560um 130.840um
label {duty[6]} center metal3
port make
box values 150.000um 135.880um 150.560um 136.440um
label {duty[7]} center metal3
port make
box values 150.000um 126.920um 150.560um 127.480um
label {duty[8]} center metal3
port make
box values 150.000um 117.960um 150.560um 118.520um
label {enable} center metal3
port make
box values 150.000um 138.120um 150.560um 138.680um
label {rst} center metal3
port make
box values 25.000um 107.220um 28.000um 107.820um
label {bias} center metal3
port make
box values 25.000um 109.220um 28.000um 109.820um
label {gate} center metal3
port make
box values 25.000um 113.220um 28.000um 113.820um
label {pwm_b} center metal3
port make
box values 25.000um 115.220um 28.000um 115.820um
label {led_k} center metal3
port make
box values 139.650um 116.500um 140.350um 117.520um
label {VDD} center metal4
port make
box values 134.650um 104.500um 135.350um 105.520um
label {VSS} center metal5
port make
box values 125.000um 111.240um 126.000um 111.800um
label {pwm_monitor} center metal3
port make
drc style drc(full)
drc style
drc check
drc catchup
puts "INTEGRATION_DRC_COUNT [drc list count total]"
puts "INTEGRATION_DRC_ALL [drc listall count]"
select top cell
box sel
puts "INTEGRATION_DRC_ERRORS [drc listall why]"
save pixel_integrated
extract all
ext2spice lvs
ext2spice
quit -noprompt
