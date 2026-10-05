"""Bench cocotb bersama untuk CDC FIFO (inti `cdc_fifo` dan wrapper TT).

Dipakai oleh tb/audit/cdc_fifo (baseline #0036 apa adanya) dan tb/cdc_fifo
(salinan SEGEL dengan perbaikan F1/F3), sehingga keduanya menjalankan
pemeriksaan yang identik. Toplevel harus menyediakan sinyal t_*/c_*, instance
`top` (wrapper TT, dengan sub-instance `fifo`) dan `core` (cdc_fifo), seperti
tb.v di kedua direktori itu.

Pemeriksaan:
  - urutan data: tidak ada yang hilang, ganda, atau tertukar;
  - flag: full=1 setiap kali isi sebenarnya = kapasitas, empty=1 setiap kali
    isi sebenarnya = 0, dan read_data == kepala antrean selama empty=0;
  - pointer Gray (pra-sinkronisasi) berubah tepat satu bit per perubahan, dan
    setiap nilai pasca-sinkronisasi adalah nilai Gray yang pernah ada.
"""

import random
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Edge, FallingEdge, RisingEdge, Timer

ADDR_W = 5
CAPACITY = (1 << ADDR_W) - 1  # pointer tanpa bit wrap: satu slot tak terpakai
def gray(n):
    return n ^ (n >> 1)


class Port:
    """Pemetaan sinyal untuk instance `core` atau `top`."""

    def __init__(self, dut, which):
        self.dut = dut
        self.which = which
        p = "c_" if which == "core" else "t_"
        g = lambda n: getattr(dut, p + n)
        self.wclk, self.winc, self.wdata = g("wclk"), g("winc"), g("wdata")
        self.rclk, self.rinc = g("rclk"), g("rinc")
        self.rdata, self.full, self.empty = g("rdata"), g("full"), g("empty")
        self.fifo = dut.core if which == "core" else dut.top.fifo

    def set_reset(self, active):
        if self.which == "core":
            self.dut.c_wrst.value = int(active)
            self.dut.c_rrst.value = int(active)
        else:
            self.dut.t_wrst_n.value = int(not active)
            self.dut.t_rrst_n.value = int(not active)


class Bench:
    def __init__(self, port, seed, data_mask=0xF, max_fill=None):
        self.p = port
        self.rng = random.Random(seed)
        self.mask = data_mask
        self.q = deque()
        self.errors = []
        self.writes = self.reads = 0
        self.full_seen = self.empty_seen = 0
        self.pw = self.pr = 0.5
        self.running = True
        self.max_occ = 0
        # Batas isi dari sisi test (None = tanpa batas). Dipakai untuk menguji
        # FIFO di luar kondisi batas F3.
        self.max_fill = max_fill

    def err(self, msg):
        if len(self.errors) < 20:
            self.errors.append(msg)

    # --- driver + monitor domain write ---
    async def writer(self):
        p = self.p
        while self.running:
            await FallingEdge(p.wclk)
            want = self.rng.random() < self.pw
            if self.max_fill is not None and len(self.q) >= self.max_fill:
                want = False
            p.winc.value = int(want)
            p.wdata.value = self.rng.randrange(16) & self.mask

    async def write_mon(self):
        p = self.p
        while True:
            await RisingEdge(p.wclk)
            inc, full = int(p.winc.value), int(p.full.value)
            data = int(p.wdata.value)
            self.full_seen += full
            if len(self.q) >= CAPACITY and not full:
                self.err(f"t={cocotb.utils.get_sim_time('ns'):.0f}ns isi={len(self.q)} tapi full=0")
            if inc and not full:
                # Data yang tercatat = data di pin; wrapper bisa membuang bit.
                self.q.append(data)
                self.writes += 1
                self.max_occ = max(self.max_occ, len(self.q))

    # --- driver + monitor domain read ---
    async def reader(self):
        p = self.p
        while self.running:
            await FallingEdge(p.rclk)
            p.rinc.value = int(self.rng.random() < self.pr)

    async def read_mon(self):
        p = self.p
        while True:
            await RisingEdge(p.rclk)
            inc, empty = int(p.rinc.value), int(p.empty.value)
            # RAM tidak di-reset: read_data boleh X selama empty=1.
            data = int(p.rdata.value) if not empty else None
            self.empty_seen += empty
            if not self.q and not empty:
                self.err(f"t={cocotb.utils.get_sim_time('ns'):.0f}ns antrean kosong tapi empty=0")
            if not empty and self.q and data != self.q[0]:
                self.err(f"t={cocotb.utils.get_sim_time('ns'):.0f}ns read_data={data:x} "
                         f"kepala={self.q[0]:x} isi={len(self.q)}")
            if inc and not empty:
                if self.q:
                    self.q.popleft()
                self.reads += 1


