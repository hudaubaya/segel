"""Test loopback PHY (rtl/phy/): dua PHY saling terhubung (tb.v).

  test_loopback_shifts  geseran bit kanal 0..9 (semua posisi) + acak; framing
                        terkunci di 10 phase berbeda, semua frame kembali utuh
  test_clock_ratios     8 konfigurasi periode clock TX/RX/sistem acak yang tidak
                        sebanding (bilangan prima ps), skew dan tunda kanal acak
  test_rate_limits      TX lebih lambat dari laju simbol (IDLE di tengah frame);
                        RX sistem terlalu lambat sementara (overflow ditandai,
                        frame terkena tidak pernah OK, link pulih tanpa reset)
  test_bit_errors       injeksi galat satu bit di kanal: setiap galat harus
                        terdeteksi (kode ilegal, disparity, simbol K tak terduga,
                        CRC, atau framing), dan tidak ada frame rusak yang lolos
                        dengan status OK. Rincian deteksi -> phy_bit_errors.json

Payload setiap frame diawali nomor urut 16 bit, sehingga frame yang hilang atau
rusak bisa dicocokkan dengan yang dikirim.
"""

import json
import os
import random

import cocotb
from cocotb.triggers import RisingEdge, Timer

SEED = int(os.environ.get("PHY_SEED", "2026"))
ERR_COUNTERS = ("code", "disp", "ctrl", "crc", "frame")


def is_prime(n):
    return n > 1 and all(n % p for p in range(2, int(n ** 0.5) + 1))


def prime_near(x):
    x = int(x)
    while not is_prime(x):
        x += 1
    return x


class Side:
    """Sinyal satu PHY (akhiran _a / _b)."""

    def __init__(self, dut, s):
        self.dut, self.s = dut, s
        self.sys_clk = getattr(dut, f"sys_clk_{s}")
        self.tx_clk = getattr(dut, f"tx_clk_{s}")
        self.phy = getattr(dut, f"u_{s}")

    def sig(self, name):
        return getattr(self.dut, f"{name}_{self.s}")

    def counters(self):
        return {c: int(self.sig(f"cnt_{c}").value) for c in ERR_COUNTERS + ("ok", "lost")}


def make_frames(rng, n, maxlen=48, seq0=0):
    frames = []
    for i in range(n):
        ln = rng.randrange(1, maxlen + 1)
        seq = (seq0 + i) & 0xFFFF
        frames.append(bytes([seq >> 8, seq & 0xFF]) + rng.randbytes(ln))
    return frames


async def tx_driver(side, frames, rng, gap=0.2):
    """Kirim frame lewat tx_data/tx_valid/tx_last (nilai dibaca sebelum tepi = di-sample)."""
    data, valid, last, ready = (side.sig(n) for n in ("tx_data", "tx_valid", "tx_last", "tx_ready"))
    for f in frames:
        i = 0
        while i < len(f):
            if rng.random() < gap:
                valid.value = 0
                await RisingEdge(side.sys_clk)
                continue
            data.value = f[i]
            last.value = int(i == len(f) - 1)
            valid.value = 1
            await RisingEdge(side.sys_clk)
            if int(ready.value):
                i += 1
    valid.value = 0
    last.value = 0


async def rx_monitor(side, out):
    """Kumpulkan frame dari rx_*: out = [(payload, {status})]."""
    buf = bytearray()
    v, d, l = side.sig("rx_valid"), side.sig("rx_data"), side.sig("rx_last")
    errs = {e: side.sig(f"rx_err_{e}") for e in ("crc", "code", "disp", "ctrl", "frame")}
    while True:
        await RisingEdge(side.sys_clk)
        if int(v.value):
            buf.append(int(d.value))
            if int(l.value):
                out.append((bytes(buf), {e: int(s.value) for e, s in errs.items()}))
                buf = bytearray()


def config(dut, cfg):
    for k, v in cfg.items():
        getattr(dut, k).value = v


