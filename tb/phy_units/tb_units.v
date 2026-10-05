// Testbench unit PHY: encoder/decoder 8b/10b (kombinasional) dan
// deserializer + comma aligner (clock dari cocotb).

`default_nettype none
`timescale 1ns / 1ps

module tb_units (
    input  wire [7:0] enc_din,
    input  wire       enc_k,
    input  wire       enc_rd,
    output wire [9:0] enc_code,
    output wire       enc_rd_out,
    output wire       enc_k_err,

    input  wire [9:0] dec_code,
    input  wire       dec_rd,
    output wire [7:0] dec_dout,
    output wire       dec_k,
    output wire       dec_illegal,
    output wire       dec_disp_err,
    output wire       dec_rd_out,

    input  wire       clk,
    input  wire       rst,
    input  wire       ser,
    output wire [9:0] word,
    output wire       word_valid,
    output wire       align,
    output wire       locked,
    output wire [3:0] phase,
    output wire [7:0] realign_cnt
);

    enc8b10b u_enc (
        .din(enc_din), .k(enc_k), .rd_in(enc_rd), .code(enc_code), .rd_out(enc_rd_out),
        .k_err(enc_k_err)
    );

    dec8b10b u_dec (
        .code(dec_code), .rd_in(dec_rd), .dout(dec_dout), .k(dec_k), .illegal(dec_illegal),
        .disp_err(dec_disp_err), .rd_out(dec_rd_out)
    );

    wire [9:0] win;
    phy_deserializer u_des (.rx_clk(clk), .rst(rst), .ser_in(ser), .win(win));
    phy_comma_align u_align (
        .rx_clk(clk), .rst(rst), .win(win), .word_valid(word_valid), .word(word), .align(align),
        .locked(locked), .phase(phase), .realign_cnt(realign_cnt)
    );

endmodule

`default_nettype wire
