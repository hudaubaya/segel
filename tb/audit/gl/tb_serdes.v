// Toplevel audit gate-level: netlist tapeout TT07 #0200 (tt_um_serdes).
`default_nettype none
`timescale 1ns / 1ps

module tb_serdes ();
  reg        clk, rst_n, ena;
  reg  [7:0] ui_in, uio_in;
  wire [7:0] uo_out, uio_out, uio_oe;
  wire VPWR = 1'b1;
  wire VGND = 1'b0;

  tt_um_serdes dut (
      .VPWR   (VPWR),
      .VGND   (VGND),
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );
endmodule
