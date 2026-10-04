"""Audit cocotb baseline TT07 #0200 (tt_um_serdes), apa adanya.

Setiap test memeriksa perilaku menurut 8b/10b standar (model/enc8b10b.py).
Test untuk cacat yang sudah terkonfirmasi ditandai `expect_fail=True` dengan
ID temuan di docs/baseline_audit.md, sehingga suite ini hijau selama cacat
masih ada dan menjadi merah kalau baseline berubah perilaku.

Notasi:
  - "std"    : kode standar abcdeifghj, `a` dikirim pertama (bit 9 = a).
  - "native" : word internal DUT {temp_4b, temp_6b} = {fghj, abcdei} dengan
               asumsi literal di RTL ditulis MSB = a / f (lihat docs).
Pin: uio_in[0]=ser_in, [2]=data_en, [3]=par_en, [4]=ser_en; uo_out=data_out.
"""

import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

import enc8b10b as m

SER_IN, DATA_EN, PAR_EN, SER_EN = 0, 2, 3, 4
REPORT = os.path.join(os.getcwd(), "audit_serdes.json")


# --- konversi notasi -------------------------------------------------------

def native_to_std(w: int) -> int:
    """{fghj, abcdei} -> abcdeifghj."""
    return ((w & 0x3F) << 4) | (w >> 6)


def std_to_native(c: int) -> int:
    """abcdeifghj -> {fghj, abcdei}."""
    return ((c & 0xF) << 6) | (c >> 4)


def bits_msb_first(v: int, n: int = 10):
    return [(v >> (n - 1 - i)) & 1 for i in range(n)]


def save(key, value):
    data = {}
    if os.path.exists(REPORT):
        with open(REPORT) as f:
            data = json.load(f)
    data[key] = value
    with open(REPORT, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)


# --- driver pin ------------------------------------------------------------

async def setup(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, units="us").start())
    for _ in range(3):
        await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


async def cyc(dut, ser_in=0, data_en=0, par_en=0, ser_en=0):
    dut.uio_in.value = ((ser_in << SER_IN) | (data_en << DATA_EN)
                        | (par_en << PAR_EN) | (ser_en << SER_EN))
    await FallingEdge(dut.clk)


async def encode(dut, byte):
    """Encode satu byte lewat pin; kembalikan word native 10 bit."""
    dut.ui_in.value = byte
    await cyc(dut, data_en=1)   # latch_8bit <= byte
    await cyc(dut)              # encoder: temp <= tabel(byte)
    await cyc(dut, ser_en=1)    # encoder: data_10b_out <= temp
    return int(dut.dut.serdes_inst.data_10b_encoded.value)


async def serialize(dut, byte):
    """Encode + kirim; kembalikan 10 bit dalam urutan keluar dari PISO."""
    word = await encode(dut, byte)
    await cyc(dut, data_en=1, ser_en=1)  # latch_10bit <= word
    await cyc(dut, ser_en=1)             # PISO load
    out = []
    for _ in range(10):
        await cyc(dut)                   # shift, ser_out <= shift_reg[0]
        out.append(int(dut.dut.serdes_inst.ser_out.value))
    return word, out


async def decode_bits(dut, bits):
    """Masukkan bit serial (urutan waktu) ke ser_in, lalu jalankan pipeline RX."""
    for b in bits:
        await cyc(dut, ser_in=b)         # SIPO shift kiri, bit pertama -> bit 9
    await cyc(dut, par_en=1)             # par_out <= shift_reg
    await cyc(dut, data_en=1)            # latch_10bit RX <= par_out
    await cyc(dut)                       # decoder: temp <= tabel(word)
    await cyc(dut, par_en=1)             # decoder: data_8b_out <= temp
    await cyc(dut, data_en=1)            # latch_8bit RX -> uo_out
    return int(dut.uo_out.value)


async def decode_native(dut, word):
    """Masukkan word native sehingga par_out == word."""
    return await decode_bits(dut, bits_msb_first(word))


# --- yang benar ------------------------------------------------------------

