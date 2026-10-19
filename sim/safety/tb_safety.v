`timescale 1ns/1ps
module tb_safety;
    reg clk=0, clk_run=1, rst=1, enable=1;
    reg [8:0] duty=256;
    reg fault=1, recover_request=0;
    wire raw_pwm, permit, protected_pwm;
    reg sync_inhibit=1;
    wire sync_only_pwm=raw_pwm && !sync_inhibit;
    integer requested_duty=256, fault_ns=520125, stop_ns=-1;
    integer stop_time_ns=540000, fd=0, checks=0;
    integer initial_fault_clear_ns=100, initial_offset=0;
    integer fault_in_off_phase=0;
    reg [4095:0] output_path="events.csv";
    pixel_pwm base(clk,rst,duty,enable,raw_pwm);
    pixel_safety safety(clk,fault,recover_request,raw_pwm,permit,protected_pwm);
    always #500 if(clk_run) clk=~clk;
    // Deliberately insufficient clock-dependent protection for a negative control.
    always @(posedge clk) begin
        if(fault) sync_inhibit<=1;
        else if(recover_request && !raw_pwm) sync_inhibit<=0;
    end
    always @(raw_pwm or permit or protected_pwm or fault or recover_request or
             sync_only_pwm or clk_run or rst or enable) begin
        if(fd) $fdisplay(fd,"%0.3f,%b,%b,%b,%b,%b,%b,%b,%b,%b",
            $realtime,raw_pwm,protected_pwm,permit,fault,sync_only_pwm,
            clk_run,rst,enable,recover_request);
    end
    task check_value;
        input condition;
        input [511:0] label;
        begin
            checks=checks+1;
            if(condition !== 1'b1) $fatal(1,"%0s time=%0.3f",label,$realtime);
        end
    endtask
    initial begin
        if($value$plusargs("DUTY=%d",requested_duty)) begin end
        if($value$plusargs("FAULT_NS=%d",fault_ns)) begin end
        if($value$plusargs("STOP_NS=%d",stop_ns)) begin end
        if($value$plusargs("STOP_TIME_NS=%d",stop_time_ns)) begin end
        if($value$plusargs("OUT=%s",output_path)) begin end
        if($value$plusargs("INITIAL_FAULT_CLEAR_NS=%d",initial_fault_clear_ns)) begin end
        initial_offset=initial_fault_clear_ns-100;
        duty=requested_duty;
        fd=$fopen(output_path,"w");
        if(!fd) $fatal(1,"Cannot open events");
        $fdisplay(fd,"time_ns,raw_pwm,protected_pwm,permit,fault,sync_only_pwm,clk_run,rst,enable,recover_request");
        #1 check_value(protected_pwm===0,"Asserted initial fault defaults off");
        #(initial_fault_clear_ns-1) fault=0;
        #900 recover_request=1;
        #1000 rst=0; recover_request=0;
        #1 check_value(permit===1,"Explicit initial recovery while raw low");
        if(fault_ns>=0) begin
            if(stop_ns>=0) begin
                #(stop_ns-2001-initial_offset) clk_run=0;
                #1 check_value(raw_pwm===1,"Stopped-clock raw PWM stuck high");
                #(fault_ns-stop_ns-1);
            end else #(fault_ns-2001-initial_offset);
            fault_in_off_phase=(raw_pwm===0);
            fault=1;
            #1;
            check_value(protected_pwm===0,"Asynchronous fault bypasses clock/frame");
            check_value(permit===0,"Fault asynchronously inhibits recovery state");
            if(stop_ns>=0)
                check_value(sync_only_pwm===1,"Stopped-clock synchronous-only negative control remains ON");
            #2999 fault=0;
            #1 check_value(protected_pwm===0 && permit===0,"Fault removal alone cannot recover");
            recover_request=1;
            if(stop_ns>=0) begin
                #1999 check_value(protected_pwm===0 && permit===0,"No recovery while clock stopped");
                clk_run=1;
            end else #1999;
            if(!fault_in_off_phase && requested_duty>=64)
                check_value(permit===0,"High raw PWM cannot qualify recovery");
            // Synchronous reset clears raw PWM; explicit recovery can then be accepted.
            rst=1;
            repeat(3) @(posedge clk);
            #1;
            check_value(raw_pwm===0 && protected_pwm===0 && permit===1,"Qualified recovery is still dark while raw reset");
            @(negedge clk); rst=0; recover_request=0;
            @(posedge clk); #1;
            check_value(protected_pwm===raw_pwm,"Recovered output follows normal PWM");
        end
        if($time<stop_time_ns) #(stop_time_ns-$time);
        $fclose(fd);
        $display("SAFETY_CASE_PASS duty=%0d fault_ns=%0d stop_ns=%0d off_phase=%0d checks=%0d",
                 requested_duty,fault_ns,stop_ns,fault_in_off_phase,checks);
        $finish;
    end
endmodule
