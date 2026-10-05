// Ascon-AEAD128 (enkripsi/dekripsi) dan Ascon-XOF128, NIST SP 800-232 (final, Agustus 2025).
//
// Permutasi Ascon-p 320 bit, satu ronde per siklus. Golden model: model/ascon.py,
// dokumentasi: docs/ascon.md.
//
// Urutan bit/byte (sama dengan SP 800-232): byte ke-i string = bus[8*i +: 8], bit ke-j
// string = bus[j]. Jadi key/nonce/blok data langsung menjadi kata state little-endian:
// x0 = bus[63:0], x1 = bus[127:64].
//
// Antarmuka perintah (diambil saat start=1 dan busy=0):
//   mode     0 = AEAD128 enkripsi, 1 = AEAD128 dekripsi, 2 = XOF128 (3 = ilegal -> err)
//   key      kunci 128 bit                         (AEAD)
//   key2     kunci kedua untuk nonce masking: nonce yang dipakai = nonce ^ key2;
//            isi 0 untuk AEAD128 tanpa masking      (AEAD)
//   nonce    nonce 128 bit                          (AEAD)
//   tag_in   tag yang diverifikasi                  (dekripsi)
//   tag_bits panjang tag 32..128 bit; tag dipotong ke tag_bits bit pertama (bit rendah).
//            Di luar 32..128 -> err, operasi tidak dijalankan.            (AEAD)
//   xof_bits panjang keluaran XOF dalam bit         (XOF)
//
// Data masuk (din_valid/din_ready). AEAD: fase AD lalu fase pesan (plaintext atau
// ciphertext); XOF: satu fase pesan. Setiap fase adalah nol atau lebih blok penuh
// (din_last=0, 128 bit AEAD / 64 bit XOF di din[63:0]) diakhiri TEPAT SATU blok
// din_last=1 berisi din_bits = 0..rate-1 bit. AD kosong = satu blok last dengan
// din_bits=0. din_last=1 dengan din_bits >= rate -> err.
//
// Data keluar (dout_valid/dout_ready, dout_bits bit valid): ciphertext (enkripsi,
// mengalir), plaintext (dekripsi, HANYA setelah tag terverifikasi), atau keluaran XOF.
// Selama dout_valid=0, dout bernilai 0.
//
// Dekripsi: plaintext disimpan di buffer internal (PT_BUF_BLOCKS blok 128 bit) dan baru
// dikeluarkan setelah tag cocok. Kalau tag salah (atau pesan melebihi buffer), buffer
// dinolkan, dout tetap 0, dout_valid tidak pernah naik, auth_ok=0. Tag yang dihitung
// tidak pernah keluar pada mode dekripsi (tag_out tetap 0).
//
// Akhir operasi: done berpulsa 1 siklus setelah keluaran terakhir diterima. Saat itu
// tag_out (enkripsi), auth_ok (dekripsi) dan err valid sampai start berikutnya.
// State, kunci dan tag_in internal dinolkan di akhir setiap operasi.

