// Encoder 8b/10b (IEEE 802.3 cl. 36), kombinasional, dengan running disparity.
//
// din = HGF EDCBA (y = din[7:5], x = din[4:0]), k = 1 untuk kode kontrol.
// code[9:0] = abcdei fghj, `a` (bit 9) dikirim pertama. rd: 0 = RD-, 1 = RD+.
// Kode K yang sah: K28.0-7, K23.7, K27.7, K29.7, K30.7. Permintaan K lain
// menaikkan k_err dan dikodekan sebagai data D.x.y.
// Ditulis ulang untuk SEGEL; tabel diambil dari baseline #0200 dengan perbaikan
// (phy_8b10b_tables.vh, docs/phy.md).

`default_nettype none

module enc8b10b (
    input  wire [7:0] din,
    input  wire       k,
    input  wire       rd_in,
    output reg  [9:0] code,
    output reg        rd_out,
    output reg        k_err
);

`include "phy_8b10b_tables.vh"

    reg [4:0] x;
    reg [2:0] y;
    reg       kk, rd_mid;
    reg [5:0] six;
    reg [3:0] four;

    always @* begin
        x = din[4:0];
        y = din[7:5];
        k_err = k && !(x == 5'd28 || (y == 3'd7 && kx7(x)));
        kk = k && !k_err;

        if (kk && x == 5'd28) six = rd_in ? 6'b110000 : 6'b001111;
        else                  six = (rd_in && alt6(x)) ? ~t6(x) : t6(x);
        rd_mid = rd_after(rd_in, pop6(six), 4'd6);

        if (kk)                              four = rd_mid ? t4k(y) : ~t4k(y);
        else if (y == 3'd7 && a7_req(x, rd_mid)) four = rd_mid ? 4'b1000 : 4'b0111;
        else                                 four = (!rd_mid && alt4(y)) ? ~t4p(y) : t4p(y);
        rd_out = rd_after(rd_mid, pop4(four), 4'd4);

        code = {six, four};
    end

endmodule

`default_nettype wire
