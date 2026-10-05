// Toplevel cocotb untuk netlist Cyclone V CDC FIFO (build/cyclonev/, hasil
// Yosys synth_intel_alm). Nama sinyal c_* sama dengan tb/cdc_fifo/tb.v agar
// bench bersama (tb/common/cdc_fifo_bench.py) bisa dipakai. Hanya inti FIFO;
// wrapper TT tidak relevan untuk FPGA.
`default_nettype none
`timescale 1ns / 1ps

module tb ();

`ifdef WAVES
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
  end
`endif

  reg        c_wclk, c_wrst, c_winc, c_rclk, c_rrst, c_rinc;
  reg  [3:0] c_wdata;
  wire [3:0] c_rdata;
  wire       c_full, c_empty;

  cdc_fifo core (
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
