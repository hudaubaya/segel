// PRBS-31 (ITU-T O.150): x^31 + x^28 + 1. Bit keluaran = s[30] ^ s[27], lalu state
// digeser ke kiri dengan bit itu masuk di LSB. Satu byte = 8 bit berurutan, bit
// pertama di MSB. Model yang sama: tb/fpga_loopback/test.py (prbs31_bytes).

function [38:0] prbs31_byte;     // {state baru [30:0], byte [7:0]}
    input [30:0] s;
    reg   [30:0] t;
    reg   [7:0]  b;
    reg          nb;
    integer      i;
    begin
        t = s;
        for (i = 0; i < 8; i = i + 1) begin
            nb = t[30] ^ t[27];
            b  = {b[6:0], nb};
            t  = {t[29:0], nb};
        end
        prbs31_byte = {t, b};
    end
endfunction
