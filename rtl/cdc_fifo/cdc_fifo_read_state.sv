// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/cdc_fifo_read_state.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - F5: pointer Gray diregister, bukan dibentuk kombinasional dari biner
// Lihat docs/cdc_fifo.md dan docs/baseline_audit.md.

module cdc_fifo_read_state #(
  parameter ADDRESS_WIDTH = 4
) (
  input logic clock,
  input logic reset,
  input logic increment,
  input logic [ADDRESS_WIDTH-1:0] write_address_gray,

  output logic [ADDRESS_WIDTH-1:0] read_address,
  output logic [ADDRESS_WIDTH-1:0] read_address_gray,
  output logic empty
);

  logic [ADDRESS_WIDTH-1:0] write_address;

  gray_to_binary #(
    .WIDTH(ADDRESS_WIDTH)
  ) write_addr_decode (
    .gray(write_address_gray),
    .binary(write_address)
  );

  // F5: Gray dihitung dari pointer BERIKUTNYA lalu diregister bersama pointer
  // biner, sehingga yang menyeberang ke domain write hanya keluaran flop.
  // Nilainya di setiap siklus sama dengan gray(read_address).
  logic [ADDRESS_WIDTH-1:0] read_address_next;
  logic [ADDRESS_WIDTH-1:0] read_address_gray_next;
  assign read_address_next = read_address + 1'b1;

  binary_to_gray #(
    .WIDTH(ADDRESS_WIDTH)
  ) read_addr_encode (
    .binary(read_address_next),
    .gray(read_address_gray_next)
  );

  assign empty = (write_address == read_address);

  always_ff @ (posedge clock or posedge reset) begin
    if (reset) begin
      read_address      <= 0;
      read_address_gray <= 0;
    end else if (increment & !empty) begin
      read_address      <= read_address_next;
      read_address_gray <= read_address_gray_next;
    end
  end

endmodule
