"""Uji skrip FPGA tanpa Quartus/System Console/papan (tclsh + mock).

  python3 tb/fpga_scripts/run_tests.py        (dari root; `make test-fpga-scripts`)

1. phy_loopback.sdc di bawah mock Timing Analyzer, untuk keempat periode tx_clk, terhadap
   nama register hasil elaborasi Yosys top FPGA (netlist_names.py): tanpa error Tcl,
   tanpa pesan "SEGEL SDC", setiap pola cocok dengan jumlah bit yang diharapkan.
2. create_project.tcl di bawah mock ::quartus::project: 4 revisi dengan TX_SEL 0..3,
   setiap port top punya pin + IO_STANDARD, pin unik, sama dengan tabel Intel, pin
   PHY_RX_CLK adalah input clock khusus, semua file sumber ada.
3. ber_sweep.tcl di bawah mock System Console: urutan unduh/mode, CSV lengkap, lalu
   sw/ber.py membacanya.
4. build_all.sh dengan perintah Quartus palsu: urutan langkah dan direktori kerja.
Keluar 0 kalau semua lulus.
"""

import csv
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FPGA = os.path.join(REPO, "fpga", "phy_loopback")
TMP = tempfile.mkdtemp(prefix="segel_fpga_scripts_")

# Pin DE10-Nano dari intel/de10-nano-hardware @9b5fc81
# (scripts/create_quartus_de10-nano-base.tcl, MIT).
INTEL_PINS = {
    "FPGA_CLK1_50": "V11", "KEY[0]": "AH17", "KEY[1]": "AH16",
    "LED[0]": "W15", "LED[1]": "AA24", "LED[2]": "V16", "LED[3]": "V15", "LED[4]": "AF26",
    "LED[5]": "AE26", "LED[6]": "Y16", "LED[7]": "AA23",
    "PHY_RX_CLK": "Y15",   # gpio_1[0]
    "PHY_RX_DAT": "AG28",  # gpio_1[4]
    "PHY_TX_CLK": "AF28",  # gpio_1[5]
    "PHY_TX_DAT": "AF27",  # gpio_1[7]
}
# Bola U23 yang terhubung ke input clock khusus (CLKPIN/NCLKPIN), dari basis data
# Mistral (Ravenslofty/mistral @d509238, data/sx120f-p2p.txt + sx120f-pkg.txt).
CLOCK_PINS = {"AA13", "AA15", "C12", "D11", "D12", "E11", "V11", "V12", "W11", "W12", "W20",
              "W21", "W24", "Y13", "Y15", "Y24"}
TX_PERIODS = {0: 200.404, 1: 100.202, 2: 50.101, 3: 40.404}
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("  GAGAL:", msg)


def tclsh(script, env):
    p = subprocess.run(["tclsh", os.path.join(HERE, script)], env=dict(os.environ, **env),
                       capture_output=True, text=True)
    if p.returncode:
        print(p.stdout, p.stderr)
    return p


def test_sdc():
    print("== SDC (mock Timing Analyzer)")
    regs = os.path.join(TMP, "regs.txt")
    subprocess.run([sys.executable, os.path.join(HERE, "netlist_names.py"), regs], check=True,
                   capture_output=True)
    for sel, period in TX_PERIODS.items():
        log = os.path.join(TMP, f"sta_{sel}.log")
        p = tclsh("mock_sta.tcl", dict(SEGEL_LOG=log, SEGEL_REGS=regs, SEGEL_TX_PERIOD=str(period),
                                       SEGEL_SDC=os.path.join(FPGA, "quartus", "phy_loopback.sdc")))
        check(p.returncode == 0, f"TX_SEL {sel}: error Tcl {p.stderr.strip()[-200:]}")
        rows = [l.rstrip("\n").split("\t") for l in open(log)]
        msgs = [r for r in rows if r[0] == "post_message" and r[1] != "info"]
        check(not msgs, f"TX_SEL {sel}: {msgs}")
        clocks = {r[1]: r for r in rows if r[0] == "create_clock"}
        check(float(clocks["rx_clk"][2]) == period and clocks["rx_clk"][3] == f"{period / 2} {period}",
              f"rx_clk {clocks.get('rx_clk')}")
        check("rx_virt" in clocks and clocks["rx_virt"][4] == "0", "rx_virt harus virtual")
        check(any(r[0] == "create_generated_clock" and r[1] == "tx_fwd_clk" and r[2] == "1"
                  for r in rows), "tx_fwd_clk -invert")
        skews = [r for r in rows if r[0] == "set_max_skew"]
        sizes = sorted((int(r[2]), int(r[3])) for r in skews)
        check(sizes == [(6, 6)] * 4 + [(8, 8)] * 4, f"bus Gray max_skew {sizes}")
        mems = [r for r in rows if r[0] == "set_max_delay" and r[3] == "0"]
        check([int(r[2]) for r in mems] == [288, 288], f"memori FIFO {mems}")
        check(abs(float(mems[0][4]) - period) < 1e-9 and float(mems[1][4]) == 20.0,
              f"batas memori {mems}")
        to_sync = [int(r[3]) for r in rows if r[0] == "set_false_path" and r[2] == "0"]
        check(to_sync[-4:] == [2, 2, 1, 1], f"synchronizer level {to_sync}")
        io = [r for r in rows if r[0] in ("set_input_delay", "set_output_delay")]
        phy_io = [r for r in io if r[1] in ("rx_virt", "tx_fwd_clk")]
        check(len(phy_io) == 4 and all(r[3] == "1" for r in phy_io), f"I/O delay PHY {phy_io}")
        check(sorted(int(r[3]) for r in io if r[1] == "clk50") == [2, 8], f"I/O KEY/LED {io}")
    print(f"  4 periode tx_clk, {sum(1 for _ in open(regs))} nama register")


