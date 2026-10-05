// Top DE10-Nano: uji loopback lapisan fisik SEGEL (rtl/phy, tanpa kriptografi).
//
//   FPGA_CLK1_50 (V11) -> sys_clk 50 MHz: framer/deframer phy, PRBS, register, JTAG master
//                      -> pll_tx -> tx_clk (laju bit, tidak sebanding dengan 50 MHz)
//   PHY_TX_CLK/PHY_TX_DAT  keluar (GPIO_1[5]/GPIO_1[7]); PHY_TX_CLK = ~tx_clk lewat DDIO
//   PHY_RX_CLK/PHY_RX_DAT  masuk  (GPIO_1[0] = pin input clock CLKp, GPIO_1[4])
// Mode berbingkai: phy + frame PRBS (FER, deteksi galat). Mode RAW (CTRL.RAW_MODE):
// bit PRBS-31 mentah ke kabel dan checker BERT di domain rx (BER kanal fisik).
// Loopback: jumper PHY_TX_CLK -> PHY_RX_CLK dan PHY_TX_DAT -> PHY_RX_DAT
// (docs/phy_howto.md). KEY[0] = reset (aktif rendah).
//
// LED: 0 pll_locked, 1 rx_locked (atau raw_locked), 2 rx_overflow, 3 err_seen,
//      4 prbs_en atau raw_mode,
//      5 detak tx_clk, 6 detak sys_clk, 7 phy_rst

`default_nettype none
`timescale 1ns / 1ps

