// Pemeriksa frame PRBS (domain sys_clk) di antarmuka RX phy.
//
// 4 byte pertama setiap frame = seed; sisanya dibandingkan dengan PRBS-31 yang
// dibangkitkan ulang dari seed itu. bit_errors = jumlah bit beda (popcount XOR),
// bits_checked = 8 x byte yang dibandingkan. Seed yang rusak membuat seluruh sisa
// frame dihitung salah (BER payload jadi konservatif); frame seperti itu hampir
// selalu juga ditandai rx_err_* oleh phy.

`default_nettype none

module prbs_checker (
    input  wire        clk,
    input  wire        rst,
    input  wire        clear,
    input  wire        rx_valid,
    input  wire [7:0]  rx_data,
    input  wire        rx_last,
    input  wire        rx_err,          // OR semua rx_err_* phy (valid bersama rx_last)
    output reg  [31:0] frames,          // frame diterima (jenuh)
    output reg  [31:0] frames_bad,      // frame berstatus galat (jenuh)
    output reg  [31:0] bit_errors,      // jenuh
    output reg  [63:0] bits_checked,
    output reg         err_seen         // sticky: ada galat sejak clear
);

`include "prbs31.vh"

    reg  [7:0]  idx;
    reg  [30:0] state;
    reg  [23:0] seed_hi;
    wire [38:0] nxt = prbs31_byte(state);
    wire [7:0]  diff = rx_data ^ nxt[7:0];
    wire [3:0]  nerr = diff[0] + diff[1] + diff[2] + diff[3] + diff[4] + diff[5] + diff[6] + diff[7];

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            idx <= 8'd0; state <= 31'd0; seed_hi <= 24'd0;
            frames <= 32'd0; frames_bad <= 32'd0; bit_errors <= 32'd0; bits_checked <= 64'd0;
            err_seen <= 1'b0;
        end else if (clear) begin
            idx <= 8'd0;
            frames <= 32'd0; frames_bad <= 32'd0; bit_errors <= 32'd0; bits_checked <= 64'd0;
            err_seen <= 1'b0;
        end else if (rx_valid) begin
            if (idx < 8'd3) begin
                seed_hi <= {seed_hi[15:0], rx_data};
            end else if (idx == 8'd3) begin
                state <= {seed_hi[22:0], rx_data};
            end else begin
                state <= nxt[38:8];
                bits_checked <= bits_checked + 64'd8;
                if (nerr != 4'd0) begin
                    err_seen <= 1'b1;
                    bit_errors <= (bit_errors > 32'hFFFF_FFFF - 32'd8) ? 32'hFFFF_FFFF
                                                                     : bit_errors + nerr;
                end
            end
            if (idx != 8'hFF) idx <= idx + 8'd1;
            if (rx_last) begin
                idx <= 8'd0;
                if (frames != 32'hFFFF_FFFF) frames <= frames + 32'd1;
                if (rx_err) begin
                    err_seen <= 1'b1;
                    if (frames_bad != 32'hFFFF_FFFF) frames_bad <= frames_bad + 32'd1;
                end
            end
        end
    end

endmodule

`default_nettype wire