@cocotb.test()
async def test_subblocks_are_standard(dut):
    """Setiap sub-blok 6b/4b keluaran encoder adalah salah satu entri tabel standar."""
    await setup(dut)
    col6 = {"RD-": 0, "RD+": 0, "netral": 0}
    col4 = {"RD-": 0, "RD+": 0, "netral": 0}
    for b in range(256):
        w = await encode(dut, b)
        six, four = f"{w & 0x3F:06b}", f"{w >> 6:04b}"
        x, y = b & 0x1F, b >> 5
        p6, p4 = m._6B[x], m._4B_D[y]
        assert six in p6, f"0x{b:02x}: 6b {six} bukan {p6}"
        assert four in p4, f"0x{b:02x}: 4b {four} bukan {p4}"
        if b < 32:
            col6["netral" if p6[0] == p6[1] else ("RD-" if six == p6[0] else "RD+")] += 1
        if x == 0:
            col4["netral" if p4[0] == p4[1] else ("RD-" if four == p4[0] else "RD+")] += 1
    save("subblock_columns", {"6b_dari_32": col6, "4b_dari_8": col4})
    dut._log.info("kolom 6b: %s, kolom 4b: %s", col6, col4)


@cocotb.test()
async def test_decoder_inverts_encoder_native(dut):
    """Decoder mengembalikan byte asal untuk word encoder-nya sendiri (layout native)."""
    await setup(dut)
    words = [await encode(dut, b) for b in range(256)]
    for b, w in enumerate(words):
        got = await decode_native(dut, w)
        assert got == b, f"0x{b:02x}: word {w:010b} -> 0x{got:02x}"


# --- encoder vs standar ----------------------------------------------------

async def _encoder_vs_rd(dut, rd):
    await setup(dut)
    bad = []
    for b in range(256):
        got = native_to_std(await encode(dut, b))
        exp, _ = m.encode(b, rd)
        if got != exp:
            bad.append(b)
    return bad


@cocotb.test(expect_fail=True)  # S1
async def test_encoder_table_rd_minus(dut):
    """Semua 256 byte cocok dengan kolom RD- standar."""
    bad = await _encoder_vs_rd(dut, -1)
    save("encoder_mismatch_rd_minus", len(bad))
    assert not bad, f"{len(bad)}/256 byte tidak cocok RD-"


@cocotb.test(expect_fail=True)  # S1
async def test_encoder_table_rd_plus(dut):
    """Semua 256 byte cocok dengan kolom RD+ standar."""
    bad = await _encoder_vs_rd(dut, +1)
    save("encoder_mismatch_rd_plus", len(bad))
    assert not bad, f"{len(bad)}/256 byte tidak cocok RD+"


@cocotb.test()
async def test_encoder_stats(dut):
    """Statistik word encoder (bukan assertion): validitas, disparity, DC balance."""
    await setup(dut)
    either = invalid = 0
    disp = {}
    worst = []
    words = {}
    for b in range(256):
        w = await encode(dut, b)
        words[b] = w
        c = native_to_std(w)
        d = m.disparity(c)
        disp[d] = disp.get(d, 0) + 1
        if c in (m.encode(b, -1)[0], m.encode(b, 1)[0]):
            either += 1
        if c not in m.DECODE:
            invalid += 1
            if abs(d) > 2:
                worst.append(f"0x{b:02x}={m.code_str(c)} (disp {d:+d})")

    # Aliran 10.000 byte acak: running digital sum (RDS), run terpanjang, comma.
    def stream_stats(order):
        rng = random.Random(7)
        rds = peak = 0
        bits = []
        for _ in range(10000):
            w = words[rng.randrange(256)]
            seq = order(w)
            rds += 2 * sum(seq) - 10
            peak = max(peak, abs(rds))
            bits.extend(seq)
        s = "".join(map(str, bits))
        runs = max(len(r) for r in s.replace("01", "0 1").replace("10", "1 0").split())
        return {"rds_akhir": rds, "rds_maks": peak, "run_terpanjang": runs,
                "comma_di_aliran_data": ("0011111" in s) or ("1100000" in s)}

    save("encoder_stats", {
        "cocok_salah_satu_kolom": either,
        "bukan_codeword_valid": invalid,
        "histogram_disparity": {str(k): v for k, v in sorted(disp.items())},
        "contoh_disparity_lebih_dari_2": worst[:8],
        "aliran_urutan_standar": stream_stats(lambda w: bits_msb_first(native_to_std(w))),
        "aliran_urutan_kabel_dut": stream_stats(lambda w: [(w >> i) & 1 for i in range(10)]),
    })


