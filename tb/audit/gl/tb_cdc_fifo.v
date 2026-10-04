// Toplevel audit gate-level: netlist tapeout TT07 #0036 (tt_um_pa1mantri_cdc_fifo).
`default_nettype none
`timescale 1ns / 1ps

module tb_cdc_fifo ();
  reg        t_wclk, t_winc, t_rclk, t_rinc, t_wrst_n, t_rrst_n;
  reg  [3:0] t_wdata;
  wire [7:0] uo_out, uio_out, uio_oe;
  wire VPWR = 1'b1;
  wire VGND = 1'b0;

  tt_um_pa1mantri_cdc_fifo dut (
      .VPWR   (VPWR),
      .VGND   (VGND),
      .ui_in  ({t_wdata, t_rinc, t_rclk, t_winc, t_wclk}),
      .uo_out (uo_out),
      .uio_in ({6'b0, t_rrst_n, t_wrst_n}),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (1'b1),
      .clk    (1'b0),
      .rst_n  (1'b1)
  );

  wire       t_empty = uo_out[0];
  wire       t_full  = uo_out[1];
  wire [3:0] t_rdata = uo_out[7:4];
endmodule