def test_project():
    print("== create_project.tcl (mock ::quartus::project)")
    log = os.path.join(TMP, "proj.log")
    p = tclsh("mock_quartus_project.tcl",
              dict(SEGEL_LOG=log, SEGEL_SCRIPT=os.path.join(FPGA, "quartus", "create_project.tcl")))
    check(p.returncode == 0, f"error Tcl {p.stderr.strip()[-300:]}")
    rows = [l.rstrip("\n").split("\t") for l in open(log)]
    revs = {}
    for rev, kind, name, val, tgt in rows:
        revs.setdefault(rev, []).append((kind, name, val, tgt))
    check(sorted(revs) == ["phy_loopback_r05", "phy_loopback_r10", "phy_loopback_r20",
                           "phy_loopback_r25"], f"revisi {sorted(revs)}")
    top = open(os.path.join(FPGA, "rtl", "de10nano_phy_loopback.v")).read()
    ports = []
    for m in re.finditer(r"^\s*(input|output)\s+wire\s*(\[(\d+):0\])?\s*(\w+)", top, re.M):
        ports += [f"{m.group(4)}[{i}]" for i in range(int(m.group(3)) + 1)] if m.group(2) \
            else [m.group(4)]
    for sel, rev in enumerate(sorted(revs)):
        a = revs[rev]
        loc = {t: v for k, n, v, t in a if k == "location"}
        iostd = {t for k, n, v, t in a if k == "instance" and n == "IO_STANDARD"}
        check([v for k, n, v, t in a if k == "parameter" and n == "TX_SEL"] == [str(sel)],
              f"{rev}: TX_SEL")
        check(set(loc) == set(ports), f"{rev}: port tanpa pin {set(ports) ^ set(loc)}")
        check(iostd == set(ports), f"{rev}: port tanpa IO_STANDARD {set(ports) ^ iostd}")
        check(len(set(loc.values())) == len(loc), f"{rev}: pin dobel")
        check({k: f"PIN_{v}" for k, v in INTEL_PINS.items()} == loc, f"{rev}: pin beda dari tabel")
        files = [v for k, n, v, t in a if k == "global" and n in ("VERILOG_FILE", "SYSTEMVERILOG_FILE")]
        qdir = os.path.join(FPGA, "quartus")
        missing = [f for f in files if not os.path.exists(os.path.join(qdir, f))]
        check(not missing, f"{rev}: file tidak ada {missing}")
        glob = {n: v for k, n, v, t in a if k == "global"}
        check(glob.get("SDC_FILE") == "phy_loopback.sdc" and "QIP_FILE" in glob, f"{rev}: SDC/QIP")
        check(glob.get("AUTO_RAM_RECOGNITION") == "OFF", f"{rev}: AUTO_RAM_RECOGNITION")
        fast = {(n, t) for k, n, v, t in a if k == "instance" and v == "ON"}
        check({("FAST_OUTPUT_REGISTER", "PHY_TX_DAT"), ("FAST_INPUT_REGISTER", "PHY_RX_DAT")} <= fast,
              f"{rev}: register I/O")
    check(INTEL_PINS["PHY_RX_CLK"] in CLOCK_PINS, "PHY_RX_CLK bukan input clock khusus")
    check(INTEL_PINS["FPGA_CLK1_50"] in CLOCK_PINS, "FPGA_CLK1_50 bukan input clock khusus")
    print(f"  {len(revs)} revisi, {len(ports)} port")


