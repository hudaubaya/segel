// Decoder 8b/10b (IEEE 802.3 cl. 36), kombinasional, dengan flag kode ilegal dan
// galat disparity.
//
// code[9:0] = abcdei fghj (a = bit 9). rd: 0 = RD-, 1 = RD+.
//   illegal  = kode tidak ada di tabel untuk RD mana pun
//   disp_err = kode sah, tetapi hanya untuk RD lawan; dout/k dari dekode RD lawan
//   rd_out   = mengikuti disparity kode yang diterima (tetap bila 0), juga untuk
//              kode salah, sehingga penerima pulih sendiri
// Perilaku identik dengan model/enc8b10b.py decode() untuk 1024 kode x 2 RD
// (diuji exhaustive di tb/phy_units).

`default_nettype none

module dec8b10b (
    input  wire [9:0] code,
    input  wire       rd_in,
    output reg  [7:0] dout,
    output reg        k,
    output reg        illegal,
    output reg        disp_err,
    output reg        rd_out
);

`include "phy_8b10b_tables.vh"

    // Dekode pada satu RD: {sah, k, byte}
    function [9:0] dec_rd;
        input [9:0] c;
        input       r;
        reg [5:0] s6;
        reg [3:0] s4;
        reg [4:0] x;
        reg [2:0] y;
        reg       ok6, ok4, k28, kk, rm;
        integer   i;
        begin
            s6 = c[9:4];
            s4 = c[3:0];
            x = 5'd0; y = 3'd0; ok6 = 1'b0; ok4 = 1'b0; kk = 1'b0;
            // 6b -> 5b: bentuk yang sah untuk RD r
            k28 = (s6 == (r ? 6'b110000 : 6'b001111));
            if (k28) begin
                x = 5'd28; ok6 = 1'b1;
            end
            for (i = 0; i < 32; i = i + 1)
                if (s6 == ((r && alt6(i)) ? ~t6(i) : t6(i))) begin
                    x = i; ok6 = 1'b1;
                end
            rm = rd_after(r, pop6(s6), 4'd6);
            // 4b -> 3b, bergantung pada RD setelah sub-blok 6b
            if (k28) begin
                kk = 1'b1;
                for (i = 0; i < 8; i = i + 1)
                    if (s4 == (rm ? t4k(i) : ~t4k(i))) begin
                        y = i; ok4 = 1'b1;
                    end
            end else begin
                for (i = 0; i < 8; i = i + 1)
                    if (s4 == ((!rm && alt4(i)) ? ~t4p(i) : t4p(i))) begin
                        y = i; ok4 = !(i == 7 && a7_req(x, rm));   // P7 dilarang bila A7 wajib
                    end
                if (s4 == (rm ? 4'b1000 : 4'b0111)) begin        // bentuk A7
                    y = 3'd7;
                    ok4 = a7_req(x, rm) || kx7(x);
                    kk = !a7_req(x, rm) && kx7(x);
                end
            end
            dec_rd = {ok6 && ok4, kk, y, x};
        end
    endfunction

    reg [9:0] d_same, d_other;
    reg [4:0] ones;
    integer   j;

    always @* begin
        d_same  = dec_rd(code, rd_in);
        d_other = dec_rd(code, !rd_in);
        illegal  = !d_same[9] && !d_other[9];
        disp_err = !d_same[9] && d_other[9];
        {k, dout} = d_same[9] ? d_same[8:0] : d_other[8:0];
        ones = 5'd0;
        for (j = 0; j < 10; j = j + 1) ones = ones + code[j];
        rd_out = (ones > 5'd5) ? 1'b1 : (ones < 5'd5) ? 1'b0 : rd_in;
    end

endmodule

`default_nettype wire