`default_nettype none

module ascon_core #(
    parameter integer PT_BUF_BLOCKS = 4   // kapasitas buffer plaintext dekripsi, blok 128 bit
) (
    input  wire         clk,
    input  wire         rst_n,            // reset asinkron aktif rendah

    input  wire         start,
    input  wire [1:0]   mode,
    input  wire [127:0] key,
    input  wire [127:0] key2,
    input  wire [127:0] nonce,
    input  wire [127:0] tag_in,
    input  wire [7:0]   tag_bits,
    input  wire [31:0]  xof_bits,
    output wire         busy,
    output reg          done,
    output reg  [127:0] tag_out,
    output reg          auth_ok,
    output reg          err,

    input  wire         din_valid,
    output reg          din_ready,
    input  wire [127:0] din,
    input  wire [7:0]   din_bits,
    input  wire         din_last,

    output reg          dout_valid,
    input  wire         dout_ready,
    output reg  [127:0] dout,
    output reg  [7:0]   dout_bits
);

    localparam [1:0] M_ENC = 2'd0, M_DEC = 2'd1, M_XOF = 2'd2;

    // IV (SP 800-232): AEAD128 = 0x00001000808c0001, XOF128 = 0x0000080000cc0003
    localparam [63:0] IV_AEAD = 64'h0000_1000_808c_0001;
    localparam [63:0] IV_XOF  = 64'h0000_0800_00cc_0003;

    localparam [3:0] S_IDLE  = 4'd0,   // menunggu start
                     S_INIT  = 4'd1,   // p12 inisialisasi (AEAD dan XOF)
                     S_AD    = 4'd2,   // menunggu blok AD
                     S_ADP   = 4'd3,   // p8 setelah blok AD
                     S_MSG   = 4'd4,   // menunggu blok plaintext/ciphertext
                     S_MSGP  = 4'd5,   // p8 setelah blok pesan
                     S_FIN   = 4'd6,   // p12 finalisasi
                     S_REL   = 4'd7,   // dekripsi: keluarkan plaintext terverifikasi
                     S_WIPE  = 4'd8,   // dekripsi: tag salah, nolkan buffer
                     S_XABS  = 4'd9,   // XOF: menunggu blok pesan
                     S_XABSP = 4'd10,  // XOF: p12 setelah blok pesan
                     S_SQ    = 4'd11,  // XOF: keluarkan satu blok
                     S_SQP   = 4'd12,  // XOF: p12 antar blok keluaran
                     S_DRAIN = 4'd13;  // tunggu keluaran terakhir diterima, lalu done

    // ---------------------------------------------------------------- permutasi
    function [63:0] rotr;
        input [63:0] x;
        input integer n;
        rotr = (x >> n) | (x << (64 - n));
    endfunction

    // Satu ronde Ascon-p. s = {x4, x3, x2, x1, x0}, r = indeks ronde 0..11.
    function [319:0] ascon_round;
        input [319:0] s;
        input [3:0]   r;
        reg [63:0] x0, x1, x2, x3, x4, t0, t1, t2, t3, t4;
        begin
            {x4, x3, x2, x1, x0} = s;
            // konstanta ronde 0xf0 - r*0x10 + r = {15-r, r}
            x2 = x2 ^ {56'd0, ~r, r};
            // lapisan substitusi (S-box 5 bit, bitsliced)
            x0 = x0 ^ x4;  x4 = x4 ^ x3;  x2 = x2 ^ x1;
            t0 = ~x0 & x1; t1 = ~x1 & x2; t2 = ~x2 & x3; t3 = ~x3 & x4; t4 = ~x4 & x0;
            x0 = x0 ^ t1;  x1 = x1 ^ t2;  x2 = x2 ^ t3;  x3 = x3 ^ t4;  x4 = x4 ^ t0;
            x1 = x1 ^ x0;  x0 = x0 ^ x4;  x3 = x3 ^ x2;  x2 = ~x2;
            // lapisan difusi linear
            x0 = x0 ^ rotr(x0, 19) ^ rotr(x0, 28);
            x1 = x1 ^ rotr(x1, 61) ^ rotr(x1, 39);
            x2 = x2 ^ rotr(x2,  1) ^ rotr(x2,  6);
            x3 = x3 ^ rotr(x3, 10) ^ rotr(x3, 17);
            x4 = x4 ^ rotr(x4,  7) ^ rotr(x4, 41);
            ascon_round = {x4, x3, x2, x1, x0};
        end
    endfunction

    // ---------------------------------------------------------------- register
    reg [3:0]   st;
    reg [319:0] s;            // state {x4, x3, x2, x1, x0}
    reg [3:0]   rnd;          // indeks ronde berikutnya
    reg [1:0]   mode_r;
    reg [127:0] key_r;
    reg [127:0] tag_in_r;
    reg [7:0]   tag_bits_r;
    reg [31:0]  rem;          // XOF: bit keluaran tersisa
    reg         ad_any;       // ada bit AD sebelum blok last
    reg         last_r;       // blok yang sedang dipermutasi adalah blok last
    reg [15:0]  nblk;         // blok plaintext di buffer
    reg [15:0]  idx;          // indeks rilis/wipe
    reg [7:0]   last_bits;    // bit valid entri buffer terakhir (0 = penuh)
    reg         ovf;          // pesan dekripsi melebihi buffer

    reg [127:0] pbuf [0:PT_BUF_BLOCKS-1];

    assign busy = (st != S_IDLE);

    wire [319:0] sr       = ascon_round(s, rnd);
    wire         perm_end = (rnd == 4'd11);
    wire         ofree    = !dout_valid || dout_ready;   // register keluaran bisa diisi
    wire         din_fire = din_valid && din_ready;

    // Blok masuk: blok non-last penuh; blok last diberi padding 1 di bit din_bits.
    wire [127:0] dmask   = din_last ? ~({128{1'b1}} << din_bits) : {128{1'b1}};
    wire [127:0] dpad    = din_last ? (128'd1 << din_bits) : 128'd0;
    wire [127:0] s01     = s[127:0];
    wire [127:0] enc_s01 = s01 ^ (din & dmask) ^ dpad;          // absorb AD / plaintext
    wire [127:0] dec_c   = din & dmask;
    wire [127:0] dec_s01 = (s01 & ~dmask) ^ dec_c ^ dpad;       // state <- ciphertext
    wire [127:0] dec_p   = (s01 ^ dec_c) & dmask;               // plaintext
    wire [63:0]  xmask   = din_last ? ~({64{1'b1}} << din_bits) : {64{1'b1}};
    wire [63:0]  xpad    = din_last ? (64'd1 << din_bits) : 64'd0;
    wire         din_has_bits = !din_last || (din_bits != 8'd0);
    wire         bad_last_aead = din_last && (din_bits > 8'd127);
    wire         bad_last_xof  = din_last && (din_bits > 8'd63);

    // Finalisasi: tag = {x4, x3} ^ key setelah p12; dipotong ke tag_bits bit rendah.
    wire [127:0] tag_mask = ~({128{1'b1}} << tag_bits_r);
    wire [127:0] tag_calc = {sr[319:256], sr[255:192]} ^ key_r;
    wire         tag_ok   = (((tag_calc ^ tag_in_r) & tag_mask) == 128'd0);

    // XOF: keluarkan min(rem, 64) bit dari x0
    wire [31:0]  sq_bits = (rem > 32'd64) ? 32'd64 : rem;
    wire [63:0]  sq_mask = ~({64{1'b1}} << sq_bits[6:0]);

    always @* begin
        case (st)
            S_AD, S_XABS: din_ready = 1'b1;
            S_MSG:        din_ready = (mode_r == M_DEC) || ofree;   // enkripsi butuh slot keluaran
            default:      din_ready = 1'b0;
        endcase
    end

    // ---------------------------------------------------------------- buffer plaintext
    // Tanpa reset; setiap entri yang ditulis dinolkan lagi saat dirilis (S_REL) atau
    // di-wipe (S_WIPE).
    reg         buf_we;
    reg [15:0]  buf_wa;
    reg [127:0] buf_wd;
    always @* begin
        buf_we = 1'b0;
        buf_wa = 16'd0;
        buf_wd = 128'd0;
        case (st)
            S_MSG:  if (din_fire && mode_r == M_DEC && din_has_bits && nblk < PT_BUF_BLOCKS) begin
                        buf_we = 1'b1; buf_wa = nblk; buf_wd = dec_p;
                    end
            S_REL:  if (ofree && idx != nblk) begin buf_we = 1'b1; buf_wa = idx; end
            S_WIPE: if (idx != nblk)          begin buf_we = 1'b1; buf_wa = idx; end
            default: ;
        endcase
    end
    always @(posedge clk) begin
        if (buf_we) pbuf[buf_wa] <= buf_wd;
    end

    // ---------------------------------------------------------------- FSM + datapath
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; s <= 320'd0; rnd <= 4'd0; mode_r <= M_ENC;
            key_r <= 128'd0; tag_in_r <= 128'd0; tag_bits_r <= 8'd0; rem <= 32'd0;
            ad_any <= 1'b0; last_r <= 1'b0; nblk <= 16'd0; idx <= 16'd0;
            last_bits <= 8'd0; ovf <= 1'b0;
            done <= 1'b0; tag_out <= 128'd0; auth_ok <= 1'b0; err <= 1'b0;
            dout_valid <= 1'b0; dout <= 128'd0; dout_bits <= 8'd0;
        end else begin
            done <= 1'b0;
            if (dout_valid && dout_ready) begin   // keluaran diterima: kosongkan dan nolkan
                dout_valid <= 1'b0; dout <= 128'd0; dout_bits <= 8'd0;
            end

            case (st)
            S_IDLE: if (start) begin
                mode_r <= mode; key_r <= key; tag_in_r <= tag_in; tag_bits_r <= tag_bits;
                rem <= xof_bits; ad_any <= 1'b0; nblk <= 16'd0; idx <= 16'd0;
                last_bits <= 8'd0; ovf <= 1'b0;
                tag_out <= 128'd0; auth_ok <= 1'b0; err <= 1'b0; rnd <= 4'd0;
                if (mode == 2'd3 || (mode != M_XOF && (tag_bits < 8'd32 || tag_bits > 8'd128))) begin
                    err <= 1'b1; st <= S_DRAIN;
                end else if (mode == M_XOF) begin
                    s <= {256'd0, IV_XOF}; st <= S_INIT;
                end else begin
                    s <= {nonce ^ key2, key, IV_AEAD}; st <= S_INIT;
                end
            end

            S_INIT: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) begin
                    if (mode_r == M_XOF) st <= S_XABS;
                    else begin
                        s <= sr ^ {key_r, 192'd0};          // x3 ^= K[0:8], x4 ^= K[8:16]
                        st <= S_AD;
                    end
                end
            end

            S_AD: if (din_fire) begin
                if (bad_last_aead) err <= 1'b1;
                if (!din_last || din_bits != 8'd0 || ad_any) begin
                    s[127:0] <= enc_s01; ad_any <= 1'b1; last_r <= din_last;
                    rnd <= 4'd4; st <= S_ADP;
                end else begin                               // AD kosong: tanpa blok
                    s[319] <= ~s[319]; st <= S_MSG;          // pemisah domain
                end
            end

            S_ADP: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) begin
                    if (last_r) begin s <= sr ^ {1'b1, 319'd0}; st <= S_MSG; end
                    else st <= S_AD;
                end
            end

            S_MSG: if (din_fire) begin
                if (bad_last_aead) err <= 1'b1;
                if (mode_r == M_DEC) begin
                    s[127:0] <= dec_s01;
                    if (din_has_bits) begin
                        if (nblk < PT_BUF_BLOCKS) nblk <= nblk + 16'd1;
                        else ovf <= 1'b1;
                        last_bits <= din_last ? din_bits : 8'd0;
                    end
                end else begin
                    s[127:0] <= enc_s01;
                    if (din_has_bits) begin
                        dout_valid <= 1'b1; dout <= enc_s01 & dmask;
                        dout_bits <= din_last ? din_bits : 8'd128;
                    end
                end
                if (!din_last) begin
                    rnd <= 4'd4; st <= S_MSGP;
                end else begin                               // finalisasi: x2 ^= K0, x3 ^= K1
                    s[255:128] <= s[255:128] ^ key_r;
                    rnd <= 4'd0; st <= S_FIN;
                end
            end

            S_MSGP: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) st <= S_MSG;
            end

            S_FIN: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) begin
                    idx <= 16'd0;
                    if (mode_r == M_ENC) begin
                        tag_out <= tag_calc & tag_mask;
                        st <= S_DRAIN;
                    end else if (tag_ok && !ovf && !err) begin
                        auth_ok <= 1'b1; st <= S_REL;
                    end else begin
                        err <= err | ovf; st <= S_WIPE;
                    end
                end
            end

            S_REL: if (ofree) begin
                if (idx == nblk) st <= S_DRAIN;
                else begin
                    dout_valid <= 1'b1; dout <= pbuf[idx[15:0]];
                    dout_bits <= (idx == nblk - 16'd1 && last_bits != 8'd0) ? last_bits : 8'd128;
                    idx <= idx + 16'd1;
                end
            end

            S_WIPE: begin
                if (idx == nblk) st <= S_DRAIN;
                else idx <= idx + 16'd1;
            end

            S_XABS: if (din_fire) begin
                if (bad_last_xof) err <= 1'b1;
                s[63:0] <= s[63:0] ^ (din[63:0] & xmask) ^ xpad;
                last_r <= din_last; rnd <= 4'd0; st <= S_XABSP;
            end

            S_XABSP: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) st <= last_r ? S_SQ : S_XABS;
            end

            S_SQ: if (ofree) begin
                if (rem == 32'd0) st <= S_DRAIN;
                else begin
                    dout_valid <= 1'b1; dout <= {64'd0, s[63:0] & sq_mask};
                    dout_bits <= sq_bits[7:0]; rem <= rem - sq_bits;
                    if (rem > 32'd64) begin rnd <= 4'd0; st <= S_SQP; end
                    else st <= S_DRAIN;
                end
            end

            S_SQP: begin
                s <= sr; rnd <= rnd + 4'd1;
                if (perm_end) st <= S_SQ;
            end

            S_DRAIN: if (ofree) begin
                done <= 1'b1; st <= S_IDLE;
                s <= 320'd0; key_r <= 128'd0; tag_in_r <= 128'd0;
            end

            default: st <= S_IDLE;
            endcase
        end
    end

endmodule

`default_nettype wire
