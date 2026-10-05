// Framer TX (domain sistem): payload -> SOF, payload, CRC-8, EOF, IDLE, IDLE ke FIFO TX.
//
// Dua IDLE (K28.5) setelah setiap frame menjamin penerima mendapat dua comma
// berurutan di antara frame walaupun FIFO TX tidak pernah kosong (lalu lintas
// padat): itu syarat aligner untuk mengonfirmasi realign dan pulih dari slip.
//
// Antarmuka payload: tx_data/tx_valid/tx_ready, tx_last pada byte terakhir.
// Payload minimal 1 byte. CRC-8 = rtl/crc8 (poly 0x07, init 0x00) atas payload,
// dikirim sebagai satu byte data setelah payload. Simbol ke FIFO: {k, byte}.

`default_nettype none

module phy_framer (
    input  wire       clk,
    input  wire       rst,          // aktif tinggi, tersinkron ke clk
    input  wire [7:0] tx_data,
    input  wire       tx_valid,
    input  wire       tx_last,
    output reg        tx_ready,
    input  wire       fifo_full,
    output reg        fifo_push,
    output reg  [8:0] fifo_data
);

`include "phy_symbols.vh"

    localparam [2:0] F_IDLE = 3'd0, F_DATA = 3'd1, F_CRC = 3'd2, F_EOF = 3'd3,
                     F_GAP1 = 3'd4, F_GAP2 = 3'd5;

    reg  [2:0] st;
    reg        crc_clr, crc_en;
    wire [7:0] crc;

    crc8 u_crc (
        .clk(clk), .rst_n(!rst), .clr(crc_clr), .en(crc_en), .din(tx_data), .crc(crc)
    );

    always @* begin
        tx_ready = 1'b0; fifo_push = 1'b0; fifo_data = 9'd0; crc_clr = 1'b0; crc_en = 1'b0;
        case (st)
            F_IDLE: if (tx_valid && !fifo_full) begin
                fifo_push = 1'b1; fifo_data = {1'b1, SYM_SOF}; crc_clr = 1'b1;
            end
            F_DATA: begin
                tx_ready = !fifo_full;
                if (tx_valid && !fifo_full) begin
                    fifo_push = 1'b1; fifo_data = {1'b0, tx_data}; crc_en = 1'b1;
                end
            end
            F_CRC: if (!fifo_full) begin fifo_push = 1'b1; fifo_data = {1'b0, crc}; end
            F_EOF: if (!fifo_full) begin fifo_push = 1'b1; fifo_data = {1'b1, SYM_EOF}; end
            default: if (!fifo_full) begin fifo_push = 1'b1; fifo_data = {1'b1, SYM_IDLE}; end
        endcase
    end

    always @(posedge clk or posedge rst) begin
        if (rst) st <= F_IDLE;
        else case (st)
            F_IDLE:  if (fifo_push) st <= F_DATA;
            F_DATA:  if (fifo_push && tx_last) st <= F_CRC;
            F_CRC:   if (fifo_push) st <= F_EOF;
            F_EOF:   if (fifo_push) st <= F_GAP1;
            F_GAP1:  if (fifo_push) st <= F_GAP2;
            default: if (fifo_push) st <= F_IDLE;
        endcase
    end

endmodule

`default_nettype wire
