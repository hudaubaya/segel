"""Model referensi 8b/10b (Widmer & Franaszek, IEEE 802.3 cl. 36).

Kode ditulis dalam urutan standar `abcdei fghj`: bit `a` dikirim pertama.
Sebagai integer 10 bit, `a` adalah bit 9 dan `j` adalah bit 0.

Running disparity (RD) direpresentasikan -1 (RD-) atau +1 (RD+). Nilai awal
standar setelah reset adalah RD-.

Jalankan langsung (`python3 model/enc8b10b.py`) untuk self-test.
"""

# 5b/6b: EDCBA -> (abcdei untuk RD-, abcdei untuk RD+)
_6B = {
    0: ("100111", "011000"), 1: ("011101", "100010"), 2: ("101101", "010010"),
    3: ("110001", "110001"), 4: ("110101", "001010"), 5: ("101001", "101001"),
    6: ("011001", "011001"), 7: ("111000", "000111"), 8: ("111001", "000110"),
    9: ("100101", "100101"), 10: ("010101", "010101"), 11: ("110100", "110100"),
    12: ("001101", "001101"), 13: ("101100", "101100"), 14: ("011100", "011100"),
    15: ("010111", "101000"), 16: ("011011", "100100"), 17: ("100011", "100011"),
    18: ("010011", "010011"), 19: ("110010", "110010"), 20: ("001011", "001011"),
    21: ("101010", "101010"), 22: ("011010", "011010"), 23: ("111010", "000101"),
    24: ("110011", "001100"), 25: ("100110", "100110"), 26: ("010110", "010110"),
    27: ("110110", "001001"), 28: ("001110", "001110"), 29: ("101110", "010001"),
    30: ("011110", "100001"), 31: ("101011", "010100"),
}
_6B_K28 = ("001111", "110000")

# 3b/4b data: HGF -> (fghj RD-, fghj RD+); indeks 7 = D.x.P7
_4B_D = {
    0: ("1011", "0100"), 1: ("1001", "1001"), 2: ("0101", "0101"),
    3: ("1100", "0011"), 4: ("1101", "0010"), 5: ("1010", "1010"),
    6: ("0110", "0110"), 7: ("1110", "0001"),
}
_4B_A7 = ("0111", "1000")
# 3b/4b kontrol (K.x.y)
_4B_K = {
    0: ("1011", "0100"), 1: ("0110", "1001"), 2: ("1010", "0101"),
    3: ("1100", "0011"), 4: ("1101", "0010"), 5: ("0101", "1010"),
    6: ("1001", "0110"), 7: ("0111", "1000"),
}

# Kode kontrol yang valid: K28.0-7, K23.7, K27.7, K29.7, K30.7
K_CODES = [(28, y) for y in range(8)] + [(23, 7), (27, 7), (29, 7), (30, 7)]
K28_5 = 0xBC  # byte K28.5 (comma)


def _disp(bits: str) -> int:
    return 2 * bits.count("1") - len(bits)


def _pick(pair, rd):
    return pair[0] if rd < 0 else pair[1]


def _after(rd: int, sub: str) -> int:
    d = _disp(sub)
    return rd if d == 0 else (1 if d > 0 else -1)


def encode(byte: int, rd: int, k: bool = False):
    """Kembalikan (kode 10 bit sebagai int abcdeifghj, RD baru)."""
    x, y = byte & 0x1F, (byte >> 5) & 0x7
    if k:
        if (x, y) not in K_CODES:
            raise ValueError(f"K.{x}.{y} bukan kode kontrol yang valid")
        six = _pick(_6B_K28 if x == 28 else _6B[x], rd)
        rd1 = _after(rd, six)
        four = _pick(_4B_K[y], rd1)
    else:
        six = _pick(_6B[x], rd)
        rd1 = _after(rd, six)
        if y == 7 and ((rd1 < 0 and x in (17, 18, 20)) or (rd1 > 0 and x in (11, 13, 14))):
            four = _pick(_4B_A7, rd1)
        else:
            four = _pick(_4B_D[y], rd1)
    rd2 = _after(rd1, four)
    return int(six + four, 2), rd2


def _build_decode():
    table = {}
    for rd in (-1, 1):
        for b in range(256):
            code, _ = encode(b, rd)
            table.setdefault(code, set()).add((b, False))
        for x, y in K_CODES:
            code, _ = encode(x | (y << 5), rd, k=True)
            table.setdefault(code, set()).add((x | (y << 5), True))
    return table


