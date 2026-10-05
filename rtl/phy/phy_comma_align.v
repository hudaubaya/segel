// Penyelarasan word dengan comma K28.5 (domain rx_clk).
//
// Comma 7 bit (0011111 atau 1100000) hanya muncul di posisi abcdeif kode
// K28.1/K28.5/K28.7, jadi comma di win[9:3] berarti win[9:0] adalah satu simbol
// utuh. bitcnt berjalan bebas 0..9; geseran bit apa pun (10 kemungkinan) hanya
// menentukan nilai bitcnt saat comma terlihat, yang disimpan sebagai `phase`.
//
//   belum terkunci : comma pertama langsung mengunci phase itu
//   terkunci       : comma di phase lain dicatat sebagai kandidat; realign hanya
//                    terjadi kalau word BERIKUTNYA (10 bit kemudian) di phase
//                    kandidat juga comma. Kalau tidak, kandidat gugur. Comma palsu
//                    akibat galat satu bit tidak bisa muncul di dua word berurutan,
//                    jadi tidak pernah menggeser framing; slip bit nyata terkonfirmasi
//                    oleh dua IDLE berurutan yang selalu dikirim framer setelah EOF.
//
// word/word_valid keluar sekali per 10 bit setelah terkunci. align = 1 untuk word
// comma yang baru saja mengunci/realign (decoder mengambil RD dari bentuknya).

`default_nettype none

module phy_comma_align (
    input  wire       rx_clk,
    input  wire       rst,
    input  wire [9:0] win,
    output reg        word_valid,
    output reg  [9:0] word,
    output reg        align,
    output reg        locked,
    output reg  [3:0] phase,
    output reg  [7:0] realign_cnt     // jumlah realign setelah terkunci (jenuh)
);

    wire comma = (win[9:3] == 7'b0011111) || (win[9:3] == 7'b1100000);

    reg [3:0] bitcnt;
    reg       cand_v;
    reg [3:0] cand;

    always @(posedge rx_clk or posedge rst) begin
        if (rst) begin
            bitcnt <= 4'd0; locked <= 1'b0; phase <= 4'd0; cand_v <= 1'b0; cand <= 4'd0;
            word_valid <= 1'b0; word <= 10'd0; align <= 1'b0; realign_cnt <= 8'd0;
        end else begin
            bitcnt     <= (bitcnt == 4'd9) ? 4'd0 : bitcnt + 4'd1;
            word_valid <= 1'b0;
            align      <= 1'b0;
            if (comma && (!locked || (cand_v && cand == bitcnt && bitcnt != phase))) begin
                if (locked && realign_cnt != 8'hFF) realign_cnt <= realign_cnt + 8'd1;
                locked <= 1'b1; phase <= bitcnt; cand_v <= 1'b0;
                word_valid <= 1'b1; word <= win; align <= 1'b1;
            end else begin
                if (comma && locked && bitcnt != phase) begin
                    cand_v <= 1'b1; cand <= bitcnt;
                end else if (cand_v && bitcnt == cand) begin
                    cand_v <= 1'b0;          // word berikutnya di phase kandidat bukan comma
                end
                if (locked && bitcnt == phase) begin
                    word_valid <= 1'b1; word <= win;
                end
            end
        end
    end

endmodule

`default_nettype wire