class GrayMon:
    """Hamming distance tiap perubahan pointer Gray pra-sinkronisasi."""

    def __init__(self, fifo):
        self.f = fifo
        self.bad = []
        self.changes = 0
        self.seen = {"w": {0}, "r": {0}}

    async def watch_pre(self, sig, key):
        prev = int(sig.value)
        while True:
            await Edge(sig)
            v = int(sig.value)
            self.changes += 1
            if bin(v ^ prev).count("1") != 1:
                self.bad.append(f"{key}: {prev:05b}->{v:05b}")
            self.seen[key].add(v)
            prev = v

    async def watch_post(self, sig, key):
        while True:
            await Edge(sig)
            v = int(sig.value)
            if v not in self.seen[key]:
                self.bad.append(f"{key}_postsync {v:05b} tidak pernah ada di sumber")

    def start(self):
        f = self.f
        cocotb.start_soon(self.watch_pre(f.write_address_gray_presync, "w"))
        cocotb.start_soon(self.watch_pre(f.read_address_gray_presync, "r"))
        cocotb.start_soon(self.watch_post(f.write_address_gray_postsync, "w"))
        cocotb.start_soon(self.watch_post(f.read_address_gray_postsync, "r"))


async def init(dut):
    dut.clk.value = 0
    dut.rst_n.value = 1
    dut.ena.value = 1
    for n in ("t_wclk", "t_winc", "t_rclk", "t_rinc", "t_wdata",
              "c_wclk", "c_winc", "c_rclk", "c_rinc", "c_wdata"):
        getattr(dut, n).value = 0
    dut.t_wrst_n.value = 1
    dut.t_rrst_n.value = 1
    dut.c_wrst.value = 0
    dut.c_rrst.value = 0
    await Timer(1, units="ns")


async def reset(port, wclk, rclk):
    port.set_reset(True)
    await Timer(3 * max(wclk, rclk), units="ns")
    port.set_reset(False)
    await Timer(3 * max(wclk, rclk), units="ns")


# Profil (pw, pr): seimbang, writer lebih cepat (uji full), reader lebih cepat (uji empty)
PROFILES = [(0.5, 0.5), (0.9, 0.2), (0.2, 0.9), (1.0, 1.0), (0.7, 0.0), (0.0, 0.8)]


