// Pemeriksaan F5 (docs/baseline_audit.md): pointer Gray pada netlist tapeout
// #0036, diamati di masukan D flop pertama synchronizer, dengan UNIT_DELAY=#1.
// Sampling tiap 0.25 ns: perubahan antar sampel yang bukan 1 bit = glitch yang
// lebarnya >= 1 unit delay. Juga memeriksa net == gray(biner) di tepi clock.
// Bukan cocotb: nama net netlist memakai identifier escaped. Jalankan lewat
// `make test-audit-gl-gray`.
`timescale 1ns/1ps
module gray_glitch;
  reg wclk = 0, winc = 0, rclk = 0, rinc = 0, wrst_n = 0, rrst_n = 0;
  reg [3:0] wd = 0;
  wire [7:0] uo, uio_out, uio_oe;
  wire VPWR = 1'b1, VGND = 1'b0;

  tt_um_pa1mantri_cdc_fifo dut (
      .VPWR(VPWR), .VGND(VGND),
      .ui_in({wd, rinc, rclk, winc, wclk}), .uo_out(uo),
      .uio_in({6'b0, rrst_n, wrst_n}), .uio_out(uio_out), .uio_oe(uio_oe),
      .ena(1'b1), .clk(1'b0), .rst_n(1'b1));

  always #50 wclk = ~wclk;
  always #37 rclk = ~rclk;

  // Masukan D flop pertama synchronizer (bit 4 = bit 4 biner, net8 = buffer-nya)
  wire [4:0] wg = {dut.net8, dut.\fifo.write_address_gray_presync[3] ,
                   dut.\fifo.write_address_gray_presync[2] , dut.\fifo.write_address_gray_presync[1] ,
                   dut.\fifo.write_address_gray_presync[0] };
  wire [4:0] rg = {dut.\fifo.fifo_memory.read_address[4] , dut.\fifo.read_address_gray_presync[3] ,
                   dut.\fifo.read_address_gray_presync[2] , dut.\fifo.read_address_gray_presync[1] ,
                   dut.\fifo.read_address_gray_presync[0] };
  wire [4:0] wbin = {dut.\fifo.fifo_memory.write_address[4] , dut.\fifo.fifo_memory.write_address[3] ,
                     dut.\fifo.fifo_memory.write_address[2] , dut.\fifo.fifo_memory.write_address[1] ,
                     dut.\fifo.fifo_memory.write_address[0] };
  wire [4:0] rbin = {dut.\fifo.fifo_memory.read_address[4] , dut.\fifo.fifo_memory.read_address[3] ,
                     dut.\fifo.fifo_memory.read_address[2] , dut.\fifo.fifo_memory.read_address[1] ,
                     dut.\fifo.fifo_memory.read_address[0] };

  function integer popcount(input [4:0] a);
    integer i;
    begin
      popcount = 0;
      for (i = 0; i < 5; i = i + 1) popcount = popcount + a[i];
    end
  endfunction

  integer armed = 0, glw = 0, glr = 0, mw = 0, mr = 0, chw = 0, chr = 0;
  reg [4:0] sw, sr;

  always @(posedge wclk) if (armed && wg !== (wbin ^ (wbin >> 1))) mw = mw + 1;
  always @(posedge rclk) if (armed && rg !== (rbin ^ (rbin >> 1))) mr = mr + 1;

  always #0.25 if (armed) begin
    if (wg !== sw) begin chw = chw + 1; if (popcount(wg ^ sw) != 1) glw = glw + 1; sw = wg; end
    if (rg !== sr) begin chr = chr + 1; if (popcount(rg ^ sr) != 1) glr = glr + 1; sr = rg; end
  end

  integer i;
  initial begin
    #600 wrst_n = 1; rrst_n = 1;
    #600 sw = wg; sr = rg; armed = 1;
    for (i = 0; i < 4000; i = i + 1) @(negedge wclk) begin winc = 1; rinc = 1; end
    $display("perubahan gray write=%0d read=%0d; glitch multi-bit write=%0d read=%0d; net!=gray(biner) write=%0d read=%0d",
             chw, chr, glw, glr, mw, mr);
    if (chw < 1000 || chr < 1000 || glw || glr || mw || mr) begin
      $display("FAIL gray_glitch");
      $fatal(1);
    end
    $display("PASS gray_glitch");
    $finish;
  end
endmodule
