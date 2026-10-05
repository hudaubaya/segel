// Deserializer PHY (domain rx_clk = clock yang diteruskan pengirim): geser satu
// bit per tepi naik rx_clk. win[9] adalah bit tertua dari 10 bit terakhir, jadi
// kalau win sejajar batas simbol, win = abcdei fghj dengan `a` = win[9].
// Tidak ada synchronizer: ser_in sinkron dengan rx_clk (source-synchronous).

`default_nettype none

module phy_deserializer (
    input  wire       rx_clk,
    input  wire       rst,          // aktif tinggi, tersinkron ke rx_clk
    input  wire       ser_in,
    output reg  [9:0] win
);

    always @(posedge rx_clk or posedge rst) begin
        if (rst) win <= 10'd0;
        else     win <= {win[8:0], ser_in};
    end

endmodule

`default_nettype wire