async def link_up(dut, rng, cfg, aligned_release=False, timeout_ns=200_000):
    """Reset kedua PHY dengan konfigurasi baru, tunggu kedua RX terkunci."""
    dut.rst_n_a.value = 0
    dut.rst_n_b.value = 0
    for s in "ab":
        getattr(dut, f"tx_valid_{s}").value = 0
    config(dut, cfg)
    dut.run.value = 1
    await Timer(200, "ns")
    if aligned_release:
        # Lepas reset di posisi tetap terhadap tx_clk_a, sehingga phase kunci B
        # hanya bergantung pada geseran kanal AB.
        await RisingEdge(dut.tx_clk_a)
        await Timer(cfg["p_tx_a"] // 4, "ps")
        dut.rst_n_a.value = 1
        dut.rst_n_b.value = 1
    else:
        for s in rng.sample("ab", 2):
            await Timer(rng.randrange(1, 20000), "ps")
            getattr(dut, f"rst_n_{s}").value = 1
    t = 0
    while not (int(dut.rx_locked_a.value) and int(dut.rx_locked_b.value)):
        await Timer(100, "ns")
        t += 100
        assert t < timeout_ns, "link tidak terkunci"


def random_cfg(rng, shift_ab=None, shift_ba=None):
    p_tx_a = prime_near(rng.uniform(4000, 12000))
    p_tx_b = prime_near(rng.uniform(4000, 12000))
    # sys_clk harus mengosongkan FIFO RX: periode < 10x periode rx_clk (= tx lawan)
    p_sys_a = prime_near(p_tx_b * rng.uniform(0.25, 3.5))
    p_sys_b = prime_near(p_tx_a * rng.uniform(0.25, 3.5))
    return dict(
        p_tx_a=p_tx_a, p_tx_b=p_tx_b, p_sys_a=p_sys_a, p_sys_b=p_sys_b,
        shift_ab=rng.randrange(32) if shift_ab is None else shift_ab,
        shift_ba=rng.randrange(32) if shift_ba is None else shift_ba,
        ddly_ab=int(p_tx_a * rng.uniform(0, 0.35)), skew_ab=int(p_tx_a * rng.uniform(0, 0.35)),
        ddly_ba=int(p_tx_b * rng.uniform(0, 0.35)), skew_ba=int(p_tx_b * rng.uniform(0, 0.35)))


async def exchange(dut, rng, n_frames, maxlen=48, timeout_ns=None):
    """Kirim n_frames ke dua arah sekaligus; kembalikan {sisi penerima: [(payload, status)]}."""
    A, B = Side(dut, "a"), Side(dut, "b")
    sent = {"b": make_frames(rng, n_frames, maxlen), "a": make_frames(rng, n_frames, maxlen)}
    got = {"a": [], "b": []}
    mons = [cocotb.start_soon(rx_monitor(B, got["b"])), cocotb.start_soon(rx_monitor(A, got["a"]))]
    txs = [cocotb.start_soon(tx_driver(A, sent["b"], rng)),
           cocotb.start_soon(tx_driver(B, sent["a"], rng))]
    if timeout_ns is None:
        p = max(int(dut.p_tx_a.value), int(dut.p_tx_b.value), int(dut.p_sys_a.value),
                int(dut.p_sys_b.value))
        timeout_ns = n_frames * (maxlen + 8) * 12 * p // 1000 + 50_000
    t = 0
    while len(got["a"]) < n_frames or len(got["b"]) < n_frames:
        await Timer(1000, "ns")
        t += 1000
        if t > timeout_ns:
            break
    await Timer(2000, "ns")
    for c in mons + txs:
        c.kill()
    return sent, got


def check_clean(dut, sent, got, label):
    for s in "ab":
        side = Side(dut, s)
        assert len(got[s]) == len(sent[s]), \
            f"{label}: {s} menerima {len(got[s])}/{len(sent[s])} frame"
        for i, ((payload, st), ref) in enumerate(zip(got[s], sent[s])):
            assert not any(st.values()), f"{label}: frame {i} di {s} berstatus {st}"
            assert payload == ref, f"{label}: frame {i} di {s} berbeda"
        c = side.counters()
        assert c["ok"] == len(sent[s]) and all(c[e] == 0 for e in ERR_COUNTERS + ("lost",)), \
            f"{label}: counter {s} = {c}"
        assert not int(side.sig("rx_overflow").value), f"{label}: overflow di {s}"


def phases(dut):
    return int(dut.u_a.u_align.phase.value), int(dut.u_b.u_align.phase.value)


@cocotb.test()
async def test_loopback_shifts(dut):
    """Geseran bit kanal 0..9 dan acak: semua frame utuh, phase kunci mencakup 10 posisi."""
    rng = random.Random(SEED)
    base = random_cfg(rng)
    seen_b = {}
    shifts = list(range(10)) + [rng.randrange(10, 32) for _ in range(4)]
    for sh in shifts:
        cfg = dict(base, shift_ab=sh, shift_ba=rng.randrange(32))
        await link_up(dut, rng, cfg, aligned_release=True)
        sent, got = await exchange(dut, rng, 12)
        check_clean(dut, sent, got, f"geseran AB {sh}")
        pa, pb = phases(dut)
        seen_b.setdefault(pb, []).append(sh)
        dut._log.info("geseran AB %2d, BA %2d: phase A %d, B %d, 2x12 frame OK",
                      sh, cfg["shift_ba"], pa, pb)
    assert len(seen_b) == 10, f"phase kunci B tidak mencakup 10 posisi: {seen_b}"
    dut._log.info("phase kunci B -> geseran: %s", dict(sorted(seen_b.items())))


@cocotb.test()
async def test_clock_ratios(dut):
    """Periode TX/RX/sistem acak (prima, ps) per konfigurasi; semua frame utuh."""
    rng = random.Random(SEED + 1)
    for n in range(8):
        cfg = random_cfg(rng)
        await link_up(dut, rng, cfg)
        sent, got = await exchange(dut, rng, 20)
        r = lambda a, b: cfg[a] / cfg[b]  # noqa: E731
        label = (f"cfg {n}: tx_a {cfg['p_tx_a']} tx_b {cfg['p_tx_b']} sys_a {cfg['p_sys_a']} "
                 f"sys_b {cfg['p_sys_b']} ps")
        check_clean(dut, sent, got, label)
        dut._log.info("%s | sys_b/rx_b %.3f sys_b/tx_b %.3f sys_a/rx_a %.3f: 2x20 frame OK",
                      label, r("p_sys_b", "p_tx_a"), r("p_sys_b", "p_tx_b"),
                      r("p_sys_a", "p_tx_b"))


@cocotb.test()
async def test_bit_errors(dut):
    """Galat satu bit di kanal A->B: selalu terdeteksi, tidak ada frame rusak lolos."""
    rng = random.Random(SEED + 2)
    n_inj = int(os.environ.get("PHY_INJECT_N", "300"))
    cfg = random_cfg(rng)
    await link_up(dut, rng, cfg)
    A, B = Side(dut, "a"), Side(dut, "b")
    frames = make_frames(rng, 100000, maxlen=40)
    got = []
    mon = cocotb.start_soon(rx_monitor(B, got))
    tx = cocotb.start_soon(tx_driver(A, frames, rng, gap=0.3))
    await Timer(20, "us")
    records = []
    for i in range(n_inj):
        before = B.counters()
        # satu bit dibalik: inj_ab = 1 tepat selama satu tepi naik tx_clk_a
        await RisingEdge(dut.tx_clk_a)
        dut.inj_ab.value = 1
        await RisingEdge(dut.tx_clk_a)
        dut.inj_ab.value = 0
        for _ in range(rng.randrange(300, 900)):     # jeda = jendela pengamatan galat ini
            await RisingEdge(dut.tx_clk_a)
        after = B.counters()
        delta = {c: after[c] - before[c] for c in ERR_COUNTERS}
        records.append(delta)
        assert any(delta.values()), f"injeksi {i}: galat tidak terdeteksi ({delta})"
    # Link harus tetap hidup: tidak pernah realign (galat satu bit tidak boleh
    # menggeser framing) dan periode tanpa galat sesudahnya mengirim frame utuh.
    assert int(dut.u_b.u_align.realign_cnt.value) == 0, "galat satu bit memicu realign"
    before = B.counters()
    await Timer(60, "us")
    after = B.counters()
    assert all(after[c] == before[c] for c in ERR_COUNTERS), f"galat tanpa injeksi: {after}"
    assert after["ok"] - before["ok"] >= 10, f"link tidak pulih: {before} -> {after}"
    tx.kill()
    await Timer(20, "us")
    mon.kill()

    # Frame berstatus OK harus identik dengan yang dikirim (dicocokkan lewat nomor urut).
    n_ok = n_bad = 0
    for payload, st in got:
        if any(st.values()):
            n_bad += 1
            continue
        seq = (payload[0] << 8) | payload[1]
        assert payload == frames[seq], f"frame #{seq} rusak tetapi berstatus OK"
        n_ok += 1
    assert not int(B.sig("rx_overflow").value)

    any_count = {c: sum(1 for d in records if d[c]) for c in ERR_COUNTERS}
    illegal_or_crc = sum(1 for d in records if d["code"] or d["crc"])
    summary = dict(seed=SEED, injections=n_inj, detected=sum(1 for d in records if any(d.values())),
                   detected_by_category_any=any_count, illegal_or_crc=illegal_or_crc,
                   frames_ok=n_ok, frames_flagged=n_bad, cfg=cfg, final_counters=B.counters())
    with open("phy_bit_errors.json", "w") as f:
        json.dump(summary, f, indent=1)
    dut._log.info("%d/%d galat terdeteksi; per penanda (boleh >1 per galat): %s",
                  summary["detected"], n_inj, any_count)
    dut._log.info("terdeteksi sebagai kode ilegal atau CRC: %d/%d; frame OK %d (semua utuh), "
                  "frame ditandai %d", illegal_or_crc, n_inj, n_ok, n_bad)


@cocotb.test()
async def test_rate_limits(dut):
    """TX lebih lambat dari laju simbol: IDLE di tengah frame transparan.
    sys_clk RX terlalu lambat: overflow ditandai, frame terkena tidak pernah berstatus OK."""
    rng = random.Random(SEED + 3)
    # 1) sys_a 15x tx_a: penulis FIFO TX A (1 simbol/siklus sys) lebih lambat dari
    #    serializer (1 simbol/10 tx_clk), jadi FIFO TX pasti kosong di tengah frame.
    cfg = dict(p_tx_a=5003, p_tx_b=10007, p_sys_a=75011, p_sys_b=3001, shift_ab=7, shift_ba=3,
               ddly_ab=0, skew_ab=1000, ddly_ba=500, skew_ba=0)
    await link_up(dut, rng, cfg)
    sent, got = await exchange(dut, rng, 10, maxlen=24)
    check_clean(dut, sent, got, "TX underflow")
    dut._log.info("TX underflow (sys_a = 15 x tx_a): 2x10 frame OK")

    # 2) sys_b 25x tx_a selama 40 us: deframer B (1 simbol/siklus) lebih lambat dari
    #    laju simbol rx_b (1 simbol/10 rx_clk) -> FIFO RX B pasti meluap. Lalu sys_b
    #    dipercepat lagi: link harus pulih tanpa reset.
    cfg = dict(cfg, p_sys_a=3001, p_sys_b=3001)
    await link_up(dut, rng, cfg)
    A, B = Side(dut, "a"), Side(dut, "b")
    frames = make_frames(rng, 60, maxlen=24)
    got = []
    mon = cocotb.start_soon(rx_monitor(B, got))
    tx = cocotb.start_soon(tx_driver(A, frames, rng, gap=0.0))
    dut.p_sys_b.value = 125003
    await Timer(40, "us")
    dut.p_sys_b.value = 3001
    await Timer(150, "us")
    tx.kill()
    mon.kill()
    c = B.counters()
    ok_seqs = []
    flagged = []
    for payload, st in got:
        if any(st.values()):
            flagged.append(st)
            continue
        seq = (payload[0] << 8) | payload[1]
        assert payload == frames[seq], f"frame #{seq} rusak tetapi berstatus OK"
        ok_seqs.append(seq)
    assert int(B.sig("rx_overflow").value) == 1, "overflow tidak ditandai"
    assert c["lost"] > 0, "penanda simbol hilang tidak sampai"
    assert any(st["frame"] for st in flagged), "tidak ada frame yang ditandai rx_err_frame"
    assert set(range(50, 60)) <= set(ok_seqs), "link tidak pulih setelah overload"
    dut._log.info("RX overflow sementara (sys_b = 25 x rx_b selama 40 us): overflow=1, "
                  "frame OK %d (semua utuh, termasuk 10 terakhir), ditandai %d, hilang %d, "
                  "counter %s", len(ok_seqs), len(flagged), 60 - len(got), c)
