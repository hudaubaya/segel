"""Test unit PHY: encoder/decoder 8b/10b (exhaustive vs model/enc8b10b.py) dan
deserializer + comma aligner (10 geseran bit, ketahanan terhadap comma palsu)."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import enc8b10b as M

K28_5 = 0xBC
VALID_K = {x | (y << 5) for x, y in M.K_CODES}


def rd_bit(rd):
    return 1 if rd > 0 else 0


@cocotb.test()
async def test_encoder_exhaustive(dut):
    """256 data + 12 K pada kedua RD = model; K tidak sah -> k_err."""
    n = 0
    for rd in (-1, 1):
        for kin in (0, 1):
            for b in range(256):
                dut.enc_din.value = b
                dut.enc_k.value = kin
                dut.enc_rd.value = rd_bit(rd)
                await Timer(1, "ns")
                if kin and b not in VALID_K:
                    assert int(dut.enc_k_err.value) == 1, f"K {b:#04x} tidak sah tanpa k_err"
                    continue
                code, nrd = M.encode(b, rd, k=bool(kin))
                got = int(dut.enc_code.value)
                assert got == code, f"{'K' if kin else 'D'} {b:#04x} RD{rd:+d}: " \
                                    f"{M.code_str(got)} != {M.code_str(code)}"
                assert int(dut.enc_rd_out.value) == rd_bit(nrd)
                assert int(dut.enc_k_err.value) == 0
                n += 1
    assert n == 2 * (256 + len(M.K_CODES))
    dut._log.info("encoder: %d kode cocok dengan model, %d K tidak sah ditandai",
                  n, 2 * (256 - len(VALID_K)))


@cocotb.test()
async def test_decoder_exhaustive(dut):
    """Semua 1024 kode 10 bit pada kedua RD: data, k, illegal, disp_err, RD baru."""
    stats = dict(ok=0, illegal=0, disp=0)
    for rd in (-1, 1):
        for code in range(1024):
            dut.dec_code.value = code
            dut.dec_rd.value = rd_bit(rd)
            await Timer(1, "ns")
            b, k, ill, dis, nrd = M.decode(code, rd)
            name = f"{M.code_str(code)} RD{rd:+d}"
            assert int(dut.dec_illegal.value) == ill, f"{name}: illegal"
            assert int(dut.dec_disp_err.value) == dis, f"{name}: disp_err"
            assert int(dut.dec_rd_out.value) == rd_bit(nrd), f"{name}: RD"
            if not ill:
                assert int(dut.dec_dout.value) == b and int(dut.dec_k.value) == k, f"{name}: data"
            stats["illegal" if ill else "disp" if dis else "ok"] += 1
    dut._log.info("decoder: 2048 kasus cocok dengan model: %s", stats)


# ---------------------------------------------------------------- aligner

def encode_stream(syms, rd=-1):
    """[(byte, k)] -> (bit list, [kode]) dengan RD dilacak."""
    bits, codes = [], []
    for b, k in syms:
        code, rd = M.encode(b, rd, k=k)
        codes.append(code)
        bits += [int(c) for c in f"{code:010b}"]
    return bits, codes, rd


def has_comma(bits, start, end):
    s = "".join(map(str, bits))
    return [i for i in range(start, end) if s[i:i + 7] in ("0011111", "1100000")]


async def align_run(dut, bits):
    """Reset aligner, kirim bit (satu per clock), kembalikan [(word, align, phase)]."""
    dut.rst.value = 1
    dut.ser.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    out = []
    for i in range(len(bits) + 3):
        dut.ser.value = bits[i] if i < len(bits) else 0
        await RisingEdge(dut.clk)
        if int(dut.word_valid.value):
            out.append((int(dut.word.value), int(dut.align.value), int(dut.phase.value)))
    return out


def symbols(rng, n):
    return [(rng.randrange(256), False) for _ in range(n)]


@cocotb.test()
async def test_align_all_shifts(dut):
    """Comma K28.5 ditemukan pada 10 geseran bit; word sesudahnya sama dengan kode."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    rng = random.Random(10)
    phases = {}
    for shift in range(10):
        syms = [(K28_5, True)] * 3 + symbols(rng, 40)
        bits, codes, _ = encode_stream(syms)
        while True:                          # awalan acak tanpa comma
            pre = [rng.randrange(2) for _ in range(shift)]
            if not has_comma(pre + bits, 0, shift):
                break
        out = await align_run(dut, pre + bits)
        words = [w for w, _, _ in out]
        assert words[:len(codes)] == codes, f"geseran {shift}: word salah"
        assert out[0][1] == 1, "word pertama harus comma yang mengunci"
        assert int(dut.realign_cnt.value) == 0
        phases[shift] = out[0][2]
    assert len(set(phases.values())) == 10, f"phase tidak mencakup 10 posisi: {phases}"
    assert all(phases[s] == (phases[0] + s) % 10 for s in range(10)), phases
    dut._log.info("10 geseran bit -> phase %s, semua word benar", phases)


