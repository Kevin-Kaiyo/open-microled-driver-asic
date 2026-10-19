`timescale 1ns/1ps
module tb_control_sdf;
 reg clk=0,run_clk=1,rst=1,enable=1,fault=0,recover_request=0;
 reg[8:0] duty=0;
 wire raw_pwm,permit,protected_monitor;
 integer checks=0,fd,k,n,on_count; real fault_time,shutdown_ns;
 reg[8191:0] sdf_path,out_path;
 pixel_control_v3 dut(.clk(clk),.rst(rst),.duty(duty),.enable(enable),.fault(fault),.recover_request(recover_request),.raw_pwm(raw_pwm),.permit(permit),.protected_monitor(protected_monitor));
 always #500 if(run_clk) clk=~clk;
 always @(raw_pwm or permit or protected_monitor or fault or recover_request or run_clk or rst)
  if(fd) $fdisplay(fd,"%0.3f,%b,%b,%b,%b,%b,%b,%b,%b",$realtime,raw_pwm,protected_monitor,permit,fault,run_clk,rst,enable,recover_request);
 task ck; input ok; input[511:0] label; begin checks=checks+1;if(ok!==1'b1)$fatal(1,"%0s @%0.3f",label,$realtime);end endtask
 initial begin
  if(!$value$plusargs("SDF=%s",sdf_path))$fatal(1,"SDF required");
  if(!$value$plusargs("OUT=%s",out_path))out_path="events.csv";
  $sdf_annotate(sdf_path,dut);
  fd=$fopen(out_path,"w");$fdisplay(fd,"time_ns,raw_pwm,protected_pwm,permit,fault,clk_run,rst,enable,recover_request");
  #1 fault=1;
  #100 ck(permit===0 && protected_monitor===0,"Initial fault asserts");
  #1099 fault=0; recover_request=1;
  repeat(3) @(posedge clk);
  #100 ck(permit===1,"Explicit safe recovery");
  @(negedge clk); recover_request=0;
  for(k=0;k<4;k=k+1) begin
   rst=1; case(k) 0:duty=0;1:duty=1;2:duty=64;3:duty=256;endcase
   repeat(2) @(posedge clk);
   @(negedge clk);rst=0;on_count=0;
   for(n=0;n<512;n=n+1)begin
    @(posedge clk);#100;
    ck(raw_pwm===((n%256)<duty),"Routed PWM slot value");
    ck(protected_monitor===raw_pwm && permit===1,"Routed permit monitor");
    if(raw_pwm)on_count=on_count+1;
   end
   ck(on_count==2*duty,"Exact 2-frame duty");
   @(negedge clk);
  end
  // Stop with raw PWM high, then assert fault between clock edges.
  #100 run_clk=0;
  #125 ck(raw_pwm===1,"Stopped raw high");fault_time=$realtime;fault=1;
  wait(protected_monitor===0);shutdown_ns=$realtime-fault_time;
  #100 ck(permit===0 && shutdown_ns<100,"Asynchronous shutoff below100ns");
  #3000 fault=0;recover_request=1;
  #2000 ck(permit===0 && protected_monitor===0,"No recovery stopped clock");
  run_clk=1;
  repeat(3)@(posedge clk);#100;ck(permit===0,"No recovery raw high");
  @(negedge clk);rst=1;
  repeat(3)@(posedge clk);#100;ck(permit===1 && raw_pwm===0,"Recovery qualified low");
  @(negedge clk);rst=0;recover_request=0;
  @(posedge clk);#100;ck(raw_pwm===1 && protected_monitor===1,"Recovery resumes");
  $fclose(fd);$display("CONTROL_SDF_PASS checks=%0d fault_delay_ns=%0.3f",checks,shutdown_ns);$finish;
 end
endmodule
