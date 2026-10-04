// Toplevel cocotb untuk CRC-8.
//   default      : RTL SEGEL (tt_um_hu_crc8)
//   -DGL_TEST    : netlist gate-level baseline TT07 #0901 (tt_um_aidenfoxivey)
// Keduanya diuji dengan test.py yang sama, jadi lulus di keduanya berarti
// perilaku RTL sama dengan desain yang di-tapeout untuk semua vektor uji.

`default_nettype none
`timescale 1ns / 1ps

module tb ();

`ifdef WAVES
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
  end
`endif

  reg        clk;
  reg        rst_n;
  reg        ena;
  reg  [7:0] ui_in;
  reg  [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;

  tt_um_aidenfoxivey dut (
      .VPWR   (VPWR),
      .VGND   (VGND),
`else
  tt_um_hu_crc8 dut (
`endif
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
