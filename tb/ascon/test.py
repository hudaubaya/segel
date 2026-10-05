"""Test cocotb rtl/ascon_core.v (Ascon-AEAD128 / Ascon-XOF128, SP 800-232).

Test:
  test_kat_aead     KAT ascon-c LWC_AEAD_KAT_128_128 (1089): enkripsi + dekripsi
  test_kat_xof      KAT ascon-c LWC_XOF_KAT_128_512 (1025)
  test_acvp_aead    NIST ACVP Ascon-AEAD128-SP800-232 (240): panjang bit, tag terpotong,
                    nonce masking, 60 vektor "modified tag" harus ditolak
  test_acvp_xof     NIST ACVP Ascon-XOF128-SP800-232 (60): panjang bit masukan/keluaran
  test_random       ASCON_RANDOM_N (default 10000) vektor acak vs model/ascon.py,
                    termasuk backpressure keluaran dan jeda masukan
  test_wrong_tag    dekripsi dengan tag/ciphertext/AD/nonce salah: setiap bit tag dibalik
                    satu per satu; plaintext tidak pernah keluar, dout tetap 0, buffer
                    dinolkan, jumlah siklus sama dengan tag benar
  test_overflow     dekripsi melebihi buffer ditolak walaupun tag benar
  test_errors       tag_bits di luar 32..128, mode 3, blok last terlalu panjang
  test_cycles       jumlah siklus untuk payload 0/16/32 byte (ditulis ke ascon_cycles.json)

Di SETIAP operasi pemeriksa di tb.v mengecek tiap siklus: dout == 0 saat dout_valid == 0;
pada dekripsi dout_valid tidak pernah naik sebelum auth_ok dan tag_out tetap 0.
"""

import json
import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

import ascon as A
import vectors as V

ENC, DEC, XOF = 0, 1, 2
CLK_NS = 10   # periode clock tb.v
AEAD_RATE, XOF_RATE = 128, 64


# ---------------------------------------------------------------- konversi bit

def to_int(data: bytes, bits: int) -> int:
    return int.from_bytes(data, "little") & ((1 << bits) - 1)


def to_bytes(v: int, bits: int) -> bytes:
    return v.to_bytes(A.nbytes(bits), "little")


def split(data: bytes, bits: int, rate: int):
    """Blok (nilai, din_bits, din_last): blok penuh lalu tepat satu blok last < rate bit."""
    v = to_int(data, bits)
    full, lb = divmod(bits, rate)
    out = [((v >> (rate * i)) & ((1 << rate) - 1), rate, 0) for i in range(full)]
    out.append(((v >> (rate * full)) & ((1 << lb) - 1), lb, 1))
    return out


def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


# ---------------------------------------------------------------- driver

class Core:
    def __init__(self, dut):
        self.dut = dut
        self._cache = {}

    def set(self, name, v):
        if self._cache.get(name) != v:
            getattr(self.dut, name).value = v
            self._cache[name] = v

    def buf_entries(self, n):
        """n entri pertama buffer plaintext (None kalau ada bit X/Z)."""
        out = []
        for i in range(n):
            v = self.dut.u_core.pbuf[i].value
            out.append(int(v) if v.is_resolvable else None)
        return out


async def setup(dut):
    core = Core(dut)
    for name in ("start", "mode", "key", "key2", "nonce", "tag_in", "tag_bits", "xof_bits",
                 "din_valid", "din", "din_bits", "din_last"):
        core.set(name, 0)
    core.set("dout_ready", 1)
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    return core


