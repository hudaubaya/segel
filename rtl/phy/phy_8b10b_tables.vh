// Tabel 8b/10b bersama encoder dan decoder (di-`include di dalam module).
//
// Kode ditulis abcdei fghj, `a` dikirim pertama; sebagai vektor, a = bit 9
// (sama dengan model/enc8b10b.py). RD: 0 = RD-, 1 = RD+.
//
// Asal tabel (lihat docs/phy.md, "Baseline SerDes #0200"):
//   t6  = tabel 6b encoder baseline (serdes_top.v:145-176) dengan D.0 dan D.2
//         dikembalikan ke kolom RD- (baseline memakai bentuk RD+ untuk keduanya,
//         temuan S1). 30 entri lainnya sudah sama dengan kolom RD- standar.
//   t4p = tabel 4b encoder baseline (serdes_top.v:134-141), yang ternyata persis
//         kolom RD+ standar. Bentuk RD- = komplemen untuk entri alt4.
// Bentuk RD+ 6b = komplemen bentuk RD- untuk entri alt6 (14 kode tidak netral + D.7).

function [5:0] t6;              // 5b/6b, kolom RD-
  input [4:0] x;
  case (x)
    5'd0:  t6 = 6'b100111;  // baseline: 011000 (RD+), diperbaiki
    5'd1:  t6 = 6'b011101;
    5'd2:  t6 = 6'b101101;  // baseline: 010010 (RD+), diperbaiki
    5'd3:  t6 = 6'b110001;
    5'd4:  t6 = 6'b110101;
    5'd5:  t6 = 6'b101001;
    5'd6:  t6 = 6'b011001;
    5'd7:  t6 = 6'b111000;
    5'd8:  t6 = 6'b111001;
    5'd9:  t6 = 6'b100101;
    5'd10: t6 = 6'b010101;
    5'd11: t6 = 6'b110100;
    5'd12: t6 = 6'b001101;
    5'd13: t6 = 6'b101100;
    5'd14: t6 = 6'b011100;
    5'd15: t6 = 6'b010111;
    5'd16: t6 = 6'b011011;
    5'd17: t6 = 6'b100011;
    5'd18: t6 = 6'b010011;
    5'd19: t6 = 6'b110010;
    5'd20: t6 = 6'b001011;
    5'd21: t6 = 6'b101010;
    5'd22: t6 = 6'b011010;
    5'd23: t6 = 6'b111010;
    5'd24: t6 = 6'b110011;
    5'd25: t6 = 6'b100110;
    5'd26: t6 = 6'b010110;
    5'd27: t6 = 6'b110110;
    5'd28: t6 = 6'b001110;
    5'd29: t6 = 6'b101110;
    5'd30: t6 = 6'b011110;
    default: t6 = 6'b101011;  // 31
  endcase
endfunction

// 1 = kode 6b punya dua bentuk (RD+ = komplemen RD-)
function alt6;
  input [4:0] x;
  case (x)
    5'd0, 5'd1, 5'd2, 5'd4, 5'd7, 5'd8, 5'd15, 5'd16,
    5'd23, 5'd24, 5'd27, 5'd29, 5'd30, 5'd31: alt6 = 1'b1;
    default: alt6 = 1'b0;
  endcase
endfunction

function [3:0] t4p;             // 3b/4b data, kolom RD+ (= tabel baseline)
  input [2:0] y;
  case (y)
    3'd0: t4p = 4'b0100;
    3'd1: t4p = 4'b1001;
    3'd2: t4p = 4'b0101;
    3'd3: t4p = 4'b0011;
    3'd4: t4p = 4'b0010;
    3'd5: t4p = 4'b1010;
    3'd6: t4p = 4'b0110;
    default: t4p = 4'b0001;  // D.x.P7
  endcase
endfunction

function alt4;
  input [2:0] y;
  alt4 = (y == 3'd0) || (y == 3'd3) || (y == 3'd4) || (y == 3'd7);
endfunction

// 3b/4b kontrol, kolom RD+ (RD- = komplemen untuk semua y). Sama dengan data
// kecuali y = 7 yang memakai bentuk A7.
function [3:0] t4k;
  input [2:0] y;
  t4k = (y == 3'd7) ? 4'b1000 : t4p(y);
endfunction

// D.x.A7 wajib dipakai (menghindari run 5 bit) untuk x tertentu
function a7_req;
  input [4:0] x;
  input       rd_mid;
  a7_req = rd_mid ? (x == 5'd11 || x == 5'd13 || x == 5'd14)
                  : (x == 5'd17 || x == 5'd18 || x == 5'd20);
endfunction

// K.x.7 selain K28: K23.7, K27.7, K29.7, K30.7
function kx7;
  input [4:0] x;
  kx7 = (x == 5'd23) || (x == 5'd27) || (x == 5'd29) || (x == 5'd30);
endfunction

// RD setelah sub-blok `n` bit dengan `ones` bit 1
function rd_after;
  input       rd;
  input [3:0] ones;
  input [3:0] n;
  rd_after = (2 * ones > n) ? 1'b1 : (2 * ones < n) ? 1'b0 : rd;
endfunction

function [3:0] pop6;
  input [5:0] v;
  pop6 = v[0] + v[1] + v[2] + v[3] + v[4] + v[5];
endfunction

function [3:0] pop4;
  input [3:0] v;
  pop4 = v[0] + v[1] + v[2] + v[3];
endfunction
