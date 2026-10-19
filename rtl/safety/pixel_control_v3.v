`timescale 1ns/1ps
// Physical implementation wrapper for the existing, separately verified RTL.
// raw_pwm and permit feed the independent analog fault gate. protected_monitor
// is an observation output; it is not the analog pixel drive connection.
// External fault must be asserted at startup with valid safety supply.
module pixel_control_v3 (
    input wire clk,
    input wire rst,
    input wire [8:0] duty,
    input wire enable,
    input wire fault,
    input wire recover_request,
    output wire raw_pwm,
    output wire permit,
    output wire protected_monitor
);
    pixel_pwm pwm_core(clk, rst, duty, enable, raw_pwm);
    pixel_safety recovery(clk, fault, recover_request, raw_pwm,
                          permit, protected_monitor);
endmodule
