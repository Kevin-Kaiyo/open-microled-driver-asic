`timescale 1ns/1ps
// Separate interlock: never changes the registered frame-PWM implementation.
// fault is active high and must start asserted while the safety supply is valid.
// Assertion bypasses clk. Release requires an explicit request on a clock edge
// for which the pre-edge raw PWM is low; this is an RTL recovery controller,
// not a transistor/physical implementation of its storage element.
module pixel_safety (
    input wire clk,
    input wire fault,
    input wire recover_request,
    input wire raw_pwm,
    output wire permit,
    output wire protected_pwm
);
    reg inhibit;
    always @(posedge clk or posedge fault) begin
        if (fault)
            inhibit <= 1'b1;
        else if (recover_request && !raw_pwm)
            inhibit <= 1'b0;
    end
    assign permit = !inhibit;
    // A direct fault term remains effective independently of storage/clock.
    assign protected_pwm = raw_pwm && permit && !fault;
endmodule
