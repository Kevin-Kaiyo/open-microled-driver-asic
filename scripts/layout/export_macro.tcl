# Derive an actual routing abstract from the verified Magic cell.
load pixel_driver_layout
box values 0 0 0 0
port VSS class inout
port VSS use ground
port vlogic class inout
port vlogic use power
port pwm class input
port pwm use signal
port bias class inout
port bias use signal
port gate class output
port gate use signal
port pwm_b class output
port pwm_b use signal
port led_k class inout
port led_k use signal
property LEFclass BLOCK
property FIXED_BBOX $env(MACRO_BBOX)
lef write pixel_driver_layout -toplayer -nomaster
quit -noprompt
