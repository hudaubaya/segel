"""Test cocotb CRC-8, dijalankan terhadap RTL SEGEL dan netlist baseline #0901.

Input diubah di tepi turun clk dan output dibaca di tepi turun berikutnya,
sehingga satu iterasi = satu tepi naik. Periode clock 100 ns memberi slack
lebar untuk UNIT_DELAY=#1 pada simulasi gate-level.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer

import crc8 as model

CLK_NS = 100


async def setup(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())
    for _ in range(3):
        await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    assert dut.uo_out.value == model.INIT, f"setelah reset: {dut.uo_out.value}"


async def step(dut, byte, en=1, uio_hi=0, ena=1):
    """Satu siklus clock; kembalikan uo_out setelah tepi naik."""
    dut.ui_in.value = byte
    dut.uio_in.value = ((uio_hi & 0x7F) << 1) | (en & 1)
    dut.ena.value = ena
    await FallingEdge(dut.clk)
    return int(dut.uo_out.value)


@cocotb.test()
async def test_check_value(dut):
    """CRC-8/SMBUS atas "123456789" harus 0xF4."""
    await setup(dut)
    crc = model.INIT
    for b in b"123456789":
        crc = await step(dut, b)
    assert crc == model.CHECK, f"got 0x{crc:02x}, expected 0x{model.CHECK:02x}"


@cocotb.test()
async def test_exhaustive_next_state(dut):
    """Semua 256 x 256 pasangan (state, byte) untuk fungsi next-state.

    Tiap state dicapai dengan satu byte "steer" (TABLE adalah permutasi),
    lalu byte uji diserap dan hasilnya dibandingkan dengan model.
    """
    await setup(dut)
    cur = model.INIT
    for s in range(256):
        for b in range(256):
            got = await step(dut, model.steer(cur, s))
            assert got == s, f"steer {cur:02x}->{s:02x} got {got:02x}"
            got = await step(dut, b)
            exp = model.update(s, b)
            assert got == exp, f"state {s:02x} byte {b:02x}: got {got:02x} exp {exp:02x}"
            cur = got


@cocotb.test()
async def test_enable_holds(dut):
    """en=0 menahan nilai untuk setiap state dan byte acak."""
    await setup(dut)
    rng = random.Random(0x5E6E1)
    cur = model.INIT
    for s in range(256):
        cur = await step(dut, model.steer(cur, s))
        assert cur == s
        for _ in range(4):
            got = await step(dut, rng.randrange(256), en=0)
            assert got == s, f"en=0 state {s:02x} berubah jadi {got:02x}"


@cocotb.test()
async def test_random_stream(dut):
    """Aliran acak dengan en, ena, dan uio_in[7:1] acak; uio_out/uio_oe harus 0."""
    await setup(dut)
    rng = random.Random(0xC8C8)
    exp = model.INIT
    for i in range(20000):
        b = rng.randrange(256)
        en = rng.random() < 0.7
        got = await step(dut, b, en=en, uio_hi=rng.randrange(128), ena=rng.randrange(2))
        if en:
            exp = model.update(exp, b)
        assert got == exp, f"siklus {i}: got {got:02x} exp {exp:02x}"
        assert dut.uio_out.value == 0 and dut.uio_oe.value == 0


@cocotb.test()
async def test_async_reset(dut):
    """rst_n rendah di tengah siklus langsung mengosongkan CRC tanpa tepi clk."""
    await setup(dut)
    for b in b"SEGEL":
        await step(dut, b)
    assert dut.uo_out.value != model.INIT
    await Timer(CLK_NS // 4, units="ns")  # masih fase clk rendah, sebelum tepi naik
    dut.rst_n.value = 0
    await Timer(10, units="ns")
    assert dut.uo_out.value == model.INIT, f"reset asinkron gagal: {dut.uo_out.value}"
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    crc = model.INIT
    for b in b"123456789":
        crc = await step(dut, b)
    assert crc == model.CHECK
