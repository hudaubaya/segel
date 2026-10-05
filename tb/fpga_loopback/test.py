"""Simulasi top DE10-Nano (fpga/phy_loopback) dengan model PLL/DDIO/JTAG.

Peta register dan kolom CSV DIAMBIL dari fpga/phy_loopback/scripts/ber_sweep.tcl, jadi
test ini sekaligus memastikan skrip System Console cocok dengan RTL. Urutan akses
register meniru run_rate di skrip itu.

  test_regmap      ID/VERSION/TX_RATE_KHZ, alamat tak dikenal, tabel Tcl = komentar RTL
  test_prbs_clean  satu putaran sweep: semua frame utuh, BER 0, laju tx_clk terukur
  test_prbs_errors galat bit diinjeksi di jumper: terdeteksi di counter PRBS dan phy;
                   CSV -> sw/ber.py
  test_raw_ber     mode RAW: tanpa galat 0 bit salah; dengan k galat diinjeksi tepat
                   k bit salah (BERT menghitung setiap bit salah sekali), tanpa
                   kehilangan sinkron
"""

import csv
import json
import os
import re
import subprocess
import sys

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge, Timer

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TCL = os.path.join(REPO, "fpga", "phy_loopback", "scripts", "ber_sweep.tcl")
RTL_REGS = os.path.join(REPO, "fpga", "phy_loopback", "rtl", "loopback_regs.v")
TX_SEL = int(os.environ.get("TX_SEL", "3"))
RATE_KHZ = {0: 4990, 1: 9980, 2: 19960, 3: 24750}[TX_SEL]
TX_HZ = 1237.5e6 / {0: 248, 1: 124, 2: 62, 3: 50}[TX_SEL]
PAYLOAD_PRBS = 60


def tcl_regs():
    s = open(TCL).read()
    body = re.search(r"array set REG \{(.*?)\}", s, re.S).group(1)
    tok = body.split()
    return {tok[i]: int(tok[i + 1], 16) for i in range(0, len(tok), 2)}


def tcl_consts():
    s = open(TCL).read()
    c = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"set (CTRL_\w+)\s+(0x[0-9A-Fa-f]+)", s)}
    cols = re.search(r"set CSV_COLUMNS \{(.*?)\}", s, re.S).group(1).split()
    return c, cols


REG = tcl_regs()
CTRL, CSV_COLUMNS = tcl_consts()


class Bus:
    """Master Avalon di stub phy_jtag. Sinyal diubah di tepi TURUN clk50 dan dibaca
    setelah tepi turun berikutnya, sehingga tidak ada race dengan tepi naik tempat
    DUT mengambil sampel (clock dibangkitkan di Verilog)."""

    def __init__(self, dut):
        self.dut = dut
        self.j = dut.u_top.u_jtag
        self.clk = dut.clk50

    async def write(self, name, value):
        await FallingEdge(self.clk)
        self.j.m_address.value = REG[name]
        self.j.m_writedata.value = value
        self.j.m_write.value = 1
        await FallingEdge(self.clk)          # tepi naik di antaranya mengambil tulisan
        self.j.m_write.value = 0

    async def read(self, name=None, addr=None):
        await FallingEdge(self.clk)
        self.j.m_address.value = REG[name] if name else addr
        self.j.m_read.value = 1
        await FallingEdge(self.clk)          # read diambil; readdatavalid naik di tepi itu
        self.j.m_read.value = 0
        u = self.dut.u_top
        if not int(u.avm_readdatavalid.value):
            raise AssertionError("readdatavalid tidak naik satu siklus setelah read")
        return int(u.avm_readdata.value)

    async def read64(self, lo, hi):
        return (await self.read(hi)) << 32 | await self.read(lo)


async def boot(dut):
    dut.key.value = 0
    await Timer(200, "ns")
    dut.key.value = 0b11
    bus = Bus(dut)
    for _ in range(20):
        await FallingEdge(bus.clk)
    return bus


async def wait_status(bus, bit, timeout_us):
    for _ in range(int(timeout_us)):
        if (await bus.read("STATUS") >> bit) & 1:
            return True
        await Timer(1, "us")
    return False


async def inject_errors(dut, n, span_us):
    """Balik n bit di jumper, tersebar merata dalam span_us."""
    step = span_us / (n + 1)
    for _ in range(n):
        await us(step)
        await RisingEdge(dut.u_top.tx_clk)
        dut.inj.value = 1
        await RisingEdge(dut.u_top.tx_clk)
        dut.inj.value = 0
    await us(step)


