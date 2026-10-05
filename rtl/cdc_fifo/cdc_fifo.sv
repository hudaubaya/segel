// FIFO for passing registers across clock domains

// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/cdc_fifo.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - reset tiap domain melewati reset_synchronizer (assert asinkron,
//     deassert sinkron ke clock domain itu)
//   - F6: reset dari domain mana pun mereset KEDUA domain, sehingga pointer
//     kedua sisi tidak pernah tidak konsisten
//   - F4: pointer lintas domain ADDRESS_WIDTH+1 bit (dengan bit wrap), sehingga
//     kapasitas penuh 2^ADDRESS_WIDTH
// Lihat docs/cdc_fifo.md.

//`include "dpram.sv"
//`include "synchronizer.sv"
//`include "cdc_fifo_read_state.sv"
//`include "cdc_fifo_write_state.sv"
//`include "binary_to_gray.sv"
//`include "gray_to_binary.sv"

module cdc_fifo #(
  parameter DATA_WIDTH = 8,
  parameter ADDRESS_WIDTH = 4
) (
  // Sender side signals/buses
  input logic write_clock,
  input logic write_reset,
  input logic [DATA_WIDTH-1:0] write_data,
  input logic write_increment,
  output logic full,

  // Receiver side signals/buses
  input logic read_clock,
  input logic read_reset,
  input logic read_increment,
  output logic [DATA_WIDTH-1:0] read_data,
  output logic empty
);

  wire write_enable;
  wire [ADDRESS_WIDTH-1:0] write_address;
  wire [ADDRESS_WIDTH:0] write_address_gray_presync;   // F4: + bit wrap
  wire [ADDRESS_WIDTH:0] write_address_gray_postsync;
  wire [ADDRESS_WIDTH-1:0] read_address;
  wire [ADDRESS_WIDTH:0] read_address_gray_presync;
  wire [ADDRESS_WIDTH:0] read_address_gray_postsync;

  assign write_enable = (!full & write_increment);

  // F6: kedua domain selalu direset bersama. Mereset hanya satu sisi saat FIFO
  // berisi membuat pointer kedua sisi tidak konsisten (data lama terbaca lagi
  // atau isi memori basi terbaca). Reset masuk ke kedua domain secara asinkron
  // dan dilepas sinkron ke clock masing-masing. Urutan pelepasan aman: domain
  // yang masih reset menahan pointer-nya di 0, dan itu konsisten dengan FIFO
  // kosong yang dilihat domain lainnya.
  logic fifo_reset;
  assign fifo_reset = write_reset | read_reset;

  // Reset per domain: assert asinkron, deassert sinkron ke clock domain itu.
  // Semua flop ber-reset di bawah ini memakai versi tersinkron.
  logic write_reset_sync, read_reset_sync;

  reset_synchronizer write_reset_synchronizer (
    .clock(write_clock),
    .reset_in(fifo_reset),
    .reset_out(write_reset_sync)
  );

  reset_synchronizer read_reset_synchronizer (
    .clock(read_clock),
    .reset_in(fifo_reset),
    .reset_out(read_reset_sync)
  );

  dpram #(
    .DATA_WIDTH(DATA_WIDTH),
    .ADDRESS_WIDTH(ADDRESS_WIDTH)
  ) fifo_memory (
    .clock(write_clock),
    .write_address(write_address),
    .write_data(write_data),
    .write_enable(write_enable),
    .read_address(read_address),
    .read_data(read_data)
  );

  cdc_fifo_write_state #(
    .ADDRESS_WIDTH(ADDRESS_WIDTH)
  ) writestate (
    .clock(write_clock),
    .reset(write_reset_sync),
    .increment(write_increment),
    .read_pointer_gray(read_address_gray_postsync),
    .write_address(write_address),
    .write_pointer_gray(write_address_gray_presync),
    .full(full)
  );

  cdc_fifo_read_state #(
    .ADDRESS_WIDTH(ADDRESS_WIDTH)
  ) readstate (
   .clock(read_clock),
   .reset(read_reset_sync),
   .increment(read_increment),
   .write_pointer_gray(write_address_gray_postsync),
   .read_address(read_address),
   .read_pointer_gray(read_address_gray_presync),
   .empty(empty)
  );

  synchronizer #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) write_address_sync (
    .clock(read_clock),
    .reset(read_reset_sync),
    .in(write_address_gray_presync),
    .out(write_address_gray_postsync)
  );

  synchronizer #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) read_address_sync (
    .clock(write_clock),
    .reset(write_reset_sync),
    .in(read_address_gray_presync),
    .out(read_address_gray_postsync)
  );

endmodule