@cocotb.test()
async def test_align_false_comma(dut):
    """Satu comma palsu tidak menggeser framing; slip bit nyata -> realign di comma ke-2."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    rng = random.Random(11)

    # 1) comma palsu: 7 bit di posisi tidak sejajar ditimpa 0011111
    syms = [(K28_5, True)] * 2 + symbols(rng, 6) + [(K28_5, True)] * 4 + symbols(rng, 6)
    bits, codes, _ = encode_stream(syms)
    for p in range(21, 80):                           # simbol data 2..7, tidak sejajar
        if p % 10 == 0:
            continue
        cand = bits[:p] + [0, 0, 1, 1, 1, 1, 1] + bits[p + 7:]
        if len([c for c in has_comma(cand, 0, len(cand) - 7) if c % 10]) == 1:
            bits = cand
            break
    else:
        raise AssertionError("tidak menemukan posisi comma palsu")
    out = await align_run(dut, bits)
    assert int(dut.realign_cnt.value) == 0, "comma palsu tunggal memicu realign"
    assert all(ph == out[0][2] for _, _, ph in out), "phase berubah"
    assert [w for w, _, _ in out][8:len(codes)] == codes[8:], "framing rusak setelah comma palsu"

    # 2) dua comma palsu di phase yang SAMA tetapi tidak di word berurutan
    #    (dua galat terpisah, tanpa IDLE di antaranya): tidak boleh realign
    syms = [(K28_5, True)] * 2 + symbols(rng, 12) + [(K28_5, True)] * 2 + symbols(rng, 3)
    bits, codes, _ = encode_stream(syms)
    placed = []
    for p in range(21, 120):
        if p % 10 != 3 or len(placed) == 2 or (placed and p - placed[-1] < 30):
            continue
        cand = bits[:p] + [0, 0, 1, 1, 1, 1, 1] + bits[p + 7:]
        if len([c for c in has_comma(cand, 0, len(cand) - 7) if c % 10]) == len(placed) + 1:
            bits = cand
            placed.append(p)
    assert len(placed) == 2, placed
    out = await align_run(dut, bits)
    assert int(dut.realign_cnt.value) == 0, f"dua comma palsu terpisah memicu realign {placed}"
    assert [w for w, _, _ in out][14:len(codes)] == codes[14:], "framing rusak"

    # 3) slip nyata: sisipkan 3 bit, lalu comma di phase baru
    syms1 = [(K28_5, True)] * 2 + symbols(rng, 5)
    bits1, codes1, rd = encode_stream(syms1)
    syms2 = [(K28_5, True)] * 3 + symbols(rng, 5)
    bits2, codes2, _ = encode_stream(syms2, rd)
    out = await align_run(dut, bits1 + [0, 1, 0] + bits2)
    aligns = [i for i, (_, a, _) in enumerate(out) if a]
    assert len(aligns) == 2, f"harus 1 lock + 1 realign, dapat {aligns}"
    assert int(dut.realign_cnt.value) == 1
    # realign tepat di comma ke-2 phase baru: word sesudahnya = sisa codes2
    after = [w for w, _, _ in out[aligns[1]:]]
    assert after[:len(codes2) - 1] == codes2[1:], "word setelah realign salah"
    dut._log.info("comma palsu tunggal / dua terpisah: tidak realign; "
                  "slip 3 bit: realign di comma ke-2 berurutan")