async def run_op(core, mode, stream, *, key=0, key2=0, nonce=0, tag_in=0, tag_bits=128,
                 xof_bits=0, ready=None, gap=None):
    """Jalankan satu operasi.

    Input ditulis tepat setelah tepi naik dan dibaca di tepi naik berikutnya; nilai yang
    dibaca di callback RisingEdge adalah nilai SEBELUM tepi itu, yaitu nilai yang
    di-sample DUT. Tanpa ready/gap acak, siklus tanpa transfer dilompati: kalau evt (tb.v)
    = 0 setelah input stabil, tunggu evt naik dulu. Pemeriksa bocoran di tb.v tetap
    berjalan setiap siklus. Kembalikan dict: out (int), out_bits, tag_out, auth_ok, err, cycles
    (tepi naik dari start diterima sampai done terdaftar), leaks (selisih leak_cnt pemeriksa
    di tb.v), consumed/n_in (blok masuk yang diterima / disediakan).
    """
    dut = core.dut
    leak0 = int(dut.leak_cnt.value)
    core.set("start", 1)
    core.set("mode", mode)
    core.set("key", key)
    core.set("key2", key2)
    core.set("nonce", nonce)
    core.set("tag_in", tag_in)
    core.set("tag_bits", tag_bits)
    core.set("xof_bits", xof_bits)
    core.set("din_valid", 0)
    core.set("dout_ready", 1)
    await RisingEdge(dut.clk)            # tepi 0: start di-sample
    t0 = get_sim_time("ns")
    assert int(dut.busy.value) == 0, "core masih busy saat start"
    core.set("start", 0)

    i, out, out_bits, cyc = 0, 0, 0, 0
    din_valid, dout_ready = 0, 1
    while True:
        if i < len(stream) and not (gap and gap()):
            v, b, last = stream[i]
            din_valid = 1
            core.set("din", v)
            core.set("din_bits", b)
            core.set("din_last", last)
        else:
            din_valid = 0
        core.set("din_valid", din_valid)
        dout_ready = ready() if ready else 1
        core.set("dout_ready", dout_ready)
        if ready is None and gap is None:
            await ReadOnly()
            if not int(dut.evt.value):
                await RisingEdge(dut.evt)
        await RisingEdge(dut.clk)
        cyc = round((get_sim_time("ns") - t0) / CLK_NS)
        if int(dut.done.value):          # done terdaftar di tepi sebelumnya
            break
        if din_valid and int(dut.din_ready.value):
            i += 1
        if dout_ready and int(dut.dout_valid.value):
            b = int(dut.dout_bits.value)
            out |= (int(dut.dout.value) & ((1 << b) - 1)) << out_bits
            out_bits += b
        assert cyc < 5_000_000, "timeout"
    core.set("din_valid", 0)
    return dict(out=out, out_bits=out_bits, tag_out=int(dut.tag_out.value),
                auth_ok=int(dut.auth_ok.value), err=int(dut.err.value), cycles=cyc - 1,
                leaks=int(dut.leak_cnt.value) - leak0, consumed=i, n_in=len(stream))


def _i(b):
    return int.from_bytes(b, "little")


async def hw_encrypt(core, key, nonce, ad, ad_bits, pt, pt_bits, tag_bits=128,
                     second_key=None, **kw):
    stream = split(ad, ad_bits, AEAD_RATE) + split(pt, pt_bits, AEAD_RATE)
    r = await run_op(core, ENC, stream, key=_i(key), key2=_i(second_key or bytes(16)),
                     nonce=_i(nonce), tag_bits=tag_bits, **kw)
    assert r["consumed"] == r["n_in"], "tidak semua blok masuk diterima"
    assert r["leaks"] == 0, f"{r['leaks']} siklus bocor"
    assert r["out_bits"] == pt_bits, (r["out_bits"], pt_bits)
    assert not r["err"]
    return to_bytes(r["out"], pt_bits), to_bytes(r["tag_out"], tag_bits), r


async def hw_decrypt(core, key, nonce, ad, ad_bits, ct, ct_bits, tag, tag_bits=128,
                     second_key=None, **kw):
    """Kembalikan (plaintext | None, hasil). None = ditolak; dicek tidak ada bocoran."""
    stream = split(ad, ad_bits, AEAD_RATE) + split(ct, ct_bits, AEAD_RATE)
    r = await run_op(core, DEC, stream, key=_i(key), key2=_i(second_key or bytes(16)),
                     nonce=_i(nonce), tag_in=to_int(tag, tag_bits), tag_bits=tag_bits, **kw)
    assert r["consumed"] == r["n_in"], "tidak semua blok masuk diterima"
    assert r["leaks"] == 0, f"{r['leaks']} siklus bocor"
    if not r["auth_ok"]:
        assert r["out_bits"] == 0 and r["out"] == 0, "plaintext keluar walau tag salah"
        n = (ct_bits + 127) // 128
        assert all(e == 0 for e in core.buf_entries(min(n, 512))), "buffer tidak dinolkan"
        return None, r
    assert r["out_bits"] == ct_bits, (r["out_bits"], ct_bits)
    return to_bytes(r["out"], ct_bits), r


