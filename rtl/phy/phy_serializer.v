// Serializer PHY (domain tx_clk): ambil simbol 9 bit dari FIFO (first-word
// fall-through), kodekan 8b/10b, kirim MSB (`a`) dulu, satu bit per tx_clk.
// FIFO kosong -> kirim IDLE (K28.5), sehingga aliran tidak pernah berhenti dan
// penerima selalu mendapat comma untuk penyelarasan.
//
// Clock diteruskan: clk_out = ~tx_clk. Data berubah di tepi naik tx_clk, jadi
// tepi naik clk_out jatuh di tengah bit (center-aligned). Di silikon/FPGA ini
// harus dibuat dengan sel output DDR/clock-forwarding, bukan gerbang inverter
// (docs/phy.md).

`default_nettype none

module phy_serializer (
    input  wire       tx_clk,
    input  wire       rst,          // aktif tinggi, tersinkron ke tx_clk
    input  wire       fifo_empty,
    input  wire [8:0] fifo_data,    // {k, byte}
    output wire       fifo_pop,
    output wire       ser_out,
    output wire       clk_out
);

`include "phy_symbols.vh"

    reg [3:0] bitcnt;
    reg [9:0] sh;
    reg       rd;

    wire       load = (bitcnt == 4'd9);
    wire [7:0] sym  = fifo_empty ? SYM_IDLE : fifo_data[7:0];
    wire       symk = fifo_empty ? 1'b1     : fifo_data[8];
    wire [9:0] code;
    wire       rd_next, k_err;

    enc8b10b u_enc (
        .din(sym), .k(symk), .rd_in(rd), .code(code), .rd_out(rd_next), .k_err(k_err)
    );

    assign fifo_pop = load && !fifo_empty;
    assign ser_out  = sh[9];
    assign clk_out  = ~tx_clk;

    always @(posedge tx_clk or posedge rst) begin
        if (rst) begin
            bitcnt <= 4'd9;          // simbol pertama dimuat di tepi pertama setelah reset
            sh     <= 10'd0;
            rd     <= 1'b0;          // RD- setelah reset
        end else if (load) begin
            sh     <= code;
            rd     <= rd_next;
            bitcnt <= 4'd0;
        end else begin
            sh     <= {sh[8:0], 1'b0};
            bitcnt <= bitcnt + 4'd1;
        end
    end

endmodule

`default_nettype wire