@cocotb.test(expect_fail=True)  # S2
async def test_encoder_running_disparity(dut):
    """Aliran 2000 byte acak mengikuti running disparity standar (mulai RD-)."""
    await setup(dut)
    rng = random.Random(0x8B10B)
    rd = -1
    bad = 0
    for i in range(2000):
        b = rng.randrange(256)
        exp, rd = m.encode(b, rd)
        bad += native_to_std(await encode(dut, b)) != exp
    save("running_disparity_salah_dari_2000", bad)
    assert bad == 0, f"{bad}/2000 simbol tidak sesuai running disparity"


@cocotb.test(expect_fail=True)  # S3
async def test_k28_5(dut):
    """K28.5 bisa dikirim (RD- 001111 1010 atau RD+ 110000 0101)."""
    await setup(dut)
    got = native_to_std(await encode(dut, m.K28_5))
    k = {m.encode(m.K28_5, rd, k=True)[0] for rd in (-1, 1)}
    save("byte_0xBC_menjadi", m.code_str(got))
    assert got in k, f"0xBC -> {m.code_str(got)} (D28.5), bukan K28.5"


# --- serializer ------------------------------------------------------------

@cocotb.test(expect_fail=True)  # S4
async def test_serial_on_pin(dut):
    """Bit serial muncul di pin ser_out datasheet (uio[1]) dengan uio_oe[1] = 1."""
    await setup(dut)
    word = await encode(dut, 0x5A)
    await cyc(dut, data_en=1, ser_en=1)
    await cyc(dut, ser_en=1)
    internal, pin1, pin0, oe = [], [], [], set()
    for _ in range(10):
        await cyc(dut)
        internal.append(str(int(dut.dut.serdes_inst.ser_out.value)))
        uo = dut.uio_out.value.binstr  # MSB dulu: [-1] = uio_out[0], [-2] = uio_out[1]
        pin0.append(uo[-1])
        pin1.append(uo[-2])
        oe.add(dut.uio_oe.value.binstr)
    save("pin_serial_0x5A", {"ser_out_internal": "".join(internal),
                             "uio_out[1]_datasheet": "".join(pin1),
                             "uio_out[0]": "".join(pin0),
                             "uio_oe": sorted(oe)})
    assert "".join(pin1) == "".join(internal) and all(int(o, 2) & 0b10 for o in oe), (
        f"uio_out[1]={''.join(pin1)}, uio_out[0]={''.join(pin0)}, uio_oe={sorted(oe)}, "
        f"internal={''.join(internal)}")


@cocotb.test(expect_fail=True)  # S5
async def test_serial_bit_order(dut):
    """Bit dikirim dalam urutan standar a,b,c,d,e,i,f,g,h,j."""
    await setup(dut)
    word, bits = await serialize(dut, 0x5A)
    exp = bits_msb_first(native_to_std(word))
    save("urutan_serial_0x5A", {"terkirim": "".join(map(str, bits)),
                                "urutan_standar": "".join(map(str, exp))})
    assert bits == exp, f"terkirim {bits}, standar {exp}"


@cocotb.test(expect_fail=True)  # S6
async def test_loopback(dut):
    """TX -> kabel ideal -> RX mengembalikan byte asal (framing ideal)."""
    await setup(dut)
    ok = 0
    for b in range(256):
        _, bits = await serialize(dut, b)
        ok += (await decode_bits(dut, bits)) == b
    save("loopback_benar_dari_256", ok)
    assert ok == 256, f"hanya {ok}/256 byte lolos loopback"


# --- decoder vs standar ----------------------------------------------------

@cocotb.test(expect_fail=True)  # S7
async def test_decoder_standard_codes_native(dut):
    """Semua kode standar (RD- dan RD+) didekode benar, layout native."""
    await setup(dut)
    bad = {"RD-": 0, "RD+": 0}
    for rd, name in ((-1, "RD-"), (1, "RD+")):
        for b in range(256):
            c, _ = m.encode(b, rd)
            if await decode_native(dut, std_to_native(c)) != b:
                bad[name] += 1
    save("decoder_salah_dari_256", bad)
    assert bad == {"RD-": 0, "RD+": 0}, f"salah decode: {bad}"