async def run_mode(dut, bus, mode, run_us, inject=0):
    """Urutan run_mode dari ber_sweep.tcl; kembalikan dict kolom CSV."""
    await bus.write("CTRL", CTRL["CTRL_PHY_RST"])
    await Timer(1, "us")
    if mode == "raw":
        base = CTRL["CTRL_RAW"] | CTRL["CTRL_PHY_RST"]
        await bus.write("CTRL", base)
        assert await wait_status(bus, 5, 200), "raw_locked tidak naik"
        await bus.write("CTRL", base | CTRL["CTRL_CLEAR"])
        if inject:
            await inject_errors(dut, inject, run_us)
        else:
            await us(run_us)
        await bus.write("CTRL", base | CTRL["CTRL_SNAP"])
        st = await bus.read("STATUS")                   # sebelum RAW mati (raw_locked)
    else:
        await bus.write("CTRL", 0)
        assert await wait_status(bus, 1, 200), "rx_locked tidak naik"
        await bus.write("CTRL", CTRL["CTRL_CLEAR"])
        await bus.write("CTRL", CTRL["CTRL_PRBS_EN"])
        if inject:
            await inject_errors(dut, inject, run_us)
        else:
            await us(run_us)
        await bus.write("CTRL", 0)
        await us(2 * 69 * 10 * 1e6 / TX_HZ + 20)       # >= 2 frame + latensi FIFO
        await bus.write("CTRL", CTRL["CTRL_SNAP"])
        st = await bus.read("STATUS")
    r = dict(revision=f"sim_sel{TX_SEL}", mode=mode, tx_rate_khz=await bus.read("TX_RATE_KHZ"),
             seconds=run_us * 1e-6)
    r["sys_cycles"] = await bus.read64("SYS_CYC_LO", "SYS_CYC_HI")
    r["tx_cycles"] = await bus.read64("TX_CYC_LO", "TX_CYC_HI")
    r["tx_clk_hz"] = round(r["tx_cycles"] * 50e6 / r["sys_cycles"])
    for k, n in (("tx_frames", "TX_FRAMES"), ("rx_frames", "RX_FRAMES"),
                 ("rx_frames_bad", "RX_FRAMES_BAD"), ("bit_errors", "BIT_ERRORS"),
                 ("phy_ok", "PHY_OK"), ("phy_crc", "PHY_CRC"), ("phy_code", "PHY_CODE"),
                 ("phy_disp", "PHY_DISP"), ("phy_ctrl", "PHY_CTRL"), ("phy_frame", "PHY_FRAME"),
                 ("phy_lost", "PHY_LOST"), ("raw_loss", "RAW_LOSS")):
        r[k] = await bus.read(n)
    r["bits_checked"] = await bus.read64("BITS_CHK_LO", "BITS_CHK_HI")
    r["raw_bits"] = await bus.read64("RAW_BITS_LO", "RAW_BITS_HI")
    r["raw_errors"] = await bus.read64("RAW_ERR_LO", "RAW_ERR_HI")
    r["pll_locked"], r["rx_locked"], r["rx_overflow"] = st & 1, (st >> 1) & 1, (st >> 2) & 1
    r["raw_locked"] = (st >> 5) & 1
    r["timestamp"] = "sim"
    await bus.write("CTRL", 0)
    return r


def us(x):
    """Timer dengan durasi dibulatkan ke ns (Timer menolak pecahan di bawah presisi)."""
    return Timer(max(1, round(x * 1000)), "ns")


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in CSV_COLUMNS])


