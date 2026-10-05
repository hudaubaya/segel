// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/cdc_fifo_read_state.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - F4: pointer punya bit wrap (ADDRESS_WIDTH+1 bit), kapasitas 2^ADDRESS_WIDTH
//   - F5: pointer Gray diregister, bukan dibentuk kombinasional dari biner
// Lihat docs/cdc_fifo.md dan docs/baseline_audit.md.

module cdc_fifo_read_state #(
  parameter ADDRESS_WIDTH = 4
) (
  input logic clock,
  input logic reset,
  input logic increment,
  input logic [ADDRESS_WIDTH:0] write_pointer_gray,    // tersinkron, dari domain write

  output logic [ADDRESS_WIDTH-1:0] read_address,       // alamat RAM
  output logic [ADDRESS_WIDTH:0] read_pointer_gray,    // ke synchronizer domain write
  output logic empty
);

  logic [ADDRESS_WIDTH:0] read_pointer;
  logic [ADDRESS_WIDTH:0] write_pointer;

  assign read_address = read_pointer[ADDRESS_WIDTH-1:0];

  gray_to_binary #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) write_ptr_decode (
    .gray(write_pointer_gray),
    .binary(write_pointer)
  );

  // F4: kosong hanya kalau seluruh pointer sama, termasuk bit wrap.
  assign empty = (write_pointer == read_pointer);

  // F5: Gray dihitung dari pointer BERIKUTNYA lalu diregister bersama pointer
  // biner, sehingga yang menyeberang ke domain write hanya keluaran flop.
  // Nilainya di setiap siklus sama dengan gray(read_pointer).
  logic [ADDRESS_WIDTH:0] read_pointer_next;
  logic [ADDRESS_WIDTH:0] read_pointer_gray_next;
  assign read_pointer_next = read_pointer + 1'b1;

  binary_to_gray #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) read_ptr_encode (
    .binary(read_pointer_next),
    .gray(read_pointer_gray_next)
  );

  always_ff @ (posedge clock or posedge reset) begin
    if (reset) begin
      read_pointer      <= 0;
      read_pointer_gray <= 0;
    end else if (increment & !empty) begin
      read_pointer      <= read_pointer_next;
      read_pointer_gray <= read_pointer_gray_next;
    end
  end

endmodule
