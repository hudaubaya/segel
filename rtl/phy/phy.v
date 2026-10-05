// PHY serial SEGEL: 8b/10b, source-synchronous (clock diteruskan), comma K28.5,
// CDC FIFO 9 bit, framing dengan CRC-8. Lihat docs/phy.md.
//
//   domain sys_clk : framer TX, deframer RX, semua antarmuka pengguna
//   domain tx_clk  : serializer (1 bit per siklus), keluaran tx_ser + tx_clk_out
//   domain rx_clk  : clock yang diteruskan PHY lawan; deserializer, aligner, decoder
// Tiga domain boleh punya frekuensi bebas, dengan syarat sys_clk cukup cepat
// untuk mengosongkan FIFO RX: periode sys_clk < 10 x periode rx_clk (satu simbol
// per siklus sys_clk). FIFO TX/RX: rtl/cdc_fifo (turunan baseline #0036) dengan
// DATA_WIDTH = 9 = {k, byte}.

`default_nettype none

module phy #(
    parameter integer FIFO_AW = 5            // kedalaman FIFO = 2^FIFO_AW
) (
    input  wire        sys_clk,
    input  wire        rst_n,                // asinkron, aktif rendah, semua domain

    // TX pengguna (sys_clk)
    input  wire [7:0]  tx_data,
    input  wire        tx_valid,
    input  wire        tx_last,
    output wire        tx_ready,

    // RX pengguna (sys_clk)
    output wire        rx_valid,
    output wire [7:0]  rx_data,
    output wire        rx_last,
    output wire        rx_err_crc,
    output wire        rx_err_code,
    output wire        rx_err_disp,
    output wire        rx_err_ctrl,
    output wire        rx_err_frame,
    output wire        rx_locked,            // aligner terkunci (tersinkron ke sys_clk)
    output wire        rx_overflow,          // FIFO RX pernah penuh, sticky (tersinkron)
    output wire [15:0] cnt_ok,
    output wire [15:0] cnt_crc,
    output wire [15:0] cnt_code,
    output wire [15:0] cnt_disp,
    output wire [15:0] cnt_ctrl,
    output wire [15:0] cnt_frame,
    output wire [15:0] cnt_lost,

    // serial
    input  wire        tx_clk,
    output wire        tx_ser,
    output wire        tx_clk_out,
    input  wire        rx_clk,
    input  wire        rx_ser
);

`include "phy_symbols.vh"

    wire rst_async = !rst_n;
    wire sys_rst, tx_rst, rx_rst;

    reset_synchronizer u_rst_sys (.clock(sys_clk), .reset_in(rst_async), .reset_out(sys_rst));
    reset_synchronizer u_rst_tx  (.clock(tx_clk),  .reset_in(rst_async), .reset_out(tx_rst));
    reset_synchronizer u_rst_rx  (.clock(rx_clk),  .reset_in(rst_async), .reset_out(rx_rst));

    // ------------------------------------------------------------ TX
    wire       txf_full, txf_push, txf_empty, txf_pop;
    wire [8:0] txf_wdata, txf_rdata;

    phy_framer u_framer (
        .clk(sys_clk), .rst(sys_rst), .tx_data(tx_data), .tx_valid(tx_valid),
        .tx_last(tx_last), .tx_ready(tx_ready), .fifo_full(txf_full),
        .fifo_push(txf_push), .fifo_data(txf_wdata)
    );

    cdc_fifo #(.DATA_WIDTH(9), .ADDRESS_WIDTH(FIFO_AW)) u_tx_fifo (
        .write_clock(sys_clk), .write_reset(rst_async), .write_data(txf_wdata),
        .write_increment(txf_push), .full(txf_full),
        .read_clock(tx_clk), .read_reset(rst_async), .read_increment(txf_pop),
        .read_data(txf_rdata), .empty(txf_empty)
    );

    phy_serializer u_ser (
        .tx_clk(tx_clk), .rst(tx_rst), .fifo_empty(txf_empty), .fifo_data(txf_rdata),
        .fifo_pop(txf_pop), .ser_out(tx_ser), .clk_out(tx_clk_out)
    );

    // ------------------------------------------------------------ RX (rx_clk)
    wire [9:0] win, word;
    wire       word_valid, align, locked;
    wire [3:0] phase;
    wire [7:0] realign_cnt;

    phy_deserializer u_des (.rx_clk(rx_clk), .rst(rx_rst), .ser_in(rx_ser), .win(win));

    phy_comma_align u_align (
        .rx_clk(rx_clk), .rst(rx_rst), .win(win), .word_valid(word_valid), .word(word),
        .align(align), .locked(locked), .phase(phase), .realign_cnt(realign_cnt)
    );

    // Saat (re)align, RD diambil dari bentuk comma: 0011111... = K28.x RD-.
    reg        rd;
    wire       rd_use = align ? (word[9:3] != 7'b0011111) : rd;
    wire [7:0] dbyte;
    wire       dk, dillegal, ddisp, rd_next;

    dec8b10b u_dec (
        .code(word), .rd_in(rd_use), .dout(dbyte), .k(dk), .illegal(dillegal),
        .disp_err(ddisp), .rd_out(rd_next)
    );

    wire       rxf_full, rxf_empty, rxf_pop;
    wire [8:0] rxf_rdata;
    wire [8:0] rx_sym    = dillegal ? {1'b1, SYM_ERR_ILLEGAL}
                         : ddisp    ? {1'b1, SYM_ERR_DISP}
                         :            {dk, dbyte};
    wire       is_idle   = !dillegal && !ddisp && dk && dbyte == SYM_IDLE;
    wire       rx_want   = word_valid && !is_idle;
    // Simbol yang dibuang karena FIFO penuh tidak boleh hilang diam-diam: begitu
    // FIFO punya tempat, SYM_ERR_LOST ditulis (menggantikan simbol saat itu, kalau
    // ada), sehingga deframer menandai frame yang terkena (rx_err_frame).
    reg        lost_pend;
    wire       rxf_push  = rx_want || lost_pend;
    wire [8:0] rxf_wdata = lost_pend ? {1'b1, SYM_ERR_LOST} : rx_sym;
    reg        rx_ovf;

    always @(posedge rx_clk or posedge rx_rst) begin
        if (rx_rst) begin
            rd <= 1'b0; rx_ovf <= 1'b0; lost_pend <= 1'b0;
        end else begin
            if (word_valid) rd <= rd_next;
            if (rxf_push && rxf_full) begin
                rx_ovf <= 1'b1; lost_pend <= 1'b1;
            end else if (lost_pend) begin
                lost_pend <= 1'b0;           // penanda tertulis di siklus ini
            end
        end
    end

    cdc_fifo #(.DATA_WIDTH(9), .ADDRESS_WIDTH(FIFO_AW)) u_rx_fifo (
        .write_clock(rx_clk), .write_reset(rst_async), .write_data(rxf_wdata),
        .write_increment(rxf_push), .full(rxf_full),
        .read_clock(sys_clk), .read_reset(rst_async), .read_increment(rxf_pop),
        .read_data(rxf_rdata), .empty(rxf_empty)
    );

    synchronizer #(.WIDTH(2)) u_sync_status (
        .clock(sys_clk), .reset(sys_rst), .in({locked, rx_ovf}), .out({rx_locked, rx_overflow})
    );

    // ------------------------------------------------------------ RX (sys_clk)
    phy_deframer u_deframer (
        .clk(sys_clk), .rst(sys_rst), .fifo_empty(rxf_empty), .fifo_data(rxf_rdata),
        .fifo_pop(rxf_pop), .rx_valid(rx_valid), .rx_data(rx_data), .rx_last(rx_last),
        .rx_err_crc(rx_err_crc), .rx_err_code(rx_err_code), .rx_err_disp(rx_err_disp),
        .rx_err_ctrl(rx_err_ctrl), .rx_err_frame(rx_err_frame), .cnt_ok(cnt_ok),
        .cnt_crc(cnt_crc), .cnt_code(cnt_code), .cnt_disp(cnt_disp), .cnt_ctrl(cnt_ctrl),
        .cnt_frame(cnt_frame), .cnt_lost(cnt_lost)
    );

endmodule

`default_nettype wire