def run_ber(path):
    p = subprocess.run([sys.executable, os.path.join(REPO, "sw", "ber.py"), path, "--json",
                        path + ".json"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    with open(path + ".json") as f:
        return p.stdout, json.load(f)


@cocotb.test()
async def test_regmap(dut):
    """Register identitas, alamat tak dikenal, dan tabel Tcl = peta di RTL."""
    bus = await boot(dut)
    assert await bus.read("ID") == 0x5345474C
    assert await bus.read("VERSION") == 1
    assert await bus.read("TX_RATE_KHZ") == RATE_KHZ
    assert await bus.read(addr=0xFC) == 0xDEADBEEF
    await bus.write("CTRL", CTRL["CTRL_PRBS_EN"] | CTRL["CTRL_PHY_RST"])
    assert await bus.read("CTRL") == 3
    await bus.write("CTRL", 0)
    # Komentar peta register di RTL harus sama dengan tabel REG di skrip Tcl
    rtl = {m.group(2): int(m.group(1), 16)
           for m in re.finditer(r"(0x[0-9A-F]{2}) ([A-Z_]+)", open(RTL_REGS).read())}
    for name, addr in REG.items():
        assert rtl.get(name) == addr, f"{name}: Tcl {addr:#x}, RTL {rtl.get(name)}"
    dut._log.info("peta register Tcl = RTL (%d register), TX_RATE_KHZ = %d", len(REG), RATE_KHZ)


@cocotb.test()
async def test_prbs_clean(dut):
    """Satu putaran sweep tanpa galat: semua frame diterima utuh, laju tx_clk benar."""
    bus = await boot(dut)
    run_us = 12 * 69 * 10 * 1e6 / TX_HZ                       # ~12 frame
    r = await run_mode(dut, bus, "framed", run_us)
    assert r["tx_frames"] >= 8, r
    assert r["rx_frames"] == r["tx_frames"], r
    assert r["rx_frames_bad"] == 0 and r["bit_errors"] == 0, r
    assert r["bits_checked"] == r["rx_frames"] * PAYLOAD_PRBS * 8, r
    assert r["phy_ok"] == r["rx_frames"], r
    assert all(r[k] == 0 for k in ("phy_crc", "phy_code", "phy_disp", "phy_ctrl",
                                   "phy_frame", "phy_lost")), r
    assert r["pll_locked"] and r["rx_locked"] and not r["rx_overflow"], r
    assert abs(r["tx_clk_hz"] - TX_HZ) / TX_HZ < 0.01, (r["tx_clk_hz"], TX_HZ)
    path = os.path.abspath(f"ber_sim_sel{TX_SEL}_clean.csv")
    write_csv([r], path)
    out, res = run_ber(path)
    assert res[0]["ber"] == 0 and not res[0]["warnings"], res
    dut._log.info("\n%s", out)


@cocotb.test()
async def test_prbs_errors(dut):
    """Galat bit di jumper terdeteksi oleh checker PRBS dan counter phy."""
    bus = await boot(dut)
    run_us = 20 * 69 * 10 * 1e6 / TX_HZ
    n_inj = 6
    r = await run_mode(dut, bus, "framed", run_us, inject=n_inj)
    phy_flags = sum(r[k] for k in ("phy_crc", "phy_code", "phy_disp", "phy_ctrl", "phy_frame"))
    assert phy_flags > 0, r
    assert r["rx_frames_bad"] > 0 or r["bit_errors"] > 0, r
    # Frame OK menurut phy = frame tanpa tanda menurut checker
    assert r["phy_ok"] == r["rx_frames"] - r["rx_frames_bad"], r
    path = os.path.abspath(f"ber_sim_sel{TX_SEL}_errors.csv")
    write_csv([r], path)
    out, res = run_ber(path)
    assert res[0]["frame_error_ratio"] > 0, res
    dut._log.info("%d galat diinjeksi -> %s\n%s", n_inj,
                  {k: r[k] for k in ("rx_frames", "rx_frames_bad", "bit_errors", "phy_crc",
                                     "phy_code", "phy_disp", "phy_frame")}, out)


@cocotb.test()
async def test_raw_ber(dut):
    """Mode RAW: BER kanal dihitung tepat (satu hitungan per bit salah)."""
    bus = await boot(dut)
    run_us = 8000 * 1e6 / TX_HZ                                # ~8000 bit
    clean = await run_mode(dut, bus, "raw", run_us)
    assert clean["raw_locked"] and clean["raw_errors"] == 0 and clean["raw_loss"] == 0, clean
    assert abs(clean["raw_bits"] - clean["tx_cycles"]) <= 64, clean     # semua bit dibandingkan
    assert clean["phy_ok"] == 0 and clean["phy_code"] == 0, clean        # phy ditahan reset
    n_inj = 7
    bad = await run_mode(dut, bus, "raw", run_us, inject=n_inj)
    assert bad["raw_errors"] == n_inj and bad["raw_loss"] == 0, bad
    path = os.path.abspath(f"ber_sim_sel{TX_SEL}_raw.csv")
    write_csv([clean, bad], path)
    out, res = run_ber(path)
    assert res[0]["ber"] == 0 and res[1]["bit_errors"] == n_inj, res
    assert abs(res[1]["ber"] - n_inj / bad["raw_bits"]) < 1e-15, res
    dut._log.info("RAW: %d bit tanpa galat; %d galat diinjeksi -> %d bit salah dari %d\n%s",
                  clean["raw_bits"], n_inj, bad["raw_errors"], bad["raw_bits"], out)
