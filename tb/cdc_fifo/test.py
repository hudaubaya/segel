"""Test cocotb CDC FIFO SEGEL (rtl/cdc_fifo/): perbaikan F1, F2, F3, F5.

Memakai bench yang sama dengan audit baseline (tb/common/cdc_fifo_bench.py).
Skenario yang di baseline ditandai expect_fail (F1, F2, F3) di sini harus lulus.
F5 (pointer Gray diregister) dibuktikan secara struktur oleh
tb/struct/check_cdc_regs.py; test di sini memastikan nilainya tidak berubah.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

from cdc_fifo_bench import (CAPACITY, Port, assert_clean, fill_from, gray, init, reset,
                            run_random)


# --- F3: full benar di semua posisi pointer ---------------------------------

@cocotb.test()
async def test_core_capacity_after_reset(dut):
    """F3: setelah reset (pointer read = 0), tepat 31 write diterima lalu full=1."""
    acc, full, empty, wa = await fill_from(dut, 0)
    assert (acc, full, empty) == (CAPACITY, 1, 0), (acc, full, empty, wa)


@cocotb.test()
async def test_core_capacity_every_read_pointer(dut):
    """F3: untuk pointer read 0..32 (32 = membungkus ke 0), tepat 31 write diterima."""
    bad = []
    for pre in range(33):
        acc, full, empty, _ = await fill_from(dut, pre)
        if (acc, full, empty) != (CAPACITY, 1, 0):
            bad.append((pre, acc, full, empty))
    assert not bad, f"(pointer read, diterima, full, empty) salah: {bad}"


@cocotb.test()
async def test_core_random_ratios(dut):
    """F3: 24 rasio clock acak tanpa batas isi (seed sama dengan audit yang gagal)."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC1, 24, 600)
    dut._log.info("write=%d read=%d isi_maks=%d full_terlihat=%d",
                  bench.writes, bench.reads, bench.max_occ, bench.full_seen)
    assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_core_random_ratios_more_seeds(dut):
    """F3: tiga seed tambahan, masing-masing 12 rasio clock acak tanpa batas isi."""
    for seed in (0xF1F0, 0x5E6E1, 0x0036):
        bench, gm, ratios, left = await run_random(dut, "core", seed, 12, 600)
        assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_core_random_ratios_below_full(dut):
    """Regresi: skenario yang sudah lulus di baseline tetap lulus."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC0, 24, 600, max_fill=CAPACITY - 2)
    assert_clean(bench, gm, left, expect_full_reached=False)


# --- F1: data 4 bit lewat pin ------------------------------------------------

@cocotb.test()
async def test_top_random_ratios_4bit(dut):
    """F1+F3: lewat pin TT, data 4 bit acak, tanpa batas isi, 12 rasio clock acak."""
    bench, gm, ratios, left = await run_random(dut, "top", 0x7070, 12, 400)
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
    """F5: setelah setiap tepi clock, pointer Gray register == gray(pointer biner)."""
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
    cocotb.start_soon(watch(port.wclk, f.write_address, f.write_address_gray_presync, "w"))
    cocotb.start_soon(watch(port.rclk, f.read_address, f.read_address_gray_presync, "r"))

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
