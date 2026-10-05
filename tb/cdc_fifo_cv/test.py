"""Test cocotb netlist Cyclone V CDC FIFO (Yosys synth_intel_alm, sel MISTRAL_*).

Netlist ini adalah inti `cdc_fifo` dari rtl/cdc_fifo/ (parameter DATA_WIDTH=4,
ADDRESS_WIDTH=5). Hanya level port: sinyal internal hilang setelah sintesis,
jadi monitor Gray dimatikan. Simulasi fungsional tanpa timing.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer

from cdc_fifo_bench import ADDR_W, Port, assert_clean, fill_from, init, reset, run_random

CAPACITY = 1 << ADDR_W  # F4


@cocotb.test()
async def test_cv_capacity_every_read_pointer(dut):
    """F3/F4: untuk pointer read 0..64, tepat 32 write diterima lalu full=1."""
    bad = []
    for pre in range(65):
        acc, full, empty, _ = await fill_from(dut, pre)
        if (acc, full, empty) != (CAPACITY, 1, 0):
            bad.append((pre, acc, full, empty))
    assert not bad, f"(pointer read, diterima, full, empty) salah: {bad}"


@cocotb.test()
async def test_cv_random_ratios(dut):
    """24 rasio clock acak tanpa batas isi: urutan data, full, empty benar."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC1, 24, 600,
                                               capacity=CAPACITY, gray_monitor=False)
    dut._log.info("write=%d read=%d isi_maks=%d full_terlihat=%d",
                  bench.writes, bench.reads, bench.max_occ, bench.full_seen)
    assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_cv_random_ratios_more_seeds(dut):
    """Tiga seed tambahan, masing-masing 12 rasio clock acak."""
    for seed in (0xF1F0, 0x5E6E1, 0x0036):
        bench, gm, ratios, left = await run_random(dut, "core", seed, 12, 600,
                                                   capacity=CAPACITY, gray_monitor=False)
        assert_clean(bench, gm, left, expect_full_reached=True)


async def _single_domain_reset_core(dut, which):
    """Isi 6 item, baca 2, lalu reset HANYA satu domain (F6) lewat port inti."""
    await init(dut)
    port = Port(dut, "core")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)

    async def write(v):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = v
        await FallingEdge(port.wclk)
        port.winc.value = 0

    async def read_all(limit=40):
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
        await write(v)
    await Timer(200, units="ns")
    assert (await read_all(2)) == [1, 2]
    rst = dut.c_wrst if which == "write" else dut.c_rrst
    rst.value = 1
    await Timer(100, units="ns")
    rst.value = 0
    await Timer(300, units="ns")
    assert int(port.empty.value) == 1 and int(port.full.value) == 0
    stale = await read_all()
    for v in (0xA, 0xB, 0xC):
        await write(v)
    await Timer(300, units="ns")
    fresh = await read_all()
    return stale, fresh


@cocotb.test()
async def test_cv_single_domain_reset(dut):
    """F6: reset domain write saja atau read saja mengosongkan seluruh FIFO."""
    for which in ("write", "read"):
        stale, fresh = await _single_domain_reset_core(dut, which)
        assert stale == [] and fresh == [0xA, 0xB, 0xC], (which, stale, fresh)


@cocotb.test()
async def test_cv_reset_async_without_clocks(dut):
    """Reset asinkron bekerja di netlist walaupun kedua clock berhenti."""
    await init(dut)
    port = Port(dut, "core")
    wc = cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    rc = cocotb.start_soon(Clock(port.rclk, 23, units="ns").start())
    await reset(port, 10, 23)
    for v in range(4):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = v
    await FallingEdge(port.wclk)
    port.winc.value = 0
    await Timer(200, units="ns")
    assert int(port.empty.value) == 0
    wc.kill()
    rc.kill()
    dut.c_wrst.value = 1
    await Timer(5, units="ns")
    assert int(port.empty.value) == 1, "reset tidak asinkron di netlist"
