// Testbench top DE10-Nano (simulasi, `define SEGEL_SIM): FPGA_CLK1_50 dari Verilog,
// jumper loopback PHY_TX_* -> PHY_RX_* dengan tunda dan injeksi galat bit.

`default_nettype none
`timescale 1ns / 1ps

module tb_fpga #(
    parameter integer TX_SEL = 3
) ();
    reg clk50 = 1'b0;
    always #10 clk50 = ~clk50;

    reg  [1:0] key = 2'b00;            // KEY[0] = reset aktif rendah
    wire [7:0] led;
    wire tx_clk_pin, tx_dat_pin;
    reg  inj = 1'b0;                   // 1 selama satu tepi naik tx_clk = satu bit dibalik
    integer ddly_ps = 1500, skew_ps = 800;

    // Kanal: data dibalik di sumber (diregister di tx_clk supaya tepat satu bit)
    reg inj_q = 1'b0;
    always @(posedge u_top.tx_clk) inj_q <= inj;
    reg rx_clk_pin = 1'b0, rx_dat_pin = 1'b0;
    always @(tx_clk_pin)          rx_clk_pin <= #(skew_ps / 1000.0) tx_clk_pin;
    always @(tx_dat_pin or inj_q) rx_dat_pin <= #(ddly_ps / 1000.0) (tx_dat_pin ^ inj_q);

    de10nano_phy_loopback #(.TX_SEL(TX_SEL)) u_top (
        .FPGA_CLK1_50(clk50), .KEY(key), .LED(led),
        .PHY_TX_CLK(tx_clk_pin), .PHY_TX_DAT(tx_dat_pin),
        .PHY_RX_CLK(rx_clk_pin), .PHY_RX_DAT(rx_dat_pin)
    );
endmodule

`default_nettype wire
