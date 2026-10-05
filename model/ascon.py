"""Golden model Ascon-AEAD128 dan Ascon-XOF128 (NIST SP 800-232, final Agustus 2025).

Sumber
------
Diturunkan dari implementasi referensi Python tim perancang Ascon:

    pyascon, https://github.com/meichlseder/pyascon
    commit ed24e54abf9507d26fa49b46a56091570c7e743e (2025-11-18), lisensi CC0 1.0

Yang disalin dari pyascon tanpa perubahan logika: permutasi Ascon-p
(`ascon_permutation`), konversi state little-endian, IV, urutan inisialisasi,
pemrosesan AD/plaintext/ciphertext, finalisasi, dan absorb/squeeze XOF.

Perluasan SEGEL (tidak ada di pyascon):
  1. Panjang dalam BIT untuk AD, plaintext/ciphertext, pesan XOF, dan output XOF.
     Bit ke-i sebuah string adalah bit (i mod 8) dari byte (i div 8), little-endian
     seperti konversi byte Ascon; padding `1` diletakkan di bit ke-`len`.
     pyascon hanya menerima byte; untuk panjang kelipatan 8 hasilnya identik.
  2. Tag terpotong `tag_bits` (32..128) dengan urutan bit yang sama.
  3. Nonce masking (SP 800-232): nonce yang dipakai = nonce XOR second_key.

README pyascon pada commit itu masih menyebut "initial public draft". Model ini
diverifikasi terhadap vektor resmi versi final, lihat `_self_test` dan
docs/ascon.md: vektor ACVP NIST `Ascon-AEAD128-SP800-232` dan
`Ascon-XOF128-SP800-232` (usnistgov/ACVP-Server), serta KAT ascon-c.

Jalankan `python3 model/ascon.py` untuk self-test (tanpa berkas vektor).
"""

from __future__ import annotations

MASK64 = (1 << 64) - 1

# Parameter Ascon-AEAD128 / Ascon-XOF128 (SP 800-232)
AEAD_RATE = 16   # byte
XOF_RATE = 8     # byte
PA, PB = 12, 8   # ronde inisialisasi/finalisasi, ronde per blok AEAD


# === permutasi (pyascon, disalin tanpa perubahan logika) ======================

def rotr(val: int, r: int) -> int:
    return (val >> r) | ((val & (1 << r) - 1) << (64 - r))


def round_constant(r: int) -> int:
    """Konstanta ronde ke-r dari 12 (r = 0..11): 0xf0, 0xe1, ..., 0x4b."""
    return 0xf0 - r * 0x10 + r * 0x1


def ascon_round(S: list[int], r: int) -> None:
    """Satu ronde Ascon-p dengan indeks konstanta r (0..11)."""
    S[2] ^= round_constant(r)
    S[0] ^= S[4]
    S[4] ^= S[3]
    S[2] ^= S[1]
    T = [(S[i] ^ MASK64) & S[(i + 1) % 5] for i in range(5)]
    for i in range(5):
        S[i] ^= T[(i + 1) % 5]
    S[1] ^= S[0]
    S[0] ^= S[4]
    S[3] ^= S[2]
    S[2] ^= MASK64
    S[0] ^= rotr(S[0], 19) ^ rotr(S[0], 28)
    S[1] ^= rotr(S[1], 61) ^ rotr(S[1], 39)
    S[2] ^= rotr(S[2], 1) ^ rotr(S[2], 6)
    S[3] ^= rotr(S[3], 10) ^ rotr(S[3], 17)
    S[4] ^= rotr(S[4], 7) ^ rotr(S[4], 41)


def ascon_permutation(S: list[int], rounds: int = 1) -> None:
    assert rounds <= 12
    for r in range(12 - rounds, 12):
        ascon_round(S, r)


# === konversi (pyascon) ======================================================

def bytes_to_int(b: bytes) -> int:
    return sum(x << (8 * i) for i, x in enumerate(b))


def int_to_bytes(v: int, n: int) -> bytes:
    return bytes((v >> (8 * i)) & 0xFF for i in range(n))


def bytes_to_state(b: bytes) -> list[int]:
    return [bytes_to_int(b[8 * w:8 * (w + 1)]) for w in range(5)]


# === bit string little-endian (perluasan SEGEL) ==============================

