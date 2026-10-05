// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/cdc_fifo_write_state.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - F3: pointer berikutnya dihitung dengan lebar eksplisit
//   - F4: pointer punya bit wrap (ADDRESS_WIDTH+1 bit), kapasitas 2^ADDRESS_WIDTH
//   - F5: pointer Gray diregister, bukan dibentuk kombinasional dari biner
// Lihat docs/cdc_fifo.md dan docs/baseline_audit.md.

module cdc_fifo_write_state #(
  parameter ADDRESS_WIDTH = 4
) (
  input logic clock,
  input logic reset,
  input logic increment,
  input logic [ADDRESS_WIDTH:0] read_pointer_gray,     // tersinkron, dari domain read

  output logic [ADDRESS_WIDTH-1:0] write_address,      // alamat RAM
  output logic [ADDRESS_WIDTH:0] write_pointer_gray,   // ke synchronizer domain read
  output logic full
);

  // F4: pointer ADDRESS_WIDTH+1 bit. Bit teratas adalah bit wrap: kalau bit
  // wrap berbeda dan bit sisanya sama, writer sudah satu putaran di depan
  // reader, artinya FIFO penuh dengan 2^ADDRESS_WIDTH item (semua slot terpakai).
  logic [ADDRESS_WIDTH:0] write_pointer;
  logic [ADDRESS_WIDTH:0] read_pointer;

  assign write_address = write_pointer[ADDRESS_WIDTH-1:0];

  gray_to_binary #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) read_ptr_decode (
    .gray(read_pointer_gray),
    .binary(read_pointer)
  );

  assign full = (write_pointer[ADDRESS_WIDTH] != read_pointer[ADDRESS_WIDTH]) &&
                (write_pointer[ADDRESS_WIDTH-1:0] == read_pointer[ADDRESS_WIDTH-1:0]);

  // F3: lebar penjumlahan eksplisit (tanpa literal 32 bit).
  logic [ADDRESS_WIDTH:0] write_pointer_next;
  assign write_pointer_next = write_pointer + 1'b1;

  // F5: Gray dihitung dari pointer BERIKUTNYA lalu diregister bersama pointer
  // biner. Yang menyeberang ke domain read hanya keluaran flop, sehingga tidak
  // ada glitch kombinasional di masukan synchronizer. Nilainya di setiap siklus
  // sama dengan gray(write_pointer).
  logic [ADDRESS_WIDTH:0] write_pointer_gray_next;

  binary_to_gray #(
    .WIDTH(ADDRESS_WIDTH + 1)
  ) write_ptr_encode (
    .binary(write_pointer_next),
    .gray(write_pointer_gray_next)
  );

  always_ff @ (posedge clock or posedge reset) begin
    if (reset) begin
      write_pointer      <= 0;
      write_pointer_gray <= 0;
    end else if (increment & !full) begin
      write_pointer      <= write_pointer_next;
      write_pointer_gray <= write_pointer_gray_next;
    end
  end

endmodule
