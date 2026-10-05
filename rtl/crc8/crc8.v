// CRC-8 paralel, satu byte per siklus clock.
//
// Default POLY/INIT = CRC-8/SMBUS: x^8 + x^2 + x + 1 (0x07), nilai awal 0x00,
// MSB lebih dulu, tanpa refleksi, tanpa XOR akhir. Ini perilaku baseline TT07
// #0901 (tt_um_aidenfoxivey); lihat docs/crc8.md.

`default_nettype none

module crc8 #(
    parameter [7:0] POLY = 8'h07,
    parameter [7:0] INIT = 8'h00
) (
    input  wire       clk,
    input  wire       rst_n,  // reset asinkron, aktif rendah: crc <= INIT
    input  wire       clr,    // 1 = crc <= INIT pada tepi naik berikutnya (prioritas di atas en)
    input  wire       en,     // 1 = serap din pada tepi naik clk berikutnya
    input  wire [7:0] din,
    output reg  [7:0] crc
);

  // Delapan langkah LFSR (MSB dulu) di-unroll menjadi logika kombinasional.
  function automatic [7:0] crc8_next(input [7:0] c, input [7:0] d);
    integer i;
    reg [7:0] r;
    begin
      r = c ^ d;
      for (i = 0; i < 8; i = i + 1)
        r = r[7] ? ({r[6:0], 1'b0} ^ POLY) : {r[6:0], 1'b0};
      crc8_next = r;
    end
  endfunction

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      crc <= INIT;
    else if (clr)
      crc <= INIT;
    else if (en)
      crc <= crc8_next(crc, din);
  end

endmodule
