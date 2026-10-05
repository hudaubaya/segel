"""Test cocotb CDC FIFO SEGEL (rtl/cdc_fifo/): perbaikan F1 dan F3.

Memakai bench yang sama dengan audit baseline (tb/common/cdc_fifo_bench.py).
Skenario yang di baseline ditandai expect_fail (F1, F3) di sini harus lulus.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer

from cdc_fifo_bench import CAPACITY, Port, assert_clean, fill_from, init, reset, run_random


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
