// PLL domain TX: satu keluaran dari FPGA_CLK1_50, frekuensi dipilih TX_SEL (satu
// revisi Quartus per laju). Rasio terhadap 50 MHz sengaja bukan bilangan bulat
// kecil (VCO 50 x 99/4 = 1237,5 MHz dibagi C = 50/62/124/248), sehingga fase tx_clk
// terhadap sys_clk berputar terus: 99/200, 99/248, 99/496, 99/992.
// Quartus memilih sendiri M/N/C; frekuensi aktual dibaca dari laporan fitter
// (docs/phy_howto.md). Dengan `define SEGEL_SIM, PLL diganti model perilaku.

`default_nettype none
`timescale 1ns / 1ps

module pll_tx #(
    parameter integer TX_SEL = 3          // 0: ~5, 1: ~10, 2: ~20, 3: ~25 Mbit/s
) (
    input  wire refclk,                   // 50 MHz
    input  wire rst,                      // aktif tinggi
    output wire outclk,
    output wire locked
);

`ifdef SEGEL_SIM
    // Model simulasi: periode dalam ps (VCO 1237,5 MHz / C).
    localparam real PERIOD_PS =
        (TX_SEL == 0) ? 200404.04 : (TX_SEL == 1) ? 100202.02 :
        (TX_SEL == 2) ? 50101.01  : 40404.04;
    reg clk_r = 1'b0, lock_r = 1'b0;
    always #(PERIOD_PS / 2000.0) clk_r = rst ? 1'b0 : ~clk_r;
    always @(posedge refclk or posedge rst)
        if (rst) lock_r <= 1'b0; else lock_r <= 1'b1;
    assign outclk = clk_r;
    assign locked = lock_r;
`else
    // Frekuensi ditulis sebagai literal string per cabang (bukan lewat vektor
    // berlebar tetap, yang akan menambah byte NUL di depan string yang lebih pendek).
`define SEGEL_PLL(FREQ) \
        altera_pll #( \
            .fractional_vco_multiplier("false"), \
            .reference_clock_frequency("50.0 MHz"), \
            .operation_mode("direct"), \
            .number_of_clocks(1), \
            .output_clock_frequency0(FREQ), \
            .phase_shift0("0 ps"), \
            .duty_cycle0(50), \
            .pll_type("General"), \
            .pll_subtype("General") \
        ) altera_pll_i ( \
            .rst(rst), .outclk(outclk), .locked(locked), .fboutclk(), .fbclk(1'b0), \
            .refclk(refclk) \
        );
    generate
        if (TX_SEL == 0)      begin : g_pll `SEGEL_PLL("4.989919 MHz")  end
        else if (TX_SEL == 1) begin : g_pll `SEGEL_PLL("9.979839 MHz")  end
        else if (TX_SEL == 2) begin : g_pll `SEGEL_PLL("19.959677 MHz") end
        else                  begin : g_pll `SEGEL_PLL("24.750000 MHz") end
    endgenerate
`undef SEGEL_PLL
`endif

endmodule

`default_nettype wire