async def hw_xof(core, msg, msg_bits, out_bits, **kw):
    r = await run_op(core, XOF, split(msg, msg_bits, XOF_RATE), xof_bits=out_bits, **kw)
    assert r["consumed"] == r["n_in"]
    assert r["leaks"] == 0, f"{r['leaks']} siklus bocor"
    assert r["out_bits"] == out_bits, (r["out_bits"], out_bits)
    assert not r["err"]
    return to_bytes(r["out"], out_bits), r


# ---------------------------------------------------------------- vektor resmi

@cocotb.test()
async def test_kat_aead(dut):
    """KAT ascon-c LWC_AEAD_KAT_128_128.txt: semua vektor, enkripsi dan dekripsi."""
    core = await setup(dut)
    kats = V.kat_aead()
    for t in kats:
        ad_bits, pt_bits = 8 * len(t["ad"]), 8 * len(t["pt"])
        ct, tag, _ = await hw_encrypt(core, t["key"], t["nonce"], t["ad"], ad_bits,
                                      t["pt"], pt_bits)
        assert ct == t["ct"] and tag == t["tag"], f"Count {t['count']}: enkripsi salah"
        pt, _ = await hw_decrypt(core, t["key"], t["nonce"], t["ad"], ad_bits, t["ct"],
                                 pt_bits, t["tag"])
        assert pt == t["pt"], f"Count {t['count']}: dekripsi salah"
    dut._log.info("KAT AEAD: %d vektor OK (enkripsi + dekripsi)", len(kats))


@cocotb.test()
async def test_kat_xof(dut):
    """KAT ascon-c LWC_XOF_KAT_128_512.txt: semua vektor."""
    core = await setup(dut)
    kats = V.kat_xof()
    for t in kats:
        md, _ = await hw_xof(core, t["msg"], 8 * len(t["msg"]), 512)
        assert md == t["md"], f"Count {t['count']}: XOF salah"
    dut._log.info("KAT XOF: %d vektor OK", len(kats))


@cocotb.test()
async def test_acvp_aead(dut):
    """NIST ACVP Ascon-AEAD128-SP800-232: semua 240 vektor."""
    core = await setup(dut)
    vecs = V.acvp_aead()
    n_rej = 0
    for t in vecs:
        name = f"tg{t['tg']} tc{t['tc']}"
        if t["direction"] == "encrypt":
            ct, tag, _ = await hw_encrypt(core, t["key"], t["nonce"], t["ad"], t["ad_bits"],
                                          t["pt"], t["pt_bits"], t["tag_bits"], t["second_key"])
            assert ct == t["ct"], f"{name}: ciphertext salah"
            assert tag == t["tag"], f"{name}: tag salah"
        else:
            pt, _ = await hw_decrypt(core, t["key"], t["nonce"], t["ad"], t["ad_bits"], t["ct"],
                                     t["pt_bits"], t["tag"], t["tag_bits"], t["second_key"])
            if t["passed"]:
                assert pt == t["pt"], f"{name}: plaintext salah / ditolak"
            else:
                assert pt is None, f"{name}: tag salah diterima ({t['reason']})"
                n_rej += 1
    dut._log.info("ACVP AEAD: %d vektor OK (%d tag salah ditolak)", len(vecs), n_rej)


@cocotb.test()
async def test_acvp_xof(dut):
    """NIST ACVP Ascon-XOF128-SP800-232: semua 60 vektor."""
    core = await setup(dut)
    vecs = V.acvp_xof()
    for t in vecs:
        md, _ = await hw_xof(core, t["msg"], t["msg_bits"], t["out_bits"])
        assert md == t["md"], f"tc{t['tc']}: XOF salah"
    dut._log.info("ACVP XOF: %d vektor OK", len(vecs))


# ---------------------------------------------------------------- acak

