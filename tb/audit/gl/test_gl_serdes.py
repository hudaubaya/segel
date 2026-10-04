"""Audit gate-level #0200: perilaku pin netlist tapeout tt_um_serdes.

Hanya level pin (sinyal internal tidak tersedia di netlist). ID temuan merujuk
ke docs/baseline_audit.md.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

DATA_EN, PAR_EN, SER_EN = 2, 3, 4


async def setup(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, units="us").start())
    for _ in range(3):
        await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


async def cyc(dut, data_en=0, par_en=0, ser_en=0):
    dut.uio_in.value = (data_en << DATA_EN) | (par_en << PAR_EN) | (ser_en << SER_EN)
    await FallingEdge(dut.clk)


async def serialize_pins(dut, byte):
    """Urutan kontrol sama dengan tb/audit/serdes; rekam uio_out dan uio_oe."""
    dut.ui_in.value = byte
    for c in (dict(data_en=1), dict(), dict(ser_en=1), dict(data_en=1, ser_en=1), dict(ser_en=1)):
        await cyc(dut, **c)
    pin0, pin1, oe = [], [], set()
    for _ in range(10):
        await cyc(dut)
        s = dut.uio_out.value.binstr
        pin0.append(s[-1])
        pin1.append(s[-2])
        oe.add(dut.uio_oe.value.binstr)
    return "".join(pin0), "".join(pin1), oe


@cocotb.test()
async def test_gl_tx_reaches_uio_out0_with_oe_low(dut):
    """S11: di netlist, bit serial sampai ke uio_out[0] (RTL: z), tetapi uio_oe = 0."""
    await setup(dut)
    pin0, pin1, oe = await serialize_pins(dut, 0x5A)
    dut._log.info("uio_out[0]=%s uio_out[1]=%s uio_oe=%s", pin0, pin1, sorted(oe))
    # Sama dengan ser_out internal RTL untuk 0x5A (tb/audit/serdes, test_serial_on_pin)
    assert pin0 == "0110101010", pin0
    assert oe == {"00000000"}, oe


@cocotb.test(expect_fail=True)  # S4
async def test_gl_serial_on_datasheet_pin(dut):
    """Bit serial muncul di uio[1] (ser_out menurut info.yaml) dengan uio_oe[1] = 1."""
    await setup(dut)
    pin0, pin1, oe = await serialize_pins(dut, 0x5A)
    assert pin1 == pin0 and all(int(o, 2) & 0b10 for o in oe), (pin1, sorted(oe))
