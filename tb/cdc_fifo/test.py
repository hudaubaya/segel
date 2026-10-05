"""Test cocotb CDC FIFO SEGEL (rtl/cdc_fifo/): perbaikan F1, F2, F3, F5, dan
sinkronisasi reset (assert asinkron, deassert sinkron per domain).

Memakai bench yang sama dengan audit baseline (tb/common/cdc_fifo_bench.py).
Skenario yang di baseline ditandai expect_fail (F1, F2, F3) di sini harus lulus.
F5 (pointer Gray diregister) dan sumber reset setiap flop dibuktikan secara
struktur oleh tb/struct/check_cdc_regs.py; test di sini memeriksa nilai dan
waktunya.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer
from cocotb.utils import get_sim_time

from cdc_fifo_bench import (ADDR_W, Port, assert_clean, fill_from, gray, init, reset,
                            run_random, single_domain_reset, single_domain_reset_ok)

# F4: pointer dengan bit wrap, semua 2^ADDR_W slot terpakai (baseline: 31).
CAPACITY = 1 << ADDR_W

# Model metastabilitas aktif (make META=1)?
META = os.environ.get("METASTABILITY_SIM") == "1"


# --- F3: full benar di semua posisi pointer ---------------------------------

@cocotb.test()
async def test_core_capacity_after_reset(dut):
    """F3/F4: setelah reset (pointer read = 0), tepat 32 write diterima lalu full=1."""
    acc, full, empty, wa = await fill_from(dut, 0)
    assert (acc, full, empty) == (CAPACITY, 1, 0), (acc, full, empty, wa)


@cocotb.test()
async def test_core_capacity_every_read_pointer(dut):
    """F3/F4: untuk pointer read 0..64 (kedua nilai bit wrap, termasuk membungkus
    kembali ke 0), tepat 32 write diterima lalu full=1."""
    bad = []
    for pre in range(65):
        acc, full, empty, _ = await fill_from(dut, pre)
        if (acc, full, empty) != (CAPACITY, 1, 0):
            bad.append((pre, acc, full, empty))
    assert not bad, f"(pointer read, diterima, full, empty) salah: {bad}"


@cocotb.test()
async def test_core_random_ratios(dut):
    """F3: 24 rasio clock acak tanpa batas isi (seed sama dengan audit yang gagal)."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC1, 24, 600,
                                               capacity=CAPACITY)
    dut._log.info("write=%d read=%d isi_maks=%d full_terlihat=%d",
                  bench.writes, bench.reads, bench.max_occ, bench.full_seen)
    assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_core_random_ratios_more_seeds(dut):
    """F3: tiga seed tambahan, masing-masing 12 rasio clock acak tanpa batas isi."""
    for seed in (0xF1F0, 0x5E6E1, 0x0036):
        bench, gm, ratios, left = await run_random(dut, "core", seed, 12, 600,
                                               capacity=CAPACITY)
        assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_core_random_ratios_below_full(dut):
    """Regresi: skenario yang sudah lulus di baseline tetap lulus (isi <= 30)."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC0, 24, 600, max_fill=CAPACITY - 2,
                                               capacity=CAPACITY)
    assert_clean(bench, gm, left, expect_full_reached=False)


# --- F1: data 4 bit lewat pin ------------------------------------------------

@cocotb.test()
async def test_top_random_ratios_4bit(dut):
    """F1+F3: lewat pin TT, data 4 bit acak, tanpa batas isi, 12 rasio clock acak."""
    bench, gm, ratios, left = await run_random(dut, "top", 0x7070, 12, 400,
                                               capacity=CAPACITY)
    dut._log.info("write=%d read=%d isi_maks=%d full_terlihat=%d",
                  bench.writes, bench.reads, bench.max_occ, bench.full_seen)
    assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_top_unused_outputs(dut):
    """uo_out[3:2], uio_out, uio_oe tetap 0."""
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    for i in range(50):
        port.winc.value = i % 2
        port.rinc.value = (i // 3) % 2
        port.wdata.value = i & 0xF
        await Timer(7, units="ns")
        assert dut.uo_out.value.binstr[4:6] == "00", dut.uo_out.value.binstr
        assert int(dut.uio_out.value) == 0 and int(dut.uio_oe.value) == 0


# --- F2: rst_n global --------------------------------------------------------

async def _write_n(port, n):
    for i in range(n):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = (i + 1) & 0xF
    await FallingEdge(port.wclk)
    port.winc.value = 0


def _pointers(port):
    f = port.fifo
    return (int(f.write_address.value), int(f.read_address.value),
            int(f.write_address_gray_presync.value), int(f.read_address_gray_presync.value))


@cocotb.test()
async def test_top_rst_n_resets_fifo(dut):
    """F2: rst_n rendah (pin uio reset tidak aktif) mengosongkan FIFO di kedua domain."""
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    await _write_n(port, 7)
    await Timer(100, units="ns")
    assert int(port.empty.value) == 0
    dut.rst_n.value = 0
    await Timer(30, units="ns")
    assert _pointers(port) == (0, 0, 0, 0), _pointers(port)
    assert int(port.empty.value) == 1 and int(port.full.value) == 0
    dut.rst_n.value = 1
    await Timer(100, units="ns")
    # Setelah reset, FIFO bekerja normal lagi: tulis 3 item, baca kembali berurutan.
    await _write_n(port, 3)
    await Timer(100, units="ns")
    got = []
    for _ in range(3):
        await FallingEdge(port.rclk)
        assert int(port.empty.value) == 0
        got.append(int(port.rdata.value))
        port.rinc.value = 1
        await FallingEdge(port.rclk)
        port.rinc.value = 0
    assert got == [1, 2, 3], got


@cocotb.test()
async def test_top_rst_n_async_without_clocks(dut):
    """F2: rst_n bekerja asinkron, juga saat kedua clock berhenti."""
    await init(dut)
    port = Port(dut, "top")
    wc = cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    rc = cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    await _write_n(port, 4)
    await Timer(100, units="ns")
    wc.kill()
    rc.kill()
    await Timer(50, units="ns")
    assert _pointers(port)[0] == 4
    dut.rst_n.value = 0
    await Timer(5, units="ns")
    assert _pointers(port) == (0, 0, 0, 0), _pointers(port)
    assert int(port.empty.value) == 1
    dut.rst_n.value = 1


@cocotb.test()
async def test_top_uio_resets_still_work(dut):
    """F2: pin reset per domain (uio_in[0]/[1]) tetap berfungsi saat rst_n tinggi."""
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    await _write_n(port, 6)
    await Timer(100, units="ns")
    assert int(dut.rst_n.value) == 1 and int(port.empty.value) == 0
    port.set_reset(True)
    await Timer(30, units="ns")
    assert _pointers(port) == (0, 0, 0, 0), _pointers(port)
    port.set_reset(False)


# --- F5: nilai pointer Gray yang diregister ----------------------------------

@cocotb.test()
async def test_registered_gray_equals_gray_of_binary(dut):
    """F5: setelah setiap tepi clock, pointer Gray register == gray(pointer biner)
    (pointer lengkap ADDRESS_WIDTH+1 bit, F4)."""
    await init(dut)
    port = Port(dut, "core")
    f = port.fifo
    rng = random.Random(0xF5)
    checked = {"w": 0, "r": 0}
    bad = []

    async def watch(clk, b, g, key):
        while True:
            await FallingEdge(clk)  # setengah siklus setelah tepi naik: nilai sudah stabil
            if int(g.value) != gray(int(b.value)):
                bad.append((key, int(b.value), int(g.value)))
            checked[key] += 1

    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)
    # F4: Gray adalah pointer lengkap (dengan bit wrap), bukan alamat RAM.
    cocotb.start_soon(watch(port.wclk, f.writestate.write_pointer, f.write_address_gray_presync, "w"))
    cocotb.start_soon(watch(port.rclk, f.readstate.read_pointer, f.read_address_gray_presync, "r"))

    async def drive(clk, sig, p):
        while True:
            await FallingEdge(clk)
            sig.value = int(rng.random() < p)

    cocotb.start_soon(drive(port.wclk, port.winc, 0.6))
    cocotb.start_soon(drive(port.rclk, port.rinc, 0.6))
    await Timer(40000, units="ns")
    dut._log.info("dicek: write=%d read=%d", checked["w"], checked["r"])
    assert checked["w"] > 3000 and checked["r"] > 1500
    assert not bad, bad[:5]


# --- sinkronisasi reset --------------------------------------------------------

DOMAINS = {
    # nama: (atribut clock Port, sinyal reset masuk di tb, sinyal reset tersinkron)
    "write": ("wclk", "c_wrst", "write_reset_sync"),
    "read": ("rclk", "c_rrst", "read_reset_sync"),
}


async def _release_and_count(dut, port, domain, offset_ps, period_ps):
    """Aktifkan reset, lepas di fase `offset_ps` setelah tepi naik, lalu hitung
    tepi naik sampai reset tersinkron turun. Kembalikan (jumlah tepi, waktu
    turun - waktu tepi terakhir dalam ps)."""
    clk_name, rst_name, sync_name = DOMAINS[domain]
    clk = getattr(port, clk_name)
    rst = getattr(dut, rst_name)
    sync = getattr(port.fifo, sync_name)

    await Timer(1, units="ps")  # keluar dari fase ReadOnly pemanggilan sebelumnya
    rst.value = 1
    await Timer(1, units="ps")
    assert int(sync.value) == 1, "assert reset tidak asinkron"
    for _ in range(3):
        await RisingEdge(clk)
    await Timer(offset_ps, units="ps")
    rst.value = 0
    await ReadOnly()
    assert int(sync.value) == 1, "reset tersinkron turun tanpa tepi clock"
    edges = 0
    while True:
        await RisingEdge(clk)
        t_edge = get_sim_time("ps")
        edges += 1
        await ReadOnly()
        if int(sync.value) == 0:
            return edges, get_sim_time("ps") - t_edge
        assert edges < 10, "reset tidak pernah dilepas"


@cocotb.test()
async def test_reset_deassert_synchronous(dut):
    """Reset tersinkron turun tepat di tepi naik ke-2 setelah pin reset dilepas,
    untuk 60 fase pelepasan acak di setiap domain; assert-nya asinkron."""
    await init(dut)
    port = Port(dut, "core")
    periods = {"write": 10000, "read": 23000}  # ps
    cocotb.start_soon(Clock(port.wclk, periods["write"], units="ps").start())
    cocotb.start_soon(Clock(port.rclk, periods["read"], units="ps").start())
    await reset(port, 10, 23)
    rng = random.Random(0x5EED)
    seen = {}
    for domain, period in periods.items():
        for _ in range(60):
            offset = rng.randrange(1, period)  # hindari tepat di tepi (race RTL)
            edges, delta = await _release_and_count(dut, port, domain, offset, period)
            assert delta == 0, (domain, offset, edges, delta)
            # Dengan model metastabilitas, pelepasan dalam jendela 1 ns sebelum
            # tepi boleh mundur satu siklus (3 tepi); di luar jendela harus 2.
            in_window = META and (period - offset) < 1000
            assert edges == 2 or (in_window and edges == 3), (domain, offset, edges)
            seen[domain] = seen.get(domain, 0) + 1
            seen["mundur"] = seen.get("mundur", 0) + (edges == 3)
    dut._log.info("pelepasan diuji: %s", seen)
    if META:
        assert seen["mundur"] > 0, "model metastabilitas reset tidak pernah memundurkan pelepasan"


@cocotb.test()
async def test_reset_held_while_clock_stopped(dut):
    """Kalau clock domain berhenti, reset tetap aktif sampai 2 tepi clock setelah
    clock berjalan lagi; domain lain tidak terpengaruh."""
    await init(dut)
    port = Port(dut, "core")
    wc = cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)
    f = port.fifo
    wc.kill()
    dut.c_wrst.value = 1
    await Timer(1, units="ns")
    assert int(f.write_reset_sync.value) == 1
    dut.c_wrst.value = 0
    await Timer(500, units="ns")
    assert int(f.write_reset_sync.value) == 1, "reset dilepas tanpa clock"
    assert int(f.read_reset_sync.value) == 0, "domain read ikut ter-reset"
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    await RisingEdge(port.wclk)
    await ReadOnly()
    assert int(f.write_reset_sync.value) == 1
    await RisingEdge(port.wclk)
    await ReadOnly()
    assert int(f.write_reset_sync.value) == 0


@cocotb.test()
async def test_top_reset_paths_use_synchronizer(dut):
    """rst_n dan pin uio sama-sama lewat reset synchronizer di wrapper TT."""
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)
    f = port.fifo
    for assert_fn, release_fn in (
        (lambda: setattr(dut.rst_n, "value", 0), lambda: setattr(dut.rst_n, "value", 1)),
        (lambda: port.set_reset(True), lambda: port.set_reset(False)),
    ):
        assert_fn()
        await Timer(1, units="ns")
        assert int(f.write_reset_sync.value) == 1 and int(f.read_reset_sync.value) == 1
        await Timer(3, units="ns")
        release_fn()
        await Timer(1, units="ns")
        assert int(f.write_reset_sync.value) == 1 and int(f.read_reset_sync.value) == 1
        await Timer(100, units="ns")
        assert int(f.write_reset_sync.value) == 0 and int(f.read_reset_sync.value) == 0


# --- reset satu domain (F6) -----------------------------------------------------

@cocotb.test()
async def test_top_write_domain_reset_empties_fifo(dut):
    """F6: reset hanya lewat uio_in[0] (domain write) mengosongkan seluruh FIFO."""
    obs = await single_domain_reset(dut, "write")
    dut._log.info("%s", obs)
    assert single_domain_reset_ok(obs), obs


@cocotb.test()
async def test_top_read_domain_reset_empties_fifo(dut):
    """F6: reset hanya lewat uio_in[1] (domain read) mengosongkan seluruh FIFO."""
    obs = await single_domain_reset(dut, "read")
    dut._log.info("%s", obs)
    assert single_domain_reset_ok(obs), obs


@cocotb.test()
async def test_reset_release_order_is_safe(dut):
    """F6: kalau clock read berhenti saat reset dilepas, domain write keluar dari
    reset lebih dulu dan menulis; setelah clock read berjalan, semua data utuh."""
    await init(dut)
    port = Port(dut, "core")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    rc = cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)
    f = port.fifo
    rc.kill()
    dut.c_wrst.value = 1  # reset lewat pin domain write saja
    await Timer(50, units="ns")
    dut.c_wrst.value = 0
    await Timer(100, units="ns")
    assert int(f.write_reset_sync.value) == 0, "domain write tidak keluar dari reset"
    assert int(f.read_reset_sync.value) == 1, "domain read harus tetap reset tanpa clock"
    sent = [3, 1, 4, 1, 5, 9, 2, 6]
    for v in sent:
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = v
        await RisingEdge(port.wclk)
        assert int(port.full.value) == 0
    await FallingEdge(port.wclk)
    port.winc.value = 0
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await Timer(300, units="ns")
    got = []
    for _ in range(len(sent) + 2):
        await FallingEdge(port.rclk)
        if int(port.empty.value):
            break
        got.append(int(port.rdata.value))
        port.rinc.value = 1
        await FallingEdge(port.rclk)
        port.rinc.value = 0
    assert got == sent, (got, sent)


# --- model metastabilitas (make META=1) --------------------------------------------

@cocotb.test(skip=not META)
async def test_metastability_model_active(dut):
    """Model metastabilitas benar-benar menyuntikkan resolusi acak di kedua
    synchronizer pointer selama skenario ini, dan FIFO tetap benar (scoreboard +
    monitor Gray)."""
    if not META:  # TESTCASE eksplisit menjalankan test skip di cocotb 1.8
        dut._log.info("dilewati: model metastabilitas tidak aktif (jalankan dengan META=1)")
        return
    f = dut.core
    names = ("write_address_sync", "read_address_sync")

    def counters():
        return {n: (int(getattr(f, n).events.value), int(getattr(f, n).delayed.value))
                for n in names}

    # Penghitung di RTL kumulatif sepanjang simulasi: ukur selisihnya saja.
    before = counters()
    bench, gm, ratios, left = await run_random(dut, "core", 0x3E7A, 24, 600, capacity=CAPACITY)
    after = counters()
    stats = {n: (after[n][0] - before[n][0], after[n][1] - before[n][1]) for n in names}
    dut._log.info("events/delayed selama test ini: %s; write=%d read=%d",
                  stats, bench.writes, bench.reads)
    for name, (ev, dl) in stats.items():
        assert ev > 0 and dl > 0, f"{name}: model tidak pernah aktif ({ev}, {dl})"
    assert_clean(bench, gm, left, expect_full_reached=True)
