`timescale 1ns/1ps

// Functional receiver output is replayed here; no receiver RTL is implemented.
module tb_frame_replay;
  reg clk=0, rst=1, enable=0;
  reg [8:0] duty=0;
  wire pwm;
  integer source, trace, samples, frames, n, slot, d, e, count, checks=0;
  integer known=0, previous_time=-1, previous_value=0;
  reg [4095:0] source_name, trace_name, samples_name;
  pixel_pwm dut(.clk(clk), .rst(rst), .duty(duty), .enable(enable), .pwm(pwm));
  always #500 clk=~clk;
  always @(pwm) begin
    if (pwm===0 || pwm===1) begin
      if (clk!==1 || ($time % 1000)!=500) $fatal(1,"Off-clock PWM event");
      if (known && ($time-previous_time)<1000) $fatal(1,"Short PWM event");
      known=1; previous_time=$time; previous_value=pwm;
      $fwrite(trace,"%0d,%0d\n",$time,pwm);
    end else if (known) $fatal(1,"Unknown PWM after reset");
  end
  initial begin
    if (!$value$plusargs("SOURCE=%s",source_name) || !$value$plusargs("OUT=%s",trace_name)
        || !$value$plusargs("SAMPLES=%s",samples_name) || !$value$plusargs("FRAMES=%d",frames))
      $fatal(1,"Replay arguments required");
    source=$fopen(source_name,"r"); trace=$fopen(trace_name,"w"); samples=$fopen(samples_name,"w");
    if (!source || !trace || !samples) $fatal(1,"Replay file unavailable");
    $fwrite(trace,"time_ns,pwm\n");
    $fwrite(samples,"time_ns,frame,slot,pwm\n");
    repeat(2) begin @(posedge clk); #1; if(pwm!==0) $fatal(1,"Reset failed"); end
    for(n=0;n<frames;n=n+1) begin
      @(negedge clk);
      count=$fscanf(source,"%d %d\n",d,e);
      if(count!=2 || d<0 || d>256 || e<0 || e>1) $fatal(1,"Invalid replay row");
      duty=d; enable=e; rst=0;
      for(slot=0;slot<256;slot=slot+1) begin
        @(posedge clk); #1;
        if(pwm!==(e && slot<d)) $fatal(1,"PWM slot differs from replay command");
        checks=checks+1;
        $fwrite(samples,"%0d,%0d,%0d,%0d\n",$time,n,slot,pwm);
      end
    end
    // Reach the exact end of the final complete frame before stopping.
    @(posedge clk); #1;
    $display("PASS replay: %0d frames, %0d slot checks",frames,checks);
    $fclose(source); $fclose(trace); $fclose(samples); $finish;
  end
endmodule
