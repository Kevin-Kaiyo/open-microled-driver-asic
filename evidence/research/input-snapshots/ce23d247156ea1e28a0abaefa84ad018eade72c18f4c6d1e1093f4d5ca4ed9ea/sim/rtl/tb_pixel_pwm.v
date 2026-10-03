`timescale 1ns/1ps

module tb_pixel_pwm;
    parameter integer CLK_PERIOD_NS = 1000;
    // Gate-level regression may allow the explicitly selected cell delay.
    parameter integer SAMPLE_DELAY_NS = 1;
    parameter integer OUTPUT_EVENT_MAX_DELAY_NS = 0;

    reg clk = 1'b0;
    reg rst = 1'b1;
    reg [8:0] duty = 9'd0;
    reg enable = 1'b0;
    wire pwm;

    integer trace_fd = 0;
    integer requested_duty = 64;
    integer requested_enable = 1;
    integer trace_only = 0;
    integer warmup_frames = 2;
    integer measure_frames = 4;
    integer unused_arg;
    integer level;
    integer checks = 0;
    integer frames_checked = 0;
    integer midframe_changes = 0;
    integer watch_midframe = 0;
    integer known_pwm_events = 0;
    integer events_this_clock = 0;
    real last_clock_ns = -1000.0;
    real last_event_ns = -1.0;
    real minimum_high_ns = 1.0e30;
    real minimum_low_ns = 1.0e30;
    real pulse_ns;
    reg last_known_value;
    integer trace_end_ns;
    reg [4095:0] output_path = "events.csv";

    pixel_pwm dut (
        .clk(clk), .rst(rst), .duty(duty), .enable(enable), .pwm(pwm)
    );

    always #(CLK_PERIOD_NS / 2) clk = ~clk;

    always @(posedge clk) begin
        last_clock_ns = $realtime;
        events_this_clock = 0;
    end

    // Only settled, known transitions from the real RTL enter the trace.
    // Synchronous reset first makes the output known at the first rising edge.
    always @(pwm) begin
        if (pwm === 1'b0 || pwm === 1'b1) begin
            known_pwm_events = known_pwm_events + 1;
            events_this_clock = events_this_clock + 1;
            if (clk !== 1'b1 || $realtime < last_clock_ns ||
                $realtime > last_clock_ns + OUTPUT_EVENT_MAX_DELAY_NS)
                $fatal(1, "PWM changed away from a rising clock edge at %0d ns", $time);
            if (events_this_clock > 1)
                $fatal(1, "Multiple PWM events following one clock edge");
            if (last_event_ns >= 0.0) begin
                pulse_ns = $realtime - last_event_ns;
                if (pulse_ns < CLK_PERIOD_NS - OUTPUT_EVENT_MAX_DELAY_NS)
                    $fatal(1, "PWM pulse too short: %0.3f ns", pulse_ns);
                if (last_known_value == 1'b1 && pulse_ns < minimum_high_ns)
                    minimum_high_ns = pulse_ns;
                if (last_known_value == 1'b0 && pulse_ns < minimum_low_ns)
                    minimum_low_ns = pulse_ns;
            end
            last_event_ns = $realtime;
            last_known_value = pwm;
        end else if (last_event_ns >= 0.0) begin
            $fatal(1, "PWM became unknown after its first known reset value");
        end
        if (trace_fd != 0 && (pwm === 1'b0 || pwm === 1'b1))
            $fdisplay(trace_fd, "%0d,%0d", $time, pwm);
        if (watch_midframe != 0)
            midframe_changes = midframe_changes + 1;
    end

    task expect_value;
        input integer expected;
        input [511:0] context_name;
        begin
            checks = checks + 1;
            if (pwm !== expected[0]) begin
                $display("FAIL %0s at %0d ns: pwm=%b expected=%0d",
                         context_name, $time, pwm, expected);
                $fatal(1);
            end
        end
    endtask

    // Called just before a frame's first rising edge. Check every slot and
    // independently count high slots, including both endpoint duty values.
    task check_frame;
        input integer expected_duty;
        input integer expected_enable;
        integer index;
        integer high_slots;
        integer expected_high;
        begin
            high_slots = 0;
            expected_high = expected_enable ? expected_duty : 0;
            for (index = 0; index < 256; index = index + 1) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(expected_enable && index < expected_duty,
                             "frame slot");
                if (pwm === 1'b1)
                    high_slots = high_slots + 1;
            end
            if (high_slots != expected_high) begin
                $display("FAIL frame count: got %0d expected %0d",
                         high_slots, expected_high);
                $fatal(1);
            end
            frames_checked = frames_checked + 1;
        end
    endtask

    task start_fresh_frame;
        input integer next_duty;
        input integer next_enable;
        begin
            @(negedge clk);
            rst = 1'b1;
            duty = next_duty;
            enable = next_enable;
            repeat (2) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(0, "synchronous reset");
            end
            @(negedge clk);
            rst = 1'b0;
        end
    endtask

    task run_self_checks;
        integer index;
        integer previous_value;
        begin
            start_fresh_frame(0, 1);
            for (level = 0; level <= 256; level = level + 1) begin
                if (level != 0) begin
                    @(negedge clk);
                    duty = level;
                end
                check_frame(level, 1);
            end

            // Jump directly between both endpoints at consecutive boundaries.
            @(negedge clk);
            duty = 9'd0;
            check_frame(0, 1);
            @(negedge clk);
            duty = 9'd256;
            check_frame(256, 1);

            // Input updates during the frame must leave its waveform intact.
            start_fresh_frame(64, 1);
            for (index = 0; index < 256; index = index + 1) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(index < 64, "duty update holds current frame");
                if (index == 17 || index == 90 || index == 201) begin
                    previous_value = pwm;
                    midframe_changes = 0;
                    watch_midframe = 1;
                    // Exercise changes away from either clock edge.
                    #(CLK_PERIOD_NS / 8);
                    if (index == 17)
                        duty = 9'd256;
                    else if (index == 90)
                        duty = 9'd0;
                    else
                        duty = 9'd128;
                    #(CLK_PERIOD_NS / 8);
                    watch_midframe = 0;
                    expect_value(previous_value, "asynchronous duty change");
                    if (midframe_changes != 0)
                        $fatal(1, "input update caused a mid-frame PWM event");
                end
            end
            check_frame(128, 1);

            // Disable commits at the boundary, not at the update instant.
            start_fresh_frame(256, 1);
            for (index = 0; index < 256; index = index + 1) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(1, "disable holds current frame");
                if (index == 23) begin
                    midframe_changes = 0;
                    watch_midframe = 1;
                    #(CLK_PERIOD_NS / 8);
                    enable = 1'b0;
                    #(CLK_PERIOD_NS / 8);
                    watch_midframe = 0;
                    expect_value(1, "asynchronous disable change");
                    if (midframe_changes != 0)
                        $fatal(1, "disable update caused a mid-frame PWM event");
                end
            end
            check_frame(256, 0);
            @(negedge clk);
            enable = 1'b1;
            check_frame(256, 1);

            // Every nine-bit out-of-range request saturates to full-on.
            start_fresh_frame(257, 1);
            check_frame(256, 1);
            for (level = 258; level <= 511; level = level + 1) begin
                @(negedge clk);
                duty = level;
                check_frame(256, 1);
            end

            // Reset interrupts a live full-on frame on its next rising edge,
            // remains low while asserted, then restarts at slot zero.
            start_fresh_frame(256, 1);
            repeat (19) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(1, "pre-reset full-on frame");
            end
            #(CLK_PERIOD_NS / 8);
            rst = 1'b1;
            #(CLK_PERIOD_NS / 8);
            expect_value(1, "reset is synchronous");
            repeat (3) begin
                @(posedge clk);
                #(SAMPLE_DELAY_NS);
                expect_value(0, "reset interrupts frame");
            end
            @(negedge clk);
            duty = 9'd1;
            enable = 1'b1;
            rst = 1'b0;
            check_frame(1, 1);

            $display("PASS pixel_pwm: all 257 valid duty levels, all 255 clamped levels, frame updates, enable, reset; %0d frames and %0d slot/value checks",
                     frames_checked, checks);
            $display("PASS pixel_pwm output events: %0d known events; at most one event per rising clock; delay window 0..%0d ns; minimum high=%0.3f ns low=%0.3f ns", known_pwm_events, OUTPUT_EVENT_MAX_DELAY_NS, minimum_high_ns, minimum_low_ns);
        end
    endtask

    initial begin
        unused_arg = $value$plusargs("OUT=%s", output_path);
        unused_arg = $value$plusargs("DUTY=%d", requested_duty);
        unused_arg = $value$plusargs("ENABLE=%d", requested_enable);
        unused_arg = $value$plusargs("TRACE_ONLY=%d", trace_only);
        unused_arg = $value$plusargs("WARMUP_FRAMES=%d", warmup_frames);
        unused_arg = $value$plusargs("MEASURE_FRAMES=%d", measure_frames);
        if (CLK_PERIOD_NS < 16 || CLK_PERIOD_NS % 2 != 0)
            $fatal(1, "CLK_PERIOD_NS must be even and at least 16");
        if (SAMPLE_DELAY_NS <= OUTPUT_EVENT_MAX_DELAY_NS ||
            SAMPLE_DELAY_NS >= CLK_PERIOD_NS / 4)
            $fatal(1, "Sample delay must exceed allowed output delay and be less than a quarter cycle");
        if (requested_duty < 0 || requested_duty > 511)
            $fatal(1, "DUTY must fit the 9-bit input (0..511)");
        if (requested_enable != 0 && requested_enable != 1)
            $fatal(1, "ENABLE must be 0 or 1");
        if (trace_only != 0 && trace_only != 1)
            $fatal(1, "TRACE_ONLY must be 0 or 1");
        if (warmup_frames < 0 || measure_frames < 1)
            $fatal(1, "WARMUP_FRAMES >= 0 and MEASURE_FRAMES >= 1 required");

        duty = requested_duty;
        enable = requested_enable;
        trace_fd = $fopen(output_path, "w");
        if (trace_fd == 0)
            $fatal(1, "Cannot open requested CSV output");
        $fdisplay(trace_fd, "time_ns,pwm");

        // Export the requested case first, so its timing is independent of
        // the longer self-check suite that follows in a normal invocation.
        repeat (2) begin
            @(posedge clk);
            #(SAMPLE_DELAY_NS);
            expect_value(0, "trace reset");
        end
        @(negedge clk);
        rst = 1'b0;
        repeat ((warmup_frames + measure_frames) * 256) begin
            @(posedge clk);
            #(SAMPLE_DELAY_NS);
        end
        @(posedge clk);
        #(SAMPLE_DELAY_NS);
        trace_end_ns = $time - SAMPLE_DELAY_NS;
        $fclose(trace_fd);
        trace_fd = 0;
        $display("TRACE first_frame_ns=%0d measure_start_ns=%0d measure_end_ns=%0d duty=%0d enable=%0d",
                 (5 * CLK_PERIOD_NS) / 2,
                 (5 * CLK_PERIOD_NS) / 2 + warmup_frames * 256 * CLK_PERIOD_NS,
                 trace_end_ns, requested_duty, requested_enable);

        if (trace_only == 0)
            run_self_checks;
        $finish;
    end
endmodule
