`timescale 1ns/1ps
// Run with the unmodified baseline tb_pixel_pwm as a second simulation root.
module safety_normal_observer;
    reg fault = 1'b1;
    reg recover_request = 1'b0;
    wire permit;
    wire protected_pwm;
    integer checks = 0;
    pixel_safety interlock(tb_pixel_pwm.clk, fault, recover_request,
                          tb_pixel_pwm.pwm, permit, protected_pwm);
    initial begin
        #100 fault=0;
        #900 recover_request=1;
        #2000 recover_request=0;
    end
    always @(posedge tb_pixel_pwm.clk) begin
        #2;
        if ($time >= 3500) begin
            checks=checks+1;
            if (permit !== 1'b1 || protected_pwm !== tb_pixel_pwm.pwm)
                $fatal(1,"Safety altered fault-free normal PWM");
        end
    end
    final begin
        if (checks < 130000) $fatal(1,"Incomplete normal safety observation");
        $display("SAFETY_NORMAL_PASS checks=%0d",checks);
    end
endmodule