module de10nano_phy_loopback #(
    parameter integer TX_SEL = 3,                  // diatur per revisi (set_parameter)
    parameter integer PAYLOAD_PRBS = 60
) (
    input  wire       FPGA_CLK1_50,
    input  wire [1:0] KEY,
    output wire [7:0] LED,
    output wire       PHY_TX_CLK,
    output wire       PHY_TX_DAT,
    input  wire       PHY_RX_CLK,
    input  wire       PHY_RX_DAT
);

    localparam [31:0] TX_RATE_KHZ = (TX_SEL == 0) ? 32'd4990  : (TX_SEL == 1) ? 32'd9980 :
                                    (TX_SEL == 2) ? 32'd19960 : 32'd24750;

    wire sys_clk = FPGA_CLK1_50;

    // ------------------------------------------------------------ reset & PLL
    wire key_rst = !KEY[0];
    wire sys_rst;
    reset_synchronizer u_rst_sys (.clock(sys_clk), .reset_in(key_rst), .reset_out(sys_rst));

    wire tx_clk, pll_locked;
    pll_tx #(.TX_SEL(TX_SEL)) u_pll (
        .refclk(FPGA_CLK1_50), .rst(key_rst), .outclk(tx_clk), .locked(pll_locked)
    );

    // ------------------------------------------------------------ JTAG master
    wire [7:0]  avm_address;
    wire        avm_read, avm_write, avm_waitrequest, avm_readdatavalid;
    wire [31:0] avm_writedata, avm_readdata;
    wire [3:0]  avm_byteenable;

    phy_jtag u_jtag (                             // Platform Designer: qsys/make_phy_jtag.tcl
        .clk_clk(sys_clk),
        .reset_reset_n(!sys_rst),
        .avmm_waitrequest(avm_waitrequest),
        .avmm_readdata(avm_readdata),
        .avmm_readdatavalid(avm_readdatavalid),
        .avmm_burstcount(),
        .avmm_writedata(avm_writedata),
        .avmm_address(avm_address),
        .avmm_write(avm_write),
        .avmm_read(avm_read),
        .avmm_byteenable(avm_byteenable),
        .avmm_debugaccess()
    );

    wire prbs_en, phy_rst_reg, clear, raw_mode;

    // ------------------------------------------------------------ PHY
    // rst_n phy: tombol, PLL belum terkunci, atau PHY_RST dari register. Masuk ke
    // reset synchronizer setiap domain phy (assert asinkron, deassert sinkron).
    wire phy_rst_n = KEY[0] && pll_locked && !phy_rst_reg;

    wire [7:0]  g_data;
    wire        g_valid, g_last, g_ready, g_busy;
    wire [31:0] g_frames;
    wire        rx_valid, rx_last, rx_locked, rx_overflow;
    wire [7:0]  rx_data;
    wire        e_crc, e_code, e_disp, e_ctrl, e_frame;
    wire [15:0] c_ok, c_crc, c_code, c_disp, c_ctrl, c_frame, c_lost;
    wire        tx_ser_core, tx_clk_out_core;
    reg         tx_dat_q = 1'b0, rx_dat_q = 1'b0;   // register I/O data (lihat "pin data")

    phy #(.FIFO_AW(5)) u_phy (
        .sys_clk(sys_clk), .rst_n(phy_rst_n),
        .tx_data(g_data), .tx_valid(g_valid), .tx_last(g_last), .tx_ready(g_ready),
        .rx_valid(rx_valid), .rx_data(rx_data), .rx_last(rx_last),
        .rx_err_crc(e_crc), .rx_err_code(e_code), .rx_err_disp(e_disp),
        .rx_err_ctrl(e_ctrl), .rx_err_frame(e_frame),
        .rx_locked(rx_locked), .rx_overflow(rx_overflow),
        .cnt_ok(c_ok), .cnt_crc(c_crc), .cnt_code(c_code), .cnt_disp(c_disp),
        .cnt_ctrl(c_ctrl), .cnt_frame(c_frame), .cnt_lost(c_lost),
        .tx_clk(tx_clk), .tx_ser(tx_ser_core), .tx_clk_out(tx_clk_out_core),
        .rx_clk(PHY_RX_CLK), .rx_ser(rx_dat_q)
    );

    // ------------------------------------------------------------ pin data
    // Data masuk dan keluar masing-masing lewat SATU register I/O (QSF:
    // FAST_INPUT_REGISTER / FAST_OUTPUT_REGISTER), sehingga delay pin tetap dan sama
    // dengan clock. Register TX memilih phy atau bit RAW; latensi tambahan satu bit
    // tidak berpengaruh karena penerima mengambil sampel di tengah bit apa pun.
    // tx_clk_out_core (inverter, untuk ASIC/simulasi) tidak dipakai di FPGA.
    wire tx_rst, rx_rst_raw, raw_tx, raw_rx, raw_bit, raw_locked;
    wire raw_inc_bit, raw_inc_err, raw_inc_loss;
    reset_synchronizer u_rst_tx  (.clock(tx_clk), .reset_in(key_rst || !pll_locked),
                                  .reset_out(tx_rst));
    reset_synchronizer u_rst_rxr (.clock(PHY_RX_CLK), .reset_in(key_rst || !pll_locked),
                                  .reset_out(rx_rst_raw));
    synchronizer #(.WIDTH(1)) u_sync_raw (.clock(tx_clk), .reset(tx_rst),
                                          .in(raw_mode), .out(raw_tx));
    synchronizer #(.WIDTH(1)) u_sync_rawrx (.clock(PHY_RX_CLK), .reset(rx_rst_raw),
                                            .in(raw_mode), .out(raw_rx));
    prbs_raw_gen u_raw_gen (.clk(tx_clk), .rst(tx_rst), .bit_out(raw_bit));

    always @(posedge tx_clk)     tx_dat_q <= raw_tx ? raw_bit : tx_ser_core;
    always @(posedge PHY_RX_CLK) rx_dat_q <= PHY_RX_DAT;
    assign PHY_TX_DAT = tx_dat_q;
    fwd_clk_out u_fwd (.clk(tx_clk), .pin(PHY_TX_CLK));

    prbs_raw_check u_raw_chk (
        .clk(PHY_RX_CLK), .rst(rx_rst_raw), .en(raw_rx), .bit_in(rx_dat_q), .locked(raw_locked),
        .inc_bit(raw_inc_bit), .inc_err(raw_inc_err), .inc_loss(raw_inc_loss)
    );

    // ------------------------------------------------------------ PRBS
    prbs_framegen #(.PAYLOAD_PRBS(PAYLOAD_PRBS)) u_gen (
        .clk(sys_clk), .rst(sys_rst), .enable(prbs_en),
        .tx_data(g_data), .tx_valid(g_valid), .tx_last(g_last), .tx_ready(g_ready),
        .busy(g_busy), .frames(g_frames)
    );

    wire [31:0] k_frames, k_bad, k_biterr;
    wire [63:0] k_bits;
    wire        err_seen;
    prbs_checker u_chk (
        .clk(sys_clk), .rst(sys_rst), .clear(clear),
        .rx_valid(rx_valid), .rx_data(rx_data), .rx_last(rx_last),
        .rx_err(e_crc | e_code | e_disp | e_ctrl | e_frame),
        .frames(k_frames), .frames_bad(k_bad), .bit_errors(k_biterr), .bits_checked(k_bits),
        .err_seen(err_seen)
    );

    // Counter lintas domain (Gray 8 bit -> sys_clk): siklus tx_clk (laju bit aktual)
    // dan counter BERT mode RAW dari domain rx.
    wire [63:0] tx_cycles, raw_bits, raw_errors, raw_loss;
    cdc_event_counter u_fm (
        .meas_clk(tx_clk), .meas_rst(tx_rst), .inc(1'b1), .clk(sys_clk), .rst(sys_rst),
        .clear(clear), .count(tx_cycles)
    );
    cdc_event_counter u_cnt_rbit (
        .meas_clk(PHY_RX_CLK), .meas_rst(rx_rst_raw), .inc(raw_inc_bit), .clk(sys_clk),
        .rst(sys_rst), .clear(clear), .count(raw_bits)
    );
    cdc_event_counter u_cnt_rerr (
        .meas_clk(PHY_RX_CLK), .meas_rst(rx_rst_raw), .inc(raw_inc_err), .clk(sys_clk),
        .rst(sys_rst), .clear(clear), .count(raw_errors)
    );
    cdc_event_counter u_cnt_rloss (
        .meas_clk(PHY_RX_CLK), .meas_rst(rx_rst_raw), .inc(raw_inc_loss), .clk(sys_clk),
        .rst(sys_rst), .clear(clear), .count(raw_loss)
    );

    // ------------------------------------------------------------ register
    // pll_locked (asinkron) dan raw_locked (domain rx) disinkronkan sebelum dibaca.
    wire pll_locked_s, raw_locked_s;
    synchronizer #(.WIDTH(2)) u_sync_lock (.clock(sys_clk), .reset(sys_rst),
                                           .in({raw_locked, pll_locked}),
                                           .out({raw_locked_s, pll_locked_s}));

    loopback_regs #(.TX_RATE_KHZ(TX_RATE_KHZ)) u_regs (
        .clk(sys_clk), .rst(sys_rst),
        .avs_address(avm_address), .avs_read(avm_read), .avs_write(avm_write),
        .avs_writedata(avm_writedata), .avs_byteenable(avm_byteenable),
        .avs_readdata(avm_readdata), .avs_readdatavalid(avm_readdatavalid),
        .avs_waitrequest(avm_waitrequest),
        .prbs_en(prbs_en), .phy_rst(phy_rst_reg), .clear(clear), .raw_mode(raw_mode),
        .status({raw_locked_s, err_seen, g_busy, rx_overflow, rx_locked, pll_locked_s}),
        .tx_frames(g_frames), .rx_frames(k_frames), .rx_frames_bad(k_bad),
        .bit_errors(k_biterr), .bits_checked(k_bits), .tx_cycles(tx_cycles),
        .phy_cnt({c_lost, c_frame, c_ctrl, c_disp, c_code, c_crc, c_ok}),
        .raw_bits(raw_bits), .raw_errors(raw_errors), .raw_loss(raw_loss)
    );

    // ------------------------------------------------------------ LED
    reg [24:0] hb_sys = 25'd0;             // nilai power-up
    reg [23:0] hb_tx  = 24'd0;
    always @(posedge sys_clk) hb_sys <= hb_sys + 25'd1;
    always @(posedge tx_clk)  hb_tx  <= hb_tx + 24'd1;
    assign LED = {phy_rst_reg, hb_sys[24], hb_tx[23], prbs_en | raw_mode, err_seen,
                  rx_overflow, rx_locked | raw_locked_s, pll_locked_s};

endmodule

`default_nettype wire
