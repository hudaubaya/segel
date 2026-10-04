"""Audit gate-level #0036: perilaku pin netlist tapeout tt_um_pa1mantri_cdc_fifo.

ID temuan merujuk ke docs/baseline_audit.md.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

CAPACITY = 31


async def setup(dut, tw=100, tr=170):
    for n in ("t_wclk", "t_winc", "t_rclk", "t_rinc", "t_wdata"):
        getattr(dut, n).value = 0
    dut.t_wrst_n.value = 0
    dut.t_rrst_n.value = 0
    cocotb.start_soon(Clock(dut.t_wclk, tw, units="ns").start())
    cocotb.start_soon(Clock(dut.t_rclk, tr, units="ns").start())
    await Timer(4 * max(tw, tr), units="ns")
    dut.t_wrst_n.value = 1
    dut.t_rrst_n.value = 1
    await Timer(4 * max(tw, tr), units="ns")


async def write(dut, data):
    await FallingEdge(dut.t_wclk)
    dut.t_winc.value = 1
    dut.t_wdata.value = data
    await RisingEdge(dut.t_wclk)
    accepted = int(dut.t_full.value) == 0
    await FallingEdge(dut.t_wclk)
    dut.t_winc.value = 0
    return accepted


async def read(dut):
    """Baca satu item (tunggu sampai empty=0); kembalikan read_data."""
    for _ in range(50):
        await FallingEdge(dut.t_rclk)
        if int(dut.t_empty.value) == 0:
            break
    else:
        raise AssertionError("FIFO tetap kosong")
    data = int(dut.t_rdata.value)
    dut.t_rinc.value = 1
    await FallingEdge(dut.t_rclk)
    dut.t_rinc.value = 0
    return data


async def fill(dut):
    accepted = 0
    for i in range(40):
        accepted += await write(dut, i & 0xF)
    await Timer(2000, units="ns")
    return accepted, int(dut.t_full.value), int(dut.t_empty.value)


@cocotb.test()
async def test_gl_capacity_read_ptr_nonzero(dut):
    """Pointer read = 5: tepat 31 write diterima lalu full=1."""
    await setup(dut)
    for _ in range(5):
        await write(dut, 0)
        await Timer(1000, units="ns")
        await read(dut)
    await Timer(2000, units="ns")
    acc, full, empty = await fill(dut)
    assert (acc, full, empty) == (CAPACITY, 1, 0), (acc, full, empty)


@cocotb.test(expect_fail=True)  # F3
async def test_gl_capacity_after_reset(dut):
    """Setelah reset: tepat 31 write diterima lalu full=1."""
    await setup(dut)
    acc, full, empty = await fill(dut)
    dut._log.info("write diterima=%d full=%d empty=%d", acc, full, empty)
    assert (acc, full, empty) == (CAPACITY, 1, 0), (acc, full, empty)


@cocotb.test(expect_fail=True)  # F1
async def test_gl_data_4bit(dut):
    """Nilai 0..15 di ui_in[7:4] keluar utuh di uo_out[7:4]."""
    await setup(dut)
    for v in range(16):
        await write(dut, v)
    await Timer(2000, units="ns")
    got = [await read(dut) for _ in range(16)]
    dut._log.info("terbaca %s", got)
    assert got == list(range(16)), got


@cocotb.test()
async def test_gl_data_bit0(dut):
    """Bit write_data0 (ui_in[4]) acak keluar utuh dan berurutan."""
    await setup(dut)
    rng = random.Random(36)
    sent = [rng.randrange(2) for _ in range(20)]
    for v in sent:
        await write(dut, v)
    await Timer(2000, units="ns")
    got = [await read(dut) for _ in range(20)]
    assert got == sent, (got, sent)
