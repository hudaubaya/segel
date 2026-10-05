// Deframer RX (domain sistem): simbol dari FIFO RX -> payload + status per frame.
//
// Frame = SOF, >= 2 byte data (payload + CRC), EOF. CRC-8 dihitung atas payload
// DAN byte CRC; sisa 0 berarti cocok (CRC-8 tanpa refleksi dan tanpa XOR akhir).
// Dua byte terakhir ditahan supaya byte CRC tidak keluar dan rx_last jatuh di
// byte payload terakhir. Status (rx_err_*) valid bersama rx_last:
//   crc   : CRC tidak cocok
//   code  : ada kode 10 bit ilegal di dalam frame
//   disp  : ada galat running disparity di dalam frame
//   ctrl  : ada simbol K yang tidak diharapkan di dalam frame
//   frame : frame terpotong oleh SOF berikutnya, atau ada simbol yang hilang
//           karena FIFO RX penuh (SYM_ERR_LOST)
// Frame dengan < 2 byte data, EOF di luar frame, dan data di luar frame tidak
// keluar ke rx_*, tetapi dihitung di cnt_frame. Setiap kejadian galat dihitung di
// cnt_* (16 bit, jenuh), termasuk yang terjadi di luar frame.
// Tidak ada backpressure: deframer mengonsumsi satu simbol per siklus.

`default_nettype none

module phy_deframer (
    input  wire        clk,
    input  wire        rst,
    input  wire        fifo_empty,
    input  wire [8:0]  fifo_data,
    output wire        fifo_pop,
    output reg         rx_valid,
    output reg  [7:0]  rx_data,
    output reg         rx_last,
    output reg         rx_err_crc,
    output reg         rx_err_code,
    output reg         rx_err_disp,
    output reg         rx_err_ctrl,
    output reg         rx_err_frame,
    output reg  [15:0] cnt_ok,       // frame diterima tanpa galat
    output reg  [15:0] cnt_crc,      // frame dengan CRC salah
    output reg  [15:0] cnt_code,     // kode ilegal
    output reg  [15:0] cnt_disp,     // galat disparity
    output reg  [15:0] cnt_ctrl,     // simbol K tak terduga
    output reg  [15:0] cnt_frame,    // galat framing
    output reg  [15:0] cnt_lost      // penanda simbol hilang (FIFO RX penuh)
);

`include "phy_symbols.vh"

    wire       vld = !fifo_empty;
    wire       k   = fifo_data[8];
    wire [7:0] b   = fifo_data[7:0];
    assign fifo_pop = vld;

    reg        in_frame, stray;
    reg  [1:0] nheld;
    reg  [7:0] h0, h1;               // h1 = byte data lebih lama
    reg        f_code, f_disp, f_ctrl, f_lost;
    wire [7:0] crc;
    wire       is_sof  = vld && k && b == SYM_SOF;
    wire       is_data = vld && !k;

    crc8 u_crc (
        .clk(clk), .rst_n(!rst), .clr(is_sof), .en(is_data && in_frame), .din(b), .crc(crc)
    );

    function [15:0] inc;
        input [15:0] v;
        inc = (v == 16'hFFFF) ? v : v + 16'd1;
    endfunction

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            in_frame <= 1'b0; stray <= 1'b0; nheld <= 2'd0; h0 <= 8'd0; h1 <= 8'd0;
            f_code <= 1'b0; f_disp <= 1'b0; f_ctrl <= 1'b0; f_lost <= 1'b0;
            rx_valid <= 1'b0; rx_data <= 8'd0; rx_last <= 1'b0;
            {rx_err_crc, rx_err_code, rx_err_disp, rx_err_ctrl, rx_err_frame} <= 5'd0;
            cnt_ok <= 16'd0; cnt_crc <= 16'd0; cnt_code <= 16'd0; cnt_disp <= 16'd0;
            cnt_ctrl <= 16'd0; cnt_frame <= 16'd0; cnt_lost <= 16'd0;
        end else begin
            rx_valid <= 1'b0; rx_last <= 1'b0; rx_data <= 8'd0;
            {rx_err_crc, rx_err_code, rx_err_disp, rx_err_ctrl, rx_err_frame} <= 5'd0;
            if (vld) begin
                if (k && b == SYM_SOF) begin
                    if (in_frame) begin                       // frame sebelumnya terpotong
                        cnt_frame <= inc(cnt_frame);
                        if (nheld == 2'd2) begin
                            rx_valid <= 1'b1; rx_data <= h1; rx_last <= 1'b1;
                            rx_err_frame <= 1'b1;
                            {rx_err_code, rx_err_disp, rx_err_ctrl} <= {f_code, f_disp, f_ctrl};
                        end
                    end
                    in_frame <= 1'b1; stray <= 1'b0; nheld <= 2'd0;
                    {f_code, f_disp, f_ctrl, f_lost} <= 4'd0;
                end else if (k && b == SYM_EOF) begin
                    if (in_frame && nheld == 2'd2) begin
                        rx_valid <= 1'b1; rx_data <= h1; rx_last <= 1'b1;
                        rx_err_crc <= (crc != 8'd0);
                        rx_err_frame <= f_lost;
                        {rx_err_code, rx_err_disp, rx_err_ctrl} <= {f_code, f_disp, f_ctrl};
                        if (crc != 8'd0) cnt_crc <= inc(cnt_crc);
                        else if (!(f_code || f_disp || f_ctrl || f_lost)) cnt_ok <= inc(cnt_ok);
                    end else begin
                        cnt_frame <= inc(cnt_frame);
                    end
                    in_frame <= 1'b0;
                end else if (k && b == SYM_ERR_ILLEGAL) begin
                    cnt_code <= inc(cnt_code);
                    if (in_frame) f_code <= 1'b1;
                end else if (k && b == SYM_ERR_LOST) begin
                    cnt_lost <= inc(cnt_lost);
                    if (in_frame) f_lost <= 1'b1;
                end else if (k && b == SYM_ERR_DISP) begin
                    cnt_disp <= inc(cnt_disp);
                    if (in_frame) f_disp <= 1'b1;
                end else if (k) begin
                    cnt_ctrl <= inc(cnt_ctrl);
                    if (in_frame) f_ctrl <= 1'b1;
                end else if (in_frame) begin                  // byte data di dalam frame
                    if (nheld == 2'd2) begin
                        rx_valid <= 1'b1; rx_data <= h1;
                    end
                    h1 <= h0; h0 <= b;
                    if (nheld != 2'd2) nheld <= nheld + 2'd1;
                end else if (!stray) begin                    // data di luar frame
                    cnt_frame <= inc(cnt_frame);
                    stray <= 1'b1;
                end
            end
        end
    end

endmodule

`default_nettype wire
