"""Audit cocotb baseline TT07 #0036 (CDC FIFO), apa adanya.

Rasio clock write/read diacak per segmen (periode dan fase acak, tidak
saling kelipatan). Bench dan pemeriksaannya ada di tb/common/cdc_fifo_bench.py.

Test untuk cacat terkonfirmasi ditandai `expect_fail=True` dengan ID temuan
di docs/baseline_audit.md.
"""

import json
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer

from cdc_fifo_bench import (CAPACITY, Port, assert_clean, fill_from, init, reset,
                            run_random, single_domain_reset, single_domain_reset_ok, summary)

REPORT = os.path.join(os.getcwd(), "audit_cdc_fifo.json")


def save(key, value):
    data = {}
    if os.path.exists(REPORT):
        with open(REPORT) as f:
            data = json.load(f)
    data[key] = value
    with open(REPORT, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)


# --- inti cdc_fifo ---------------------------------------------------------

@cocotb.test()
async def test_core_random_ratios_below_full(dut):
    """Inti: 24 rasio acak, isi dibatasi <= 29 oleh test; urutan data, empty, Gray benar."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC0, 24, 600, max_fill=CAPACITY - 2)
    save("core_random_dibawah_full", summary(bench, gm, ratios, left))
    assert_clean(bench, gm, left, expect_full_reached=False)


@cocotb.test(expect_fail=True)  # F3
async def test_core_random_ratios(dut):
    """Inti: 24 rasio acak tanpa batas isi; tidak ada data hilang dan full benar."""
    bench, gm, ratios, left = await run_random(dut, "core", 0xCDC1, 24, 600)
    save("core_random", summary(bench, gm, ratios, left))
    assert_clean(bench, gm, left, expect_full_reached=True)


@cocotb.test()
async def test_core_capacity_read_ptr_nonzero(dut):
    """Inti: dengan pointer read = 5, tepat 31 write diterima lalu full=1."""
    acc, full, empty, wa = await fill_from(dut, 5)
    save("core_kapasitas_ra_5", {"write_diterima": acc, "full": full, "empty": empty, "write_address": wa})
    assert acc == CAPACITY and full == 1 and empty == 0, (acc, full, empty)


@cocotb.test(expect_fail=True)  # F3
async def test_core_capacity_after_reset(dut):
    """Inti: setelah reset (pointer read = 0), tepat 31 write diterima lalu full=1."""
    acc, full, empty, wa = await fill_from(dut, 0)
    save("core_kapasitas_setelah_reset", {"write_diterima": acc, "full": full, "empty": empty,
                                          "write_address": wa})
    assert acc == CAPACITY and full == 1 and empty == 0, (acc, full, empty)


# --- wrapper TT: lewat pin -------------------------------------------------

@cocotb.test(expect_fail=True)  # F1
async def test_top_random_ratios_4bit(dut):
    """Wrapper TT: data 4 bit lewat ui_in[7:4] keluar utuh di uo_out[7:4] (isi <= 29)."""
    bench, gm, ratios, left = await run_random(dut, "top", 0x7070, 12, 400,
                                               max_fill=CAPACITY - 2)
    save("top_random_4bit", summary(bench, gm, ratios, left))
    assert not bench.errors, bench.errors[:5]


@cocotb.test()
async def test_top_random_ratios_bit0(dut):
    """Wrapper TT: hanya write_data0 (ui_in[4]) divariasikan, isi <= 29; FIFO lewat pin benar."""
    bench, gm, ratios, left = await run_random(dut, "top", 0x7171, 12, 400, data_mask=0x1,
                                               max_fill=CAPACITY - 2)
    save("top_random_bit0", summary(bench, gm, ratios, left))
    assert not bench.errors, bench.errors[:5]
    assert not gm.bad, gm.bad[:5]
    assert left == 0 and bench.writes == bench.reads


@cocotb.test()
async def test_top_unused_outputs(dut):
    """Wrapper TT: uo_out[3:2], uio_out, uio_oe selalu 0."""
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
        uo = dut.uo_out.value.binstr  # MSB dulu; uo_out[7:4] boleh X (RAM belum ditulis)
        assert uo[4:6] == "00", uo
        assert int(dut.uio_out.value) == 0 and int(dut.uio_oe.value) == 0


@cocotb.test(expect_fail=True)  # F2
async def test_top_rst_n_resets_fifo(dut):
    """Wrapper TT: rst_n global (aktif rendah) mengosongkan FIFO."""
    await init(dut)
    port = Port(dut, "top")
    cocotb.start_soon(Clock(port.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(port.rclk, 13, units="ns").start())
    await reset(port, 10, 13)
    for i in range(5):
        await FallingEdge(port.wclk)
        port.winc.value = 1
        port.wdata.value = 1
    await FallingEdge(port.wclk)
    port.winc.value = 0
    await Timer(100, units="ns")
    assert int(port.empty.value) == 0
    dut.rst_n.value = 0
    await Timer(100, units="ns")
    dut.rst_n.value = 1
    await Timer(100, units="ns")
    save("rst_n_global", {"empty_setelah_rst_n": int(port.empty.value)})
    assert int(port.empty.value) == 1, "FIFO tidak kosong setelah rst_n"


@cocotb.test(expect_fail=True)  # F6
async def test_top_write_domain_reset_empties_fifo(dut):
    """Reset hanya lewat uio_in[0] (domain write) mengosongkan seluruh FIFO.
    Data dibatasi ke bit 0 agar kegagalan tidak berasal dari F1."""
    obs = await single_domain_reset(dut, "write", mask=0x1)
    save("reset_hanya_domain_write", obs)
    assert single_domain_reset_ok(obs), obs


@cocotb.test(expect_fail=True)  # F6
async def test_top_read_domain_reset_empties_fifo(dut):
    """Reset hanya lewat uio_in[1] (domain read) mengosongkan seluruh FIFO.
    Data dibatasi ke bit 0 agar kegagalan tidak berasal dari F1."""
    obs = await single_domain_reset(dut, "read", mask=0x1)
    save("reset_hanya_domain_read", obs)
    assert single_domain_reset_ok(obs), obs
