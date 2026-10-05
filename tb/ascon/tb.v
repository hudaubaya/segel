// Wrapper cocotb untuk ascon_core + pemeriksa bocoran per siklus.
//
// leak_cnt bertambah di setiap tepi naik clock di mana:
//   - dout != 0 saat dout_valid = 0
//   - operasi dekripsi: dout_valid = 1 sebelum auth_ok = 1
//   - operasi dekripsi: tag_out != 0 (tag hasil hitung tidak boleh keluar)
// test.py membaca selisih leak_cnt per operasi dan mensyaratkan 0.
// Clock dibangkitkan di sini (periode 10 ns).
// evt dipakai test.py untuk melompati siklus tanpa transfer (permutasi berjalan).

`default_nettype none
`timescale 1ns / 1ps

module tb #(
    parameter integer PT_BUF_BLOCKS = 512
) (
    output reg          clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire [1:0]   mode,
    input  wire [127:0] key,
    input  wire [127:0] key2,
    input  wire [127:0] nonce,
    input  wire [127:0] tag_in,
    input  wire [7:0]   tag_bits,
    input  wire [31:0]  xof_bits,
    output wire         busy,
    output wire         done,
    output wire [127:0] tag_out,
    output wire         auth_ok,
    output wire         err,
    input  wire         din_valid,
    output wire         din_ready,
    input  wire [127:0] din,
    input  wire [7:0]   din_bits,
    input  wire         din_last,
    output wire         dout_valid,
    input  wire         dout_ready,
    output wire [127:0] dout,
    output wire [7:0]   dout_bits,
    output reg  [31:0]  leak_cnt,
    output wire         evt          // ada transfer masuk/keluar atau done di tepi berikutnya
);

    ascon_core #(.PT_BUF_BLOCKS(PT_BUF_BLOCKS)) u_core (
        .clk(clk), .rst_n(rst_n), .start(start), .mode(mode), .key(key), .key2(key2),
        .nonce(nonce), .tag_in(tag_in), .tag_bits(tag_bits), .xof_bits(xof_bits),
        .busy(busy), .done(done), .tag_out(tag_out), .auth_ok(auth_ok), .err(err),
        .din_valid(din_valid), .din_ready(din_ready), .din(din), .din_bits(din_bits),
        .din_last(din_last), .dout_valid(dout_valid), .dout_ready(dout_ready), .dout(dout),
        .dout_bits(dout_bits)
    );

    assign evt = done || (din_valid && din_ready) || (dout_valid && dout_ready);

    // Clock 100 MHz dibangkitkan di Verilog, bukan cocotb.Clock (yang di cocotb 1.8
    // membangunkan Python dua kali per siklus).
    initial clk = 1'b0;
    always #5 clk = ~clk;

    reg [1:0] op_mode;
    initial begin
        leak_cnt = 32'd0;
        op_mode  = 2'd0;
    end

    always @(posedge clk) begin
        if (start && !busy) op_mode <= mode;
        if (rst_n) begin
            if (!dout_valid && dout != 128'd0)
                leak_cnt <= leak_cnt + 32'd1;
            else if (op_mode == 2'd1 && dout_valid && !auth_ok)
                leak_cnt <= leak_cnt + 32'd1;
            else if (op_mode == 2'd1 && tag_out != 128'd0)
                leak_cnt <= leak_cnt + 32'd1;
        end
    end

endmodule

`default_nettype wire
