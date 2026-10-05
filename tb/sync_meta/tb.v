// Toplevel uji unit model metastabilitas synchronizer (rtl/cdc_fifo).
`default_nettype none
`timescale 1ns / 1ps

module tb ();
  reg        clk, rst;
  reg  [3:0] din;
  wire [3:0] dout;

  synchronizer #(.WIDTH(4)) dut (
      .clock(clk),
      .reset(rst),
      .in   (din),
      .out  (dout)
  );
endmodule