async def run_random(dut, which, seed, segments, edges_per_segment, data_mask=0xF,
                     max_fill=None):
    await init(dut)
    port = Port(dut, which)
    rng = random.Random(seed)
    bench = Bench(port, seed + 1, data_mask, max_fill)
    gm = GrayMon(port.fifo)

    # Reset dengan clock berjalan
    wc = cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    rc = cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    gm.start()
    for co in (bench.write_mon(), bench.read_mon(), bench.writer(), bench.reader()):
        cocotb.start_soon(co)

    ratios = []
    for s in range(segments):
        # Periode dalam ps, genap agar setengah periode tetap bilangan bulat.
        tw = 2 * rng.randrange(2000, 60000)
        tr = 2 * rng.randrange(2000, 60000)
        ratios.append(round(tw / tr, 3))
        bench.pw, bench.pr = PROFILES[s % len(PROFILES)]
        wc.kill()
        rc.kill()
        await Timer(rng.randrange(1, tw), units="ps")
        wc = cocotb.start_soon(Clock(port.wclk, tw, units="ps").start(start_high=False))
        await Timer(rng.randrange(1, tr), units="ps")
        rc = cocotb.start_soon(Clock(port.rclk, tr, units="ps").start(start_high=False))
        await Timer(edges_per_segment * max(tw, tr) // 2, units="ps")

    # Kuras: hentikan write, baca sampai habis
    bench.pw, bench.pr = 0.0, 1.0
    await Timer(4 * (CAPACITY + 4) * 120, units="ns")
    bench.running = False
    leftover = len(bench.q)
    wc.kill()
    rc.kill()
    return bench, gm, ratios, leftover


def summary(bench, gm, ratios, leftover):
    return {
        "segmen": len(ratios),
        "rasio_tw_tr_min": min(ratios), "rasio_tw_tr_maks": max(ratios),
        "write_diterima": bench.writes, "read_diterima": bench.reads,
        "isi_maks": bench.max_occ, "sisa_setelah_kuras": leftover,
        "siklus_write_dengan_full": bench.full_seen,
        "siklus_read_dengan_empty": bench.empty_seen,
        "perubahan_gray": gm.changes, "pelanggaran_gray": gm.bad[:10],
        "galat_scoreboard": bench.errors[:10],
    }


def assert_clean(bench, gm, left, expect_full_reached):
    assert not bench.errors, bench.errors[:5]
    assert not gm.bad, gm.bad[:5]
    assert left == 0, f"{left} data tertinggal setelah kuras"
    assert bench.writes == bench.reads
    if expect_full_reached:
        assert bench.max_occ == CAPACITY, f"isi maks {bench.max_occ}, harusnya {CAPACITY}"
        assert bench.full_seen > 0
    assert bench.empty_seen > 0


async def fill_from(dut, pre):
    """Tulis+baca `pre` item, lalu tulis terus tanpa read; kembalikan jumlah diterima."""
    await init(dut)
    port = Port(dut, "core")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 17, units="ns").start())
    await reset(port, 10, 17)
    for _ in range(pre):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        await FallingEdge(port.wclk)
        port.winc.value = 0
        await Timer(100, units="ns")   # tunggu empty turun (sinkronisasi 2 flop)
        await FallingEdge(port.rclk)
        port.rinc.value = 1
        await FallingEdge(port.rclk)
        port.rinc.value = 0
    await Timer(200, units="ns")   # biarkan pointer read tersinkron ke domain write
    accepted = 0
    for i in range(40):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = i & 0xF
        await RisingEdge(port.wclk)
        accepted += int(port.full.value) == 0
    await FallingEdge(port.wclk)
    port.winc.value = 0
    await Timer(200, units="ns")
    ra = int(port.fifo.read_address.value)
    assert ra == pre % (1 << ADDR_W), f"persiapan gagal: read_address={ra}, harusnya {pre % (1 << ADDR_W)}"
    return accepted, int(port.full.value), int(port.empty.value), int(port.fifo.write_address.value)


FRESH = (0xA, 0xB, 0xC)


async def single_domain_reset(dut, domain, mask=0xF):
    """Isi FIFO lewat pin TT, lalu reset HANYA satu domain lewat pin uio-nya.

    Mengembalikan pengamatan: flag segera setelah reset, isi yang masih bisa
    dibaca sebelum write baru, dan hasil baca setelah 3 write baru (FRESH).
    Perilaku yang benar: FIFO kosong di kedua sisi, tidak ada data lama yang
    terbaca, dan tepat 3 item baru kembali berurutan.

    `mask` membatasi bit data yang ditulis. Audit baseline memakai mask=0x1
    agar hasilnya tidak tercampur dengan F1 (bit data 1-3 hilang).
    """
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)

    async def write(v):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = v
        await FallingEdge(port.wclk)
        port.winc.value = 0

    async def drain(limit=40):
        got = []
        for _ in range(limit):
            await FallingEdge(port.rclk)
            if int(port.empty.value):
                break
            got.append(int(port.rdata.value))
            port.rinc.value = 1
            await FallingEdge(port.rclk)
            port.rinc.value = 0
        return got

    for v in range(1, 7):
        await write(v & mask)
    await Timer(200, units="ns")
    first = []
    for _ in range(2):  # konsumsi 2 item -> pointer read = 2, isi = 4
        await FallingEdge(port.rclk)
        first.append(int(port.rdata.value))
        port.rinc.value = 1
        await FallingEdge(port.rclk)
        port.rinc.value = 0
    await Timer(200, units="ns")

    pin = dut.t_wrst_n if domain == "write" else dut.t_rrst_n
    pin.value = 0
    await Timer(100, units="ns")
    pin.value = 1
    await Timer(300, units="ns")
    after = {"empty": int(port.empty.value), "full": int(port.full.value)}
    stale = await drain()
    for v in FRESH:
        await write(v & mask)
    await Timer(300, units="ns")
    fresh = await drain()
    return {"sebelum": first, "flag_setelah_reset": after, "terbaca_sebelum_write_baru": stale,
            "terbaca_setelah_write_baru": fresh, "mask": mask}


def single_domain_reset_ok(obs):
    return (obs["flag_setelah_reset"] == {"empty": 1, "full": 0}
            and obs["terbaca_sebelum_write_baru"] == []
            and obs["terbaca_setelah_write_baru"] == [v & obs["mask"] for v in FRESH])
