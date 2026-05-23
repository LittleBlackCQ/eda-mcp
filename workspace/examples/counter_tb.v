`timescale 1ns / 1ps

module counter_tb;
    reg clk = 0;
    reg rst_n = 0;
    wire [3:0] q;

    counter dut (.clk(clk), .rst_n(rst_n), .q(q));

    always #5 clk = ~clk;

    initial begin
        $dumpfile("counter.vcd");
        $dumpvars(0, counter_tb);
        #12 rst_n = 1;
        #200;
        $display("final q = %0d", q);
        $finish;
    end
endmodule
