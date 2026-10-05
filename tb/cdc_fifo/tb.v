// Toplevel cocotb untuk CDC FIFO SEGEL (rtl/cdc_fifo/, perbaikan F1 dan F3).
// Dua instance independen:
//   top  : wrapper tt_um_pa1mantri_cdc_fifo, diakses lewat pin TT
//   core : cdc_fifo #(DATA_WIDTH=4, ADDRESS_WIDTH=5) langsung, parameter sama
//          dengan yang dipakai wrapper, untuk menguji logika FIFO tanpa wrapper
`default_nettype none
`timescale 1ns / 1ps

module tb ();

`ifdef WAVES
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
  end
`endif

  // --- wrapper TT ---------------------------------------------------------
  reg        t_wclk, t_winc, t_rclk, t_rinc;
  reg  [3:0] t_wdata;
  reg        t_wrst_n, t_rrst_n;   // uio_in[0], uio_in[1]: aktif rendah
  reg        clk, rst_n, ena;
  wire [7:0] uo_out, uio_out, uio_oe;

  tt_um_aduhayabu_cdc_fifo top (
      .ui_in  ({t_wdata, t_rinc, t_rclk, t_winc, t_wclk}),
      .uo_out (uo_out),
      .uio_in ({6'b0, t_rrst_n, t_wrst_n}),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  wire       t_empty = uo_out[0];
  wire       t_full  = uo_out[1];
  wire [3:0] t_rdata = uo_out[7:4];

  // --- inti cdc_fifo ------------------------------------------------------
  reg        c_wclk, c_wrst, c_winc, c_rclk, c_rrst, c_rinc;
  reg  [3:0] c_wdata;
  wire [3:0] c_rdata;
  wire       c_full, c_empty;

  cdc_fifo #(
      .DATA_WIDTH   (4),
      .ADDRESS_WIDTH(5)
  ) core (
      .write_clock    (c_wclk),
      .write_reset    (c_wrst),
      .write_data     (c_wdata),
      .write_increment(c_winc),
      .full           (c_full),
      .read_clock     (c_rclk),
      .read_reset     (c_rrst),
      .read_increment (c_rinc),
      .read_data      (c_rdata),
      .empty          (c_empty)
  );

endmodule
