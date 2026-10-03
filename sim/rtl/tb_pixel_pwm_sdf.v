`timescale 1ns/1ps

// Reuse the functional and event assertions with a settling allowance for
// the implemented clock tree, FF and output buffer. Require actual SDF input.
module tb_pixel_pwm_sdf;
    tb_pixel_pwm #(
        .SAMPLE_DELAY_NS(100),
        .OUTPUT_EVENT_MAX_DELAY_NS(50)
    ) tb();
    reg [8191:0] sdf_path;
    initial begin
        if (!$value$plusargs("SDF=%s", sdf_path))
            $fatal(1, "An actual post-route +SDF=<file> is required");
        $sdf_annotate(sdf_path, tb.dut);
    end
endmodule