@cocotb.test(expect_fail=True)  # S7
async def test_decoder_standard_wire_order(dut):
    """Aliran bit standar (a dulu) didekode benar."""
    await setup(dut)
    bad = 0
    for b in range(256):
        c, _ = m.encode(b, -1)
        bad += (await decode_bits(dut, bits_msb_first(c))) != b
    save("decoder_urutan_kabel_standar_salah_dari_256", bad)
    assert bad == 0, f"{bad}/256 salah"


async def _observe(dut, word):
    got = await decode_native(dut, word)
    # uio_out[0] tidak punya driver (z), jadi pin dibandingkan sebagai string.
    return (got, dut.uio_out.value.binstr, dut.uio_oe.value.binstr)


@cocotb.test(expect_fail=True)  # S8
async def test_decoder_flags_illegal_code(dut):
    """Kode ilegal menghasilkan keluaran yang berbeda dari kode legal mana pun."""
    await setup(dut)
    legal = {await _observe(dut, std_to_native(m.encode(b, rd)[0]))
             for b in range(256) for rd in (-1, 1)}
    legal |= {await _observe(dut, await encode(dut, b)) for b in range(256)}
    illegal = [0b0000000000, 0b1111111111, std_to_native(0b1111110000),
               await encode(dut, 0x00)]  # word DUT sendiri utk 0x00, disparity -4
    hits = [f"{w:010b}" for w in illegal if (await _observe(dut, w)) in legal]
    save("kode_ilegal_tak_terbedakan", hits)
    assert not hits, f"kode ilegal tak terbedakan dari legal: {hits}"


@cocotb.test(expect_fail=True)  # S9
async def test_decoder_flags_disparity_error(dut):
    """Kode yang melanggar running disparity menghasilkan indikasi galat."""
    await setup(dut)
    c, _ = m.encode(0x21, -1)        # D.1.1 RD-: 011101 1001, disparity +2
    first = await _observe(dut, std_to_native(c))
    second = await _observe(dut, std_to_native(c))  # harusnya bentuk RD+
    save("galat_disparity", {"pertama": first, "kedua_melanggar": second})
    assert first != second, f"keluaran identik {first}: galat disparity tidak terlihat"


# --- penyelarasan word -----------------------------------------------------

async def _stream_decode(dut, words, offset):
    """Kirim word native berurutan dengan `offset` bit sampah di depan.

    Framing ditentukan murni oleh jadwal par_en (11 siklus per word: 10 shift +
    1 siklus par_en yang tidak men-shift). Kembalikan byte yang terdekode.
    """
    stream = [1, 0, 1][:offset] + [bit for w in words for bit in bits_msb_first(w)]
    stream += [0] * (10 - len(stream) % 10)
    out = []
    for f in range(len(stream) // 10):
        frame = stream[10 * f:10 * f + 10]
        out.append(await decode_bits(dut, frame))
    return out


@cocotb.test()
async def test_framing_offset_zero(dut):
    """Tanpa geseran bit, framing eksternal dari par_en memberi hasil benar."""
    await setup(dut)
    data = [0x11, 0x22, 0x5A, 0xA5, 0xFF, 0x00]
    words = [await encode(dut, b) for b in data]
    got = await _stream_decode(dut, words, 0)
    assert got[:len(data)] == data, got


@cocotb.test(expect_fail=True)  # S10
async def test_word_alignment(dut):
    """Penerima menyelaraskan ulang setelah aliran tergeser 3 bit."""
    await setup(dut)
    rng = random.Random(3)
    data = [rng.randrange(256) for _ in range(40)]
    words = [await encode(dut, b) for b in data]
    got = await _stream_decode(dut, words, 3)
    # Toleransi: boleh salah sampai 5 word pertama selama penyelarasan.
    tail = data[5:]
    found = any(got[s:s + len(tail)] == tail for s in range(0, 10))
    save("penyelarasan_word_geser_3", {"terdekode_10_pertama": got[:10], "dikirim_10_pertama": data[:10]})
    assert found, "tidak pernah sinkron kembali"
