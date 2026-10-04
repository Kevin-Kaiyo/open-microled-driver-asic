// One pixel physical integration; controls are bare macro ports, no pads/ESD.
module pixel_integrated(input clk, input rst, input enable, input [8:0] duty,
    inout VDD, inout VSS, inout bias, inout led_k,
    output gate, output pwm_b, output pwm_monitor);
wire pwm_link;
assign pwm_monitor = pwm_link;
pixel_pwm digital (.clk(clk),.rst(rst),.enable(enable),.duty(duty),.pwm(pwm_link),.VDD(VDD),.VSS(VSS));
pixel_driver_layout analog (.VSS(VSS),.bias(bias),.gate(gate),.pwm(pwm_link),.pwm_b(pwm_b),.led_k(led_k),.vlogic(VDD));
endmodule