EDGE_BITS = [0, 1, 7, 8, 9, 63, 64, 65, 120, 127, 128, 129, 191, 192, 255, 256, 257, 384]


def rand_bits(rng, hi=520):
    return rng.choice(EDGE_BITS) if rng.random() < 0.4 else rng.randrange(hi)


@cocotb.test()
async def test_random(dut):
    """Vektor acak (default 10000) dibandingkan dengan golden model."""
    core = await setup(dut)
    n = int(os.environ.get("ASCON_RANDOM_N", "10000"))
    seed = int(os.environ.get("ASCON_SEED", "232"))
    rng = random.Random(seed)
    dut._log.info("seed %d, %d vektor", seed, n)
    stats = dict(enc=0, dec_ok=0, dec_rej=0, xof=0)
    for k in range(n):
        kw = {}
        if rng.random() < 0.2:
            p = rng.random()
            kw["ready"] = lambda p=p: int(rng.random() < p + 0.1)
        if rng.random() < 0.2:
            q = rng.random() * 0.5
            kw["gap"] = lambda q=q: rng.random() < q
        r = rng.random()
        if r < 0.25:
            msg_bits, out_bits = rand_bits(rng), rng.randrange(1, 600)
            msg = rng.randbytes(A.nbytes(msg_bits))
            md, _ = await hw_xof(core, msg, msg_bits, out_bits, **kw)
            assert md == A.xof(msg, out_bits, msg_bits), f"#{k} XOF"
            stats["xof"] += 1
            continue
        key, nonce = rng.randbytes(16), rng.randbytes(16)
        sk = rng.randbytes(16) if rng.random() < 0.5 else None
        ad_bits, pt_bits = rand_bits(rng), rand_bits(rng)
        tag_bits = 128 if rng.random() < 0.5 else rng.randrange(32, 129)
        ad, pt = rng.randbytes(A.nbytes(ad_bits)), rng.randbytes(A.nbytes(pt_bits))
        ect, etag = A.aead_encrypt(key, nonce, ad, pt, ad_bits, pt_bits, tag_bits, sk)
        if r < 0.6:
            ct, tag, _ = await hw_encrypt(core, key, nonce, ad, ad_bits, pt, pt_bits,
                                          tag_bits, sk, **kw)
            assert (ct, tag) == (ect, etag), f"#{k} enkripsi"
            stats["enc"] += 1
            continue
        # dekripsi: 30% dirusak (tag, ciphertext, AD, nonce, atau kunci kedua)
        ct, tag, ad_d, nonce_d, sk_d = ect, etag, ad, nonce, sk
        if rng.random() < 0.3:
            what = rng.choice(["tag", "ct", "ad", "nonce", "sk"])
            if what == "ct" and pt_bits:
                b = rng.randrange(pt_bits)
                ct = bytearray(ct); ct[b // 8] ^= 1 << (b % 8); ct = bytes(ct)
            elif what == "ad" and ad_bits:
                b = rng.randrange(ad_bits)
                ad_d = bytearray(ad); ad_d[b // 8] ^= 1 << (b % 8); ad_d = bytes(ad_d)
            elif what == "nonce":
                nonce_d = xor_bytes(nonce, (1 << rng.randrange(128)).to_bytes(16, "little"))
            elif what == "sk":
                sk_d = rng.randbytes(16) if sk is None else None
            else:
                b = rng.randrange(tag_bits)
                tag = bytearray(tag); tag[b // 8] ^= 1 << (b % 8); tag = bytes(tag)
        exp = A.aead_decrypt(key, nonce_d, ad_d, ct, tag, ad_bits, pt_bits, tag_bits, sk_d)
        got, _ = await hw_decrypt(core, key, nonce_d, ad_d, ad_bits, ct, pt_bits, tag,
                                  tag_bits, sk_d, **kw)
        assert got == exp, f"#{k} dekripsi: model {exp!r}, RTL {got!r}"
        stats["dec_ok" if exp is not None else "dec_rej"] += 1
    dut._log.info("acak OK: %s", stats)


# ---------------------------------------------------------------- tag salah

@cocotb.test()
async def test_wrong_tag(dut):
    """Tag/data salah tidak pernah mengeluarkan plaintext (dout ditahan 0, buffer dinol)."""
    core = await setup(dut)
    rng = random.Random(800232)
    n_rej = 0
    for ad_bits, pt_bits in [(0, 0), (0, 128), (0, 256), (64, 37), (200, 300)]:
        key, nonce = rng.randbytes(16), rng.randbytes(16)
        ad, pt = rng.randbytes(A.nbytes(ad_bits)), rng.randbytes(A.nbytes(pt_bits))
        ct, tag = A.aead_encrypt(key, nonce, ad, pt, ad_bits, pt_bits)
        # kontrol positif: tag benar diterima
        got, r_ok = await hw_decrypt(core, key, nonce, ad, ad_bits, ct, pt_bits, tag)
        assert got == A.truncate_bits(pt, pt_bits), "tag benar ditolak"
        # setiap bit tag (128) dibalik satu per satu; jumlah siklus harus sama dengan
        # tag benar (rilis dan wipe sama panjang, waktu tidak membocorkan hasil verifikasi)
        for b in range(128):
            bad = bytearray(tag); bad[b // 8] ^= 1 << (b % 8)
            got, r = await hw_decrypt(core, key, nonce, ad, ad_bits, ct, pt_bits, bytes(bad))
            assert got is None, f"AD {ad_bits} b, PT {pt_bits} b: bit tag {b} dibalik diterima"
            assert r["cycles"] == r_ok["cycles"], f"siklus {r['cycles']} != {r_ok['cycles']}"
            n_rej += 1
        # ciphertext / AD / nonce / kunci kedua salah
        cases = [("nonce", dict(nonce=xor_bytes(nonce, b"\x80" + bytes(15)))),
                 ("key2", dict(second_key=b"\x01" + bytes(15)))]
        if pt_bits:
            c2 = bytearray(ct); c2[-1] ^= 1 << ((pt_bits - 1) % 8)
            cases.append(("ct", dict(ct=bytes(c2))))
        if ad_bits:
            a2 = bytearray(ad); a2[0] ^= 1
            cases.append(("ad", dict(ad=bytes(a2))))
        for name, ch in cases:
            args = dict(key=key, nonce=nonce, ad=ad, ct=ct, second_key=None) | ch
            got, _ = await hw_decrypt(core, args["key"], args["nonce"], args["ad"], ad_bits,
                                      args["ct"], pt_bits, tag, 128, args["second_key"])
            assert got is None, f"{name} salah diterima"
            n_rej += 1
    # tag terpotong 64 bit: bit 0..63 diverifikasi, bit 64..127 tag_in diabaikan
    key, nonce = rng.randbytes(16), rng.randbytes(16)
    ct, tag = A.aead_encrypt(key, nonce, b"", b"\x55" * 16, tag_bits=64)
    full = tag + rng.randbytes(8)
    for b in range(128):
        bad = bytearray(full); bad[b // 8] ^= 1 << (b % 8)
        stream = split(b"", 0, AEAD_RATE) + split(ct, 128, AEAD_RATE)
        r = await run_op(core, DEC, stream, key=_i(key), nonce=_i(nonce),
                         tag_in=_i(bytes(bad)), tag_bits=64)
        assert r["leaks"] == 0, f"{r['leaks']} siklus bocor"
        assert r["auth_ok"] == (b >= 64), f"tag 64 bit, bit {b}"
        if b < 64:
            assert r["out_bits"] == 0
            n_rej += 1
    dut._log.info("tag/data salah: %d dekripsi ditolak, tidak ada plaintext keluar", n_rej)


@cocotb.test()
async def test_overflow(dut):
    """Pesan dekripsi > PT_BUF_BLOCKS blok ditolak walaupun tag benar."""
    core = await setup(dut)
    nbuf = int(dut.PT_BUF_BLOCKS.value)
    rng = random.Random(5)
    key, nonce = rng.randbytes(16), rng.randbytes(16)
    for nblk in (nbuf, nbuf + 1):
        pt_bits = 128 * nblk - (0 if nblk == nbuf else 64)
        pt = rng.randbytes(A.nbytes(pt_bits))
        ct, tag = A.aead_encrypt(key, nonce, b"", pt, 0, pt_bits)
        got, r = await hw_decrypt(core, key, nonce, b"", 0, ct, pt_bits, tag)
        if nblk == nbuf:
            assert got == pt and not r["err"], "pesan tepat sebesar buffer ditolak"
        else:
            assert got is None and r["err"], "pesan melebihi buffer tidak ditolak"
    dut._log.info("buffer %d blok: %d blok diterima, %d blok ditolak", nbuf, nbuf, nbuf + 1)


@cocotb.test()
async def test_errors(dut):
    """Parameter ilegal -> err, tanpa keluaran."""
    core = await setup(dut)
    for tb_ in (0, 31, 129, 255):
        r = await run_op(core, ENC, [], tag_bits=tb_)
        assert r["err"] and r["out_bits"] == 0 and r["tag_out"] == 0, f"tag_bits {tb_}"
        assert r["cycles"] == 1
    r = await run_op(core, 3, [])
    assert r["err"], "mode 3"
    # blok last dengan din_bits >= rate
    r = await run_op(core, DEC, [(0, 128, 1), (0, 0, 1)], tag_bits=128)
    assert r["err"] and not r["auth_ok"] and r["out_bits"] == 0, "AD last 128 bit"
    r = await run_op(core, XOF, [(0, 64, 1)], xof_bits=64)
    assert r["err"], "XOF last 64 bit"
    # operasi normal sesudahnya tidak terpengaruh
    ct, tag, r = await hw_encrypt(core, bytes(16), bytes(16), b"", 0, b"", 0)
    assert (ct, tag) == A.aead_encrypt(bytes(16), bytes(16), b"", b"") and not r["err"]


# ---------------------------------------------------------------- siklus

def expected_cycles(mode, ad_bytes, msg_bytes, out_bits=256):
    """Rumus siklus (docs/ascon.md), dengan masukan selalu siap dan dout_ready = 1."""
    if mode == XOF:
        b_in = msg_bytes * 8 // 64 + 1
        b_out = (out_bits + 63) // 64
        return 12 + 13 * b_in + b_out + 12 * (b_out - 1) + 1
    ad = 1 if ad_bytes == 0 else 9 * (ad_bytes * 8 // 128 + 1)
    full, lb = divmod(msg_bytes * 8, 128)
    n = 12 + ad + 9 * full + 1 + 12 + 1
    if mode == DEC:
        n += full + (lb > 0) + 1
    return n


@cocotb.test()
async def test_cycles(dut):
    """Jumlah siklus per operasi untuk payload 0, 16, 32 byte."""
    core = await setup(dut)
    key, nonce = bytes(range(16)), bytes(range(16, 32))
    rows = []
    for ad_len in (0, 16):
        for n in (0, 16, 32):
            pt = bytes(range(n))
            ad = bytes(range(ad_len))
            ct, tag, re = await hw_encrypt(core, key, nonce, ad, 8 * ad_len, pt, 8 * n)
            got, rd = await hw_decrypt(core, key, nonce, ad, 8 * ad_len, ct, 8 * n, tag)
            assert got == pt
            rows.append(dict(op="AEAD128-enc", ad=ad_len, payload=n, cycles=re["cycles"]))
            rows.append(dict(op="AEAD128-dec", ad=ad_len, payload=n, cycles=rd["cycles"]))
    for n in (0, 16, 32):
        _, rx = await hw_xof(core, bytes(range(n)), 8 * n, 256)
        rows.append(dict(op="XOF128 (256 bit keluar)", ad=0, payload=n, cycles=rx["cycles"]))
    for row in rows:
        dut._log.info("%-24s AD %2d B  payload %2d B : %3d siklus", row["op"], row["ad"],
                      row["payload"], row["cycles"])
        mode = XOF if row["op"].startswith("XOF") else (DEC if "dec" in row["op"] else ENC)
        exp = expected_cycles(mode, row["ad"], row["payload"])
        assert row["cycles"] == exp, f"{row}: rumus {exp}"
    with open("ascon_cycles.json", "w") as f:
        json.dump(rows, f, indent=1)