def nbytes(bits: int) -> int:
    return (bits + 7) // 8


def truncate_bits(data: bytes, bits: int) -> bytes:
    """`bits` bit pertama dari `data`; bit sisa di byte terakhir dinolkan."""
    out = bytearray(data[:nbytes(bits)])
    if len(out) < nbytes(bits):
        raise ValueError("data lebih pendek dari jumlah bit")
    if bits % 8:
        out[-1] &= (1 << (bits % 8)) - 1
    return bytes(out)


def pad_bits(data: bytes, bits: int, rate: int) -> bytes:
    """data (bits bit) || 1 || 0*, sampai kelipatan `rate` byte."""
    out = bytearray(truncate_bits(data, bits))
    if bits % 8 == 0:
        out.append(0)
    out[bits // 8] |= 1 << (bits % 8)
    out += bytes(-len(out) % rate)
    return bytes(out)


# === Ascon-AEAD128 ===========================================================

def _iv_aead() -> bytes:
    version, taglen = 1, 128
    return bytes([version, 0, (PB << 4) + PA]) + int_to_bytes(taglen, 2) + bytes([AEAD_RATE, 0, 0])


def aead_init(key: bytes, nonce: bytes, second_key: bytes | None = None) -> list[int]:
    assert len(key) == 16 and len(nonce) == 16
    if second_key is not None:  # nonce masking
        assert len(second_key) == 16
        nonce = bytes(a ^ b for a, b in zip(nonce, second_key))
    S = bytes_to_state(_iv_aead() + key + nonce)
    ascon_permutation(S, PA)
    S[3] ^= bytes_to_int(key[0:8])
    S[4] ^= bytes_to_int(key[8:16])
    return S


def aead_absorb_ad(S: list[int], ad: bytes, ad_bits: int) -> None:
    if ad_bits > 0:
        padded = pad_bits(ad, ad_bits, AEAD_RATE)
        for i in range(0, len(padded), AEAD_RATE):
            S[0] ^= bytes_to_int(padded[i:i + 8])
            S[1] ^= bytes_to_int(padded[i + 8:i + 16])
            ascon_permutation(S, PB)
    S[4] ^= 1 << 63  # pemisah domain


def aead_finalize(S: list[int], key: bytes) -> bytes:
    S[2] ^= bytes_to_int(key[0:8])
    S[3] ^= bytes_to_int(key[8:16])
    ascon_permutation(S, PA)
    S[3] ^= bytes_to_int(key[0:8])
    S[4] ^= bytes_to_int(key[8:16])
    return int_to_bytes(S[3], 8) + int_to_bytes(S[4], 8)


def aead_encrypt(key: bytes, nonce: bytes, ad: bytes, pt: bytes, ad_bits: int | None = None,
                 pt_bits: int | None = None, tag_bits: int = 128,
                 second_key: bytes | None = None) -> tuple[bytes, bytes]:
    """Kembalikan (ciphertext, tag). Panjang default = len * 8."""
    ad_bits = len(ad) * 8 if ad_bits is None else ad_bits
    pt_bits = len(pt) * 8 if pt_bits is None else pt_bits
    S = aead_init(key, nonce, second_key)
    aead_absorb_ad(S, ad, ad_bits)
    padded = pad_bits(pt, pt_bits, AEAD_RATE)
    ct = b""
    for i in range(0, len(padded), AEAD_RATE):
        S[0] ^= bytes_to_int(padded[i:i + 8])
        S[1] ^= bytes_to_int(padded[i + 8:i + 16])
        ct += int_to_bytes(S[0], 8) + int_to_bytes(S[1], 8)
        if i + AEAD_RATE < len(padded):
            ascon_permutation(S, PB)
    tag = aead_finalize(S, key)
    return truncate_bits(ct, pt_bits), truncate_bits(tag, tag_bits)


def aead_decrypt(key: bytes, nonce: bytes, ad: bytes, ct: bytes, tag: bytes,
                 ad_bits: int | None = None, ct_bits: int | None = None, tag_bits: int = 128,
                 second_key: bytes | None = None) -> bytes | None:
    """Kembalikan plaintext, atau None kalau tag tidak cocok."""
    ad_bits = len(ad) * 8 if ad_bits is None else ad_bits
    ct_bits = len(ct) * 8 if ct_bits is None else ct_bits
    S = aead_init(key, nonce, second_key)
    aead_absorb_ad(S, ad, ad_bits)
    full = ct_bits // 128
    pt = b""
    for blk in range(full):
        c = ct[16 * blk:16 * blk + 16]
        c0, c1 = bytes_to_int(c[0:8]), bytes_to_int(c[8:16])
        pt += int_to_bytes(S[0] ^ c0, 8) + int_to_bytes(S[1] ^ c1, 8)
        S[0], S[1] = c0, c1
        ascon_permutation(S, PB)
    # blok terakhir (0..127 bit) + padding
    lb = ct_bits - 128 * full
    last = truncate_bits(ct[16 * full:], lb) + bytes(16)
    c = bytes_to_int(last[:16])
    s = S[0] | (S[1] << 64)
    keep = ((1 << 128) - 1) ^ ((1 << lb) - 1)         # bit yang tidak tertimpa ciphertext
    p = (s ^ c) & ((1 << lb) - 1)
    s = (s & keep) ^ c ^ (1 << lb)
    S[0], S[1] = s & MASK64, s >> 64
    pt += int_to_bytes(p, 16)
    pt = truncate_bits(pt, ct_bits)
    exp = aead_finalize(S, key)
    if truncate_bits(exp, tag_bits) == truncate_bits(tag, tag_bits):
        return pt
    return None


# === Ascon-XOF128 ============================================================

def _iv_xof() -> bytes:
    version, taglen = 3, 0
    return bytes([version, 0, (12 << 4) + 12]) + int_to_bytes(taglen, 2) + bytes([XOF_RATE, 0, 0])


def xof_init() -> list[int]:
    S = bytes_to_state(_iv_xof() + bytes(32))
    ascon_permutation(S, 12)
    return S


def xof(msg: bytes, out_bits: int, msg_bits: int | None = None) -> bytes:
    msg_bits = len(msg) * 8 if msg_bits is None else msg_bits
    S = xof_init()
    padded = pad_bits(msg, msg_bits, XOF_RATE)
    for i in range(0, len(padded), XOF_RATE):
        S[0] ^= bytes_to_int(padded[i:i + 8])
        ascon_permutation(S, 12)
    out = b""
    while len(out) * 8 < out_bits:
        out += int_to_bytes(S[0], 8)
        if len(out) * 8 < out_bits:
            ascon_permutation(S, 12)
    return truncate_bits(out, out_bits)


# === self-test ===============================================================

def _self_test() -> None:
    # KAT ascon-c @446347f (crypto_aead/asconaead128/LWC_AEAD_KAT_128_128.txt
    # Count = 1, 2; crypto_hash/asconxof128/LWC_XOF_KAT_128_512.txt Count = 1).
    k = bytes(range(16))
    n = bytes(range(16, 32))
    ct, tag = aead_encrypt(k, n, b"", b"")
    assert (ct + tag).hex().upper() == "4F9C278211BEC9316BF68F46EE8B2EC6", (ct + tag).hex()
    ct, tag = aead_encrypt(k, n, b"\x30", b"")
    assert (ct + tag).hex().upper() == "CCCB674FE18A09A285D6AB11B35675C0", (ct + tag).hex()
    assert xof(b"", 256).hex().upper() == \
        "473D5E6164F58B39DFD84AACDB8AE42EC2D91FED33388EE0D960D9B3993295C6", xof(b"", 256).hex()
    # Konsistensi: dekripsi membalik enkripsi untuk semua panjang bit 0..300
    import random
    rng = random.Random(1)
    for bits in list(range(0, 300)) + [1024, 1031]:
        ad_bits = rng.randrange(0, 300)
        k, n = rng.randbytes(16), rng.randbytes(16)
        ad, pt = rng.randbytes(nbytes(ad_bits)), rng.randbytes(nbytes(bits))
        ct, tag = aead_encrypt(k, n, ad, pt, ad_bits, bits)
        assert aead_decrypt(k, n, ad, ct, tag, ad_bits, bits) == truncate_bits(pt, bits)
        bad = bytearray(tag)
        bad[rng.randrange(16)] ^= 1 << rng.randrange(8)
        assert aead_decrypt(k, n, ad, ct, bytes(bad), ad_bits, bits) is None
    print("model/ascon.py: OK")


if __name__ == "__main__":
    _self_test()
