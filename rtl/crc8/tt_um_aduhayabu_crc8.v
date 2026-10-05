// Wrapper Tiny Tapeout untuk crc8. Pinout sama dengan baseline TT07 #0901
// (tt_um_aidenfoxivey), sehingga bisa menggantikannya langsung:
//   ui_in[7:0]  byte masukan
//   uio_in[0]   enable (1 = serap ui_in pada tepi naik clk)
//   uo_out[7:0] nilai CRC saat ini
// ena dan uio_in[7:1] tidak dipakai; uio_out/uio_oe selalu 0.

`default_nettype none

module tt_um_aduhayabu_crc8 (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  crc8 u_crc8 (
      .clk  (clk),
      .rst_n(rst_n),
      .clr  (1'b0),
      .en   (uio_in[0]),
      .din  (ui_in),
      .crc  (uo_out)
  );

  assign uio_out = 8'h00;
  assign uio_oe  = 8'h00;

  wire _unused = &{ena, uio_in[7:1], 1'b0};

endmodule
