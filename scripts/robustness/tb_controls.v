`timescale 1ns/1ps

// Real RTL control semantics only. Supply/POR behavior is not modeled here.
module tb_controls;
  reg clk = 0;
  reg rst = 1;
  reg [8:0] duty = 256;
  reg enable = 1;
  wire pwm;
  integer out, inputs, selected, unknowns = 0;
  reg [1023:0] out_name, input_name;
  pixel_pwm dut(.clk(clk), .rst(rst), .duty(duty), .enable(enable), .pwm(pwm));
  always #500 clk = ~clk;
  always @(pwm) begin
    if (pwm === 0 || pwm === 1) $fwrite(out, "%0d,%0d\n", $time, pwm);
    else if ($time > 500) unknowns = unknowns + 1;
  end
  initial begin
    if (!$value$plusargs("OUT=%s", out_name)) $fatal(1, "OUT required");
    if (!$value$plusargs("INPUTS=%s", input_name)) $fatal(1, "INPUTS required");
    if (!$value$plusargs("CASE=%d", selected)) $fatal(1, "CASE required");
    out = $fopen(out_name, "w"); inputs = $fopen(input_name, "w");
    $fwrite(out, "time_ns,pwm\n");
    $fwrite(inputs, "time_ns,rst,enable\n0,1,1\n");
    #2000 rst = 0; $fwrite(inputs,"2000,0,1\n");
    if (selected == 0) begin
      #18000 rst = 1; $fwrite(inputs,"20000,1,1\n");
      #10000 rst = 0; $fwrite(inputs,"30000,0,1\n");
    end else begin
      #18000 enable = 0; $fwrite(inputs,"20000,0,0\n");
      #280000 enable = 1; $fwrite(inputs,"300000,0,1\n");
    end
    #300000;
    if (unknowns) $fatal(1,"Unknown PWM events: %0d",unknowns);
    $display("PASS control trace CASE=%0d; synchronous reset; enable committed at frame boundary",selected);
    $fclose(out); $fclose(inputs); $finish;
  end
endmodule
