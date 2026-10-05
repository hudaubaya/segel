"""Uji unit model metastabilitas di rtl/cdc_fifo/synchronizer.sv.

Masukan berganti di dekat tepi clock tujuan (di dalam jendela 1 ns) dan di luar
jendela. Untuk setiap tepi, keluaran dua tepi kemudian dibandingkan dengan
nilai lama dan nilai baru:

  - transisi biner multi-bit (0111 -> 1000): dengan model aktif, keluaran bisa
    berupa campuran bit lama/baru yang TIDAK PERNAH ada di sumber;
  - transisi Gray (1 bit): keluaran selalu nilai lama atau baru;
  - tanpa model (simulasi biasa): keluaran selalu tepat nilai baru.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

META = os.environ.get("METASTABILITY_SIM") == "1"
PERIOD_PS = 20000


async def run(dut, pairs, near):
    """Untuk setiap (lama, baru): set lama, tunggu stabil, ganti ke baru di dekat
    (`near`=True, 0,2-0,8 ns sebelum tepi) atau jauh dari tepi, lalu baca keluaran
    sinkron setelah tepi itu. Kembalikan hitungan kategori."""
    rng = random.Random(11)
    cnt = {"baru": 0, "lama": 0, "campuran": 0}
    for old, new in pairs:
        dut.din.value = old
        for _ in range(4):
            await RisingEdge(dut.clk)
        # ganti nilai `gap` ps sebelum tepi berikutnya
        gap = rng.randrange(200, 800) if near else rng.randrange(5000, 9000)
        await Timer(PERIOD_PS - gap, units="ps")
        dut.din.value = new
        await RisingEdge(dut.clk)   # tepi yang mungkin metastabil (tahap 1)
        await RisingEdge(dut.clk)   # tahap 2 memuat nilai tahap 1
        await Timer(1, units="ps")
        got = int(dut.dout.value)
        cnt["baru" if got == new else "lama" if got == old else "campuran"] += 1
    return cnt


async def setup(dut):
    dut.rst.value = 1
    dut.din.value = 0
    cocotb.start_soon(Clock(dut.clk, PERIOD_PS, units="ps").start())
    for _ in range(3):
        await RisingEdge(dut.clk)
    await Timer(1, units="ps")
    dut.rst.value = 0


BINARY = [(0b0111, 0b1000), (0b1000, 0b0111), (0b0011, 0b1100), (0b1111, 0b0000)] * 50
GRAY = [(0b0100, 0b1100), (0b1100, 0b1101), (0b0001, 0b0011), (0b0110, 0b0111)] * 50


@cocotb.test()
async def test_binary_near_edge(dut):
    """Transisi biner di dalam jendela: model menghasilkan nilai campuran;
    tanpa model selalu nilai baru."""
    await setup(dut)
    cnt = await run(dut, BINARY, near=True)
    dut._log.info("biner dekat tepi: %s", cnt)
    if META:
        assert cnt["campuran"] > 0 and cnt["lama"] > 0 and cnt["baru"] > 0, cnt
        assert int(dut.dut.events.value) > 0
    else:
        assert cnt == {"baru": len(BINARY), "lama": 0, "campuran": 0}, cnt


@cocotb.test()
async def test_gray_near_edge(dut):
    """Transisi Gray di dalam jendela: hanya lama atau baru, tidak pernah campuran."""
    await setup(dut)
    cnt = await run(dut, GRAY, near=True)
    dut._log.info("gray dekat tepi: %s", cnt)
    assert cnt["campuran"] == 0, cnt
    if META:
        assert cnt["lama"] > 0 and cnt["baru"] > 0, cnt
    else:
        assert cnt["lama"] == 0, cnt


@cocotb.test()
async def test_binary_far_from_edge(dut):
    """Perubahan jauh dari tepi (di luar jendela) tidak pernah terpengaruh model."""
    await setup(dut)
    cnt = await run(dut, BINARY, near=False)
    dut._log.info("biner jauh dari tepi: %s", cnt)
    assert cnt == {"baru": len(BINARY), "lama": 0, "campuran": 0}, cnt
