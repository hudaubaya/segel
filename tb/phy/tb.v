// Testbench loopback dua PHY: A.tx -> kanal AB -> B.rx dan B.tx -> kanal BA -> A.rx.
//
// Setiap PHY punya tiga clock yang frekuensinya bebas: sys_clk dan tx_clk miliknya
// sendiri, serta rx_clk = clock yang diteruskan PHY lawan. Periode (ps) diatur
// test.py lewat p_*; clock dibangkitkan di sini, bukan cocotb.Clock.
//
// Kanal (per arah):
//   shift_* : data ditunda 1 + shift_* bit (register geser di clock TX pengirim),
//             sehingga batas simbol bergeser terhadap penerima
//   ddly_*  : tunda analog data (ps)
//   skew_*  : tunda analog clock yang diteruskan (ps)
//   inj_*   : 1 selama tepat satu tepi naik clock TX = satu bit dibalik

`default_nettype none
`timescale 1ns / 1ps

module tb;

    reg run = 1'b0;
    integer p_sys_a = 10000, p_sys_b = 10000, p_tx_a = 10000, p_tx_b = 10000;
    integer shift_ab = 0, shift_ba = 0, ddly_ab = 0, ddly_ba = 0, skew_ab = 0, skew_ba = 0;
    reg inj_ab = 1'b0, inj_ba = 1'b0;
    reg rst_n_a = 1'b0, rst_n_b = 1'b0;

    reg sys_clk_a = 1'b0, sys_clk_b = 1'b0, tx_clk_a = 1'b0, tx_clk_b = 1'b0;
    always begin wait (run); #(p_sys_a / 2000.0) sys_clk_a = ~sys_clk_a; end
    always begin wait (run); #(p_sys_b / 2000.0) sys_clk_b = ~sys_clk_b; end
    always begin wait (run); #(p_tx_a  / 2000.0) tx_clk_a  = ~tx_clk_a;  end
    always begin wait (run); #(p_tx_b  / 2000.0) tx_clk_b  = ~tx_clk_b;  end

    // ---------------------------------------------------------------- PHY A dan B
    reg  [7:0]  tx_data_a = 8'd0, tx_data_b = 8'd0;
    reg         tx_valid_a = 1'b0, tx_valid_b = 1'b0, tx_last_a = 1'b0, tx_last_b = 1'b0;

    wire tx_ser_a, tx_ser_b, tx_clk_out_a, tx_clk_out_b;
    reg  rx_clk_a = 1'b0, rx_clk_b = 1'b0, rx_ser_a = 1'b0, rx_ser_b = 1'b0;

`define PHY_PORTS(X) \
    wire        tx_ready_``X, rx_valid_``X, rx_last_``X, rx_err_crc_``X, rx_err_code_``X; \
    wire        rx_err_disp_``X, rx_err_ctrl_``X, rx_err_frame_``X, rx_locked_``X, rx_overflow_``X; \
    wire [7:0]  rx_data_``X; \
    wire [15:0] cnt_ok_``X, cnt_crc_``X, cnt_code_``X, cnt_disp_``X, cnt_ctrl_``X, cnt_frame_``X; \
    wire [15:0] cnt_lost_``X;

    `PHY_PORTS(a)
    `PHY_PORTS(b)

`define PHY_INST(X) \
    phy u_``X ( \
        .sys_clk(sys_clk_``X), .rst_n(rst_n_``X), \
        .tx_data(tx_data_``X), .tx_valid(tx_valid_``X), .tx_last(tx_last_``X), .tx_ready(tx_ready_``X), \
        .rx_valid(rx_valid_``X), .rx_data(rx_data_``X), .rx_last(rx_last_``X), \
        .rx_err_crc(rx_err_crc_``X), .rx_err_code(rx_err_code_``X), .rx_err_disp(rx_err_disp_``X), \
        .rx_err_ctrl(rx_err_ctrl_``X), .rx_err_frame(rx_err_frame_``X), \
        .rx_locked(rx_locked_``X), .rx_overflow(rx_overflow_``X), \
        .cnt_ok(cnt_ok_``X), .cnt_crc(cnt_crc_``X), .cnt_code(cnt_code_``X), .cnt_disp(cnt_disp_``X), \
        .cnt_ctrl(cnt_ctrl_``X), .cnt_frame(cnt_frame_``X), .cnt_lost(cnt_lost_``X), \
        .tx_clk(tx_clk_``X), .tx_ser(tx_ser_``X), .tx_clk_out(tx_clk_out_``X), \
        .rx_clk(rx_clk_``X), .rx_ser(rx_ser_``X) \
    );

    `PHY_INST(a)
    `PHY_INST(b)

    // ---------------------------------------------------------------- kanal
    reg [31:0] chan_ab = 32'd0, chan_ba = 32'd0;
    always @(posedge tx_clk_a) chan_ab <= {chan_ab[30:0], tx_ser_a ^ inj_ab};
    always @(posedge tx_clk_b) chan_ba <= {chan_ba[30:0], tx_ser_b ^ inj_ba};
    wire tap_ab = chan_ab[shift_ab];
    wire tap_ba = chan_ba[shift_ba];

    always @(tap_ab)       rx_ser_b <= #(ddly_ab / 1000.0) tap_ab;
    always @(tap_ba)       rx_ser_a <= #(ddly_ba / 1000.0) tap_ba;
    always @(tx_clk_out_a) rx_clk_b <= #(skew_ab / 1000.0) tx_clk_out_a;
    always @(tx_clk_out_b) rx_clk_a <= #(skew_ba / 1000.0) tx_clk_out_b;

endmodule

`default_nettype wire
