// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/cdc_fifo_write_state.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - F3: perbandingan full memakai pointer berikutnya selebar ADDRESS_WIDTH
//   - F5: pointer Gray diregister, bukan dibentuk kombinasional dari biner
// Lihat docs/cdc_fifo.md dan docs/baseline_audit.md.

module cdc_fifo_write_state #(
  parameter ADDRESS_WIDTH = 4
) (
  input logic clock,
  input logic reset,
  input logic increment,
  input logic [ADDRESS_WIDTH-1:0] read_address_gray,

  output logic [ADDRESS_WIDTH-1:0] write_address,
  output logic [ADDRESS_WIDTH-1:0] write_address_gray,
  output logic full
);

  // F3: pointer berikutnya dihitung dengan lebar ADDRESS_WIDTH agar membungkus
  // ke 0. Dengan literal 1 tak berukuran, penjumlahan dihitung 32 bit sehingga
  // 31 + 1 = 32 != 0 dan full tidak pernah naik saat pointer read = 0.
  logic [ADDRESS_WIDTH-1:0] write_address_next;
  assign write_address_next = write_address + 1'b1;
  assign full = (write_address_next == read_address);

  logic [ADDRESS_WIDTH-1:0] read_address;

  gray_to_binary #(
    .WIDTH(ADDRESS_WIDTH)
  ) read_addr_decode (
    .gray(read_address_gray),
    .binary(read_address)
  );

  // F5: Gray dihitung dari pointer BERIKUTNYA lalu diregister bersama pointer
  // biner. Yang menyeberang ke domain read hanya keluaran flop, sehingga tidak
  // ada glitch kombinasional di masukan synchronizer. Nilainya di setiap siklus
  // sama dengan gray(write_address).
  logic [ADDRESS_WIDTH-1:0] write_address_gray_next;

  binary_to_gray #(
    .WIDTH(ADDRESS_WIDTH)
  ) write_addr_encode (
    .binary(write_address_next),
    .gray(write_address_gray_next)
  );

  always_ff @ (posedge clock or posedge reset) begin
    if (reset) begin
      write_address      <= 0;
      write_address_gray <= 0;
    end else if (increment & !full) begin
      write_address      <= write_address_next;
      write_address_gray <= write_address_gray_next;
    end
  end

endmodule
