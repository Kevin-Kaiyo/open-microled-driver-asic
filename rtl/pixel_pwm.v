`timescale 1ns/1ps

// One pixel, 256 clock slots per frame. Inputs commit at a frame boundary.
module pixel_pwm (
    input  wire       clk,
    input  wire       rst,
    input  wire [8:0] duty,
    input  wire       enable,
    output wire       pwm
);
    reg [7:0] counter;
    reg [8:0] active_duty;
    reg       active_enable;

    // A nine-bit threshold includes both exact off (0) and exact on (256).
    wire [8:0] bounded_duty = (duty > 9'd256) ? 9'd256 : duty;

    always @(posedge clk) begin
        if (rst) begin
            // The first clock after reset release starts a complete new frame.
            counter       <= 8'hff;
            active_duty   <= 9'd0;
            active_enable <= 1'b0;
        end else if (counter == 8'hff) begin
            counter       <= 8'd0;
            active_duty   <= bounded_duty;
            active_enable <= enable;
        end else begin
            counter <= counter + 8'd1;
        end
    end

    assign pwm = active_enable && ({1'b0, counter} < active_duty);
endmodule
