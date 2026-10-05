// Pengganti sistem Platform Designer phy_jtag untuk simulasi: port sama dengan hasil
// qsys-generate (fpga/phy_loopback/qsys/make_phy_jtag.tcl); transaksi Avalon digerakkan
// test.py lewat register m_* di modul ini.

`default_nettype none
`timescale 1ns / 1ps

module phy_jtag (
    input  wire        clk_clk,
    input  wire        reset_reset_n,
    input  wire        avmm_waitrequest,
    input  wire [31:0] avmm_readdata,
    input  wire        avmm_readdatavalid,
    output wire [0:0]  avmm_burstcount,
    output wire [31:0] avmm_writedata,
    output wire [7:0]  avmm_address,
    output wire        avmm_write,
    output wire        avmm_read,
    output wire [3:0]  avmm_byteenable,
    output wire        avmm_debugaccess
);
    reg [7:0]  m_address = 8'd0;
    reg [31:0] m_writedata = 32'd0;
    reg        m_write = 1'b0, m_read = 1'b0;
    assign avmm_address = m_address;
    assign avmm_writedata = m_writedata;
    assign avmm_write = m_write;
    assign avmm_read = m_read;
    assign avmm_byteenable = 4'hF;
    assign avmm_burstcount = 1'b1;
    assign avmm_debugaccess = 1'b0;
endmodule

`default_nettype wire