DECODE = _build_decode()


def _build_legal():
    """{rd: {kode: (byte, k)}}: kode yang sah bila diterima pada RD tersebut."""
    legal = {-1: {}, 1: {}}
    for rd in (-1, 1):
        for b in range(256):
            legal[rd][encode(b, rd)[0]] = (b, False)
        for x, y in K_CODES:
            legal[rd][encode(x | (y << 5), rd, k=True)[0]] = (x | (y << 5), True)
    return legal


LEGAL = _build_legal()


def decode(code: int, rd: int):
    """Dekode satu kode 10 bit pada running disparity `rd`.

    Kembalikan (byte, k, illegal, disp_err, rd_baru):
      - kode sah pada `rd`: byte/k hasil dekode, kedua flag 0
      - kode hanya sah pada RD lawan: galat disparity; byte/k dari RD lawan
      - kode tidak ada di tabel mana pun: illegal; byte/k = None
    RD baru mengikuti disparity kode yang diterima (tidak berubah kalau 0), juga
    untuk kode yang salah, supaya penerima pulih sendiri.
    """
    d = disparity(code)
    rd_next = rd if d == 0 else (1 if d > 0 else -1)
    if code in LEGAL[rd]:
        b, k = LEGAL[rd][code]
        return b, k, False, False, rd_next
    if code in LEGAL[-rd]:
        b, k = LEGAL[-rd][code]
        return b, k, False, True, rd_next
    return None, None, True, False, rd_next


def code_str(code: int) -> str:
    s = f"{code:010b}"
    return f"{s[:6]} {s[6:]}"


def disparity(code: int) -> int:
    return _disp(f"{code:010b}")


def _self_test() -> None:
    # Nilai yang umum dikutip dari tabel standar
    assert encode(K28_5, -1, k=True) == (0b0011111010, 1)
    assert encode(K28_5, +1, k=True) == (0b1100000101, -1)
    assert encode(0x00, -1)[0] == 0b1001110100      # D.0.0 RD-
    assert encode(0x00, +1)[0] == 0b0110001011      # D.0.0 RD+
    assert encode(0xB5, -1)[0] == 0b1010101010      # D.21.5
    assert encode(0xF1, -1)[0] == 0b1000110111      # D.17.7 (A7) RD-
    assert encode(0xEB, +1)[0] == 0b1101001000      # D.11.7 (A7) RD+
    # Setiap simbol: disparity 0 atau sesuai arah RD, RD baru konsisten
    for rd in (-1, 1):
        for b in range(256):
            code, nrd = encode(b, rd)
            d = disparity(code)
            assert d in (0, -2 * rd), (b, rd, d)
            assert nrd == (rd if d == 0 else -rd)
    # Satu kode 10 bit hanya punya satu arti
    assert all(len(v) == 1 for v in DECODE.values())
    assert len(DECODE) == len({c for c in DECODE})
    # Aliran data acak: run length <= 5 dan tidak ada comma (0011111/1100000)
    import random
    rng = random.Random(1)
    rd, bits = -1, ""
    for _ in range(20000):
        code, rd = encode(rng.randrange(256), rd)
        bits += f"{code:010b}"
    assert "000000" not in bits and "111111" not in bits
    assert "0011111" not in bits and "1100000" not in bits
    # Dekoder: 268 kode sah per RD (256 data + 12 K), invers encoder, flag benar
    assert len(LEGAL[-1]) == len(LEGAL[1]) == 268
    for rd in (-1, 1):
        for b in range(256):
            code, nrd = encode(b, rd)
            assert decode(code, rd) == (b, False, False, False, nrd)
        for x, y in K_CODES:
            code, nrd = encode(x | (y << 5), rd, k=True)
            assert decode(code, rd) == (x | (y << 5), True, False, False, nrd)
    assert decode(0b0000000000, -1)[2] and decode(0b1111111111, 1)[2]
    d121 = encode(0x21, -1)[0]                  # D.1.1 bentuk RD-, diterima di RD+
    assert decode(d121, 1)[:4] == (0x21, False, False, True)
    # K28.5 memuat comma
    assert "0011111" in f"{encode(K28_5, -1, k=True)[0]:010b}"
    print("model/enc8b10b.py: OK")


if __name__ == "__main__":
    _self_test()
