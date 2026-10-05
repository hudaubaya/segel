// Generator frame PRBS (domain sys_clk) untuk antarmuka TX phy.
//
// Setiap frame = 4 byte seed (state PRBS-31 di awal frame, MSB dulu, bit 31 = 0)
// + PAYLOAD_PRBS byte PRBS-31 dari seed itu. State berlanjut antar frame, jadi
// aliran PRBS kontinu. `enable` hanya dicek di awal frame: frame yang sudah mulai
// selalu diselesaikan, sehingga tidak ada frame setengah jadi saat uji dihentikan.

`default_nettype none

module prbs_framegen #(
    parameter integer PAYLOAD_PRBS = 60
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       enable,
    output wire [7:0] tx_data,
    output wire       tx_valid,
    output wire       tx_last,
    input  wire       tx_ready,
    output reg        busy,          // sedang di tengah frame
    output reg [31:0] frames         // frame selesai dikirim (jenuh)
);

`include "prbs31.vh"

    localparam integer LEN = 4 + PAYLOAD_PRBS;

    reg  [30:0] state;               // state PRBS untuk byte berikutnya
    reg  [30:0] seed;                // state di awal frame ini
    reg  [7:0]  idx;
    wire [38:0] nxt = prbs31_byte(state);

    assign tx_valid = busy;
    assign tx_last  = busy && (idx == LEN - 1);
    assign tx_data  = (idx == 8'd0) ? {1'b0, seed[30:24]} :
                      (idx == 8'd1) ? seed[23:16] :
                      (idx == 8'd2) ? seed[15:8]  :
                      (idx == 8'd3) ? seed[7:0]   : nxt[7:0];

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= {31{1'b1}}; seed <= {31{1'b1}}; idx <= 8'd0; busy <= 1'b0;
            frames <= 32'd0;
        end else if (!busy) begin
            if (enable) begin
                busy <= 1'b1; idx <= 8'd0; seed <= state;
            end
        end else if (tx_ready) begin            // byte idx diterima phy
            if (idx >= 8'd4) state <= nxt[38:8];
            if (idx == LEN - 1) begin
                busy <= 1'b0;
                if (frames != 32'hFFFF_FFFF) frames <= frames + 32'd1;
            end
            idx <= idx + 8'd1;
        end
    end

endmodule

`default_nettype wire