def test_sweep():
    print("== ber_sweep.tcl (mock System Console)")
    out_csv = os.path.join(TMP, "sweep.csv")
    ops = os.path.join(TMP, "ops.txt")
    sof_dir = os.path.join(TMP, "sof")
    os.makedirs(sof_dir, exist_ok=True)
    for r in ("r05", "r10", "r20", "r25"):
        open(os.path.join(sof_dir, f"phy_loopback_{r}.sof"), "w").close()
    p = tclsh("mock_system_console.tcl", dict(
        SEGEL_SCRIPT=os.path.join(FPGA, "scripts", "ber_sweep.tcl"), SEGEL_OPS=ops,
        SEGEL_ARGS=f"-- detik=2 csv={out_csv} sof_dir={sof_dir}", SEGEL_RAW_ERR="3",
        SEGEL_BAD_FRAMES="1"))
    check(p.returncode == 0, f"error Tcl {p.stderr.strip()[-300:]}")
    o = dict(l.split(" ", 1) for l in open(ops).read().splitlines())
    check(o["downloads"].split() == ["r05", "r10", "r20", "r25"], f"unduhan {o['downloads']}")
    rows = list(csv.DictReader(open(out_csv)))
    check([(r["revision"], r["mode"]) for r in rows] ==
          [(rv, m) for rv in ("r05", "r10", "r20", "r25") for m in ("raw", "framed")],
          "urutan baris CSV")
    khz = {"r05": 4990, "r10": 9980, "r20": 19960, "r25": 24750}
    for r in rows:
        check(int(r["tx_rate_khz"]) == khz[r["revision"]], f"{r['revision']}: kHz")
        if r["mode"] == "raw":
            check(int(r["raw_bits"]) == round(2 * khz[r["revision"]] * 1000) and
                  int(r["raw_errors"]) == 3 and r["raw_locked"] == "1", f"raw {r}")
        else:
            check(int(r["rx_frames"]) > 0 and int(r["rx_frames_bad"]) == 1, f"framed {r}")
    js = os.path.join(TMP, "ber.json")
    p = subprocess.run([sys.executable, os.path.join(REPO, "sw", "ber.py"), out_csv, "--json", js],
                       capture_output=True, text=True)
    check(p.returncode == 0, f"ber.py {p.stderr}")
    res = json.load(open(js))
    raw = [x for x in res if x["mode"] == "raw"]
    check(all(abs(x["ber"] - 3 / x["bits"]) < 1e-18 for x in raw), "BER raw")
    print(p.stdout)


def test_build_script():
    print("== build_all.sh (perintah Quartus palsu)")
    bindir = os.path.join(TMP, "bin")
    os.makedirs(bindir, exist_ok=True)
    log = os.path.join(TMP, "build.log")
    for tool in ("qsys-script", "qsys-generate", "quartus_sh", "quartus_sta"):
        path = os.path.join(bindir, tool)
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\necho "$(basename "$PWD") {tool} $*" >> {log}\n')
        os.chmod(path, 0o755)
    p = subprocess.run([os.path.join(FPGA, "scripts", "build_all.sh"), "r05", "r25"],
                       env=dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"]),
                       capture_output=True, text=True)
    check(p.returncode == 0, f"build_all.sh {p.stderr}")
    got = open(log).read().splitlines()
    exp = ["qsys qsys-script --script=make_phy_jtag.tcl",
           "qsys qsys-generate phy_jtag.qsys --synthesis=VERILOG --output-directory=phy_jtag",
           "quartus quartus_sh -t create_project.tcl"]
    for r in ("r05", "r25"):
        exp += [f"quartus quartus_sh --flow compile phy_loopback -c phy_loopback_{r}",
                f"quartus quartus_sta -t ../scripts/sta_checks.tcl phy_loopback phy_loopback_{r}"]
    check(got == exp, f"urutan build {got}")
    print(f"  {len(got)} langkah")


def main():
    test_sdc()
    test_project()
    test_sweep()
    test_build_script()
    print(("PASS" if not fails else f"FAIL ({len(fails)})") + " skrip FPGA (mock)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
