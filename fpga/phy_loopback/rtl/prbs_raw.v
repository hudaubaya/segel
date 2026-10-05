// Mode RAW (BERT klasik): bit PRBS-31 langsung ke kabel, tanpa 8b/10b dan framing.
// Mengukur BER kanal fisik; mode berbingkai (prbs_framegen/checker) tidak bisa,
// karena simbol yang ditandai galat dibuang phy sehingga sisa frame bergeser.
//
// prbs_raw_gen   (domain tx_clk): satu bit per siklus, b[n] = b[n-31] ^ b[n-28].
// prbs_raw_check (domain rx_clk):
//   SEARCH: prediksi swa-sinkron dari 31 bit terakhir yang diterima; setelah 64 bit
//           berturut-turut cocok -> LOCK, generator lokal dimuat dari bit diterima.
//   LOCK  : generator lokal berjalan sendiri; setiap bit beda = satu galat (tepat
//           satu hitungan per bit salah, tidak dikali 3 seperti checker swa-sinkron).
//           >= 16 galat dalam jendela 64 bit -> kehilangan sinkron, kembali SEARCH.
//   en = 0 (RAW_MODE mati): ditahan di SEARCH (reset sinkron), sehingga setiap putaran
//           RAW mulai dengan sinkronisasi baru dan `locked` tidak basi.

`default_nettype none

module prbs_raw_gen (
    input  wire clk,
    input  wire rst,
    output wire bit_out
);
    reg [30:0] s;
    wire nb = s[30] ^ s[27];
    always @(posedge clk or posedge rst)
        if (rst) s <= {31{1'b1}};
        else     s <= {s[29:0], nb};
    assign bit_out = nb;
endmodule

module prbs_raw_check (
    input  wire clk,
    input  wire rst,
    input  wire en,
    input  wire bit_in,
    output reg  locked,
    output reg  inc_bit,         // satu bit dibandingkan (LOCK)
    output reg  inc_err,         // bit itu salah
    output reg  inc_loss         // kehilangan sinkron
);
    reg [30:0] rsh;              // 31 bit terakhir yang diterima, rsh[0] terbaru
    reg [30:0] loc;              // generator lokal (LOCK)
    reg [6:0]  good;
    reg [5:0]  wcnt;
    reg [4:0]  werr;

    wire pred_self = rsh[30] ^ rsh[27];
    wire pred_loc  = loc[30] ^ loc[27];
    wire err       = bit_in ^ pred_loc;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            rsh <= 31'd0; loc <= 31'd0; good <= 7'd0; locked <= 1'b0;
            wcnt <= 6'd0; werr <= 5'd0; inc_bit <= 1'b0; inc_err <= 1'b0; inc_loss <= 1'b0;
        end else begin
            rsh <= {rsh[29:0], bit_in};
            inc_bit <= 1'b0; inc_err <= 1'b0; inc_loss <= 1'b0;
            if (!en) begin
                locked <= 1'b0; good <= 7'd0; wcnt <= 6'd0; werr <= 5'd0;
            end else if (!locked) begin
                good <= (bit_in == pred_self && rsh != 31'd0) ? good + 7'd1 : 7'd0;
                if (good == 7'd63 && bit_in == pred_self) begin
                    locked <= 1'b1; loc <= {rsh[29:0], bit_in}; wcnt <= 6'd0; werr <= 5'd0;
                end
            end else begin
                loc <= {loc[29:0], pred_loc};
                inc_bit <= 1'b1;
                inc_err <= err;
                wcnt <= wcnt + 6'd1;
                if (wcnt == 6'd63) begin
                    werr <= 5'd0;
                    if (werr + err >= 16) begin
                        locked <= 1'b0; good <= 7'd0; inc_loss <= 1'b1;
                    end
                end else if (werr != 5'd31) begin
                    werr <= werr + err;
                end
            end
        end
    end
endmodule

`default_nettype wire
