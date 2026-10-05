"""Pemeriksaan struktur CDC FIFO setelah sintesis Yosys.

Mensintesis `cdc_fifo` (`synth -flatten`, gerbang generik), lalu memeriksa:

  --gray   F5: setiap bit masukan D flop tingkat pertama di kedua synchronizer
           pointer digerakkan LANGSUNG oleh keluaran Q flop yang di-clock domain
           sumber, tanpa gerbang di antaranya (kalau ada gerbang, mis. XOR dari
           binary_to_gray, pointer yang menyeberang domain bisa glitch).
  --reset  setiap flop ber-reset asinkron (selain flop reset synchronizer itu
           sendiri) menerima reset dari keluaran reset synchronizer yang
           di-clock domain yang sama, sehingga reset dilepas sinkron ke clock
           flop itu (tidak ada pelanggaran recovery/removal).

  python3 check_cdc_regs.py --src rtl/cdc_fifo --gray registered --reset synced
  python3 check_cdc_regs.py --src rtl/baseline/cdc_fifo_0036/src \\
      --gray combinational --reset unsynced                       # audit baseline

Keluar 0 kalau semua hasil sesuai harapan yang diminta, 1 kalau tidak.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

FILES = ["cdc_fifo.sv", "dpram.sv", "cdc_fifo_read_state.sv", "cdc_fifo_write_state.sv",
         "binary_to_gray.sv", "gray_to_binary.sv", "synchronizer.sv",
         "reset_synchronizer.sv"]  # yang terakhir hanya ada di salinan SEGEL
# synchronizer pointer -> (net clock tujuan, net clock sumber)
SYNCS = {"write_address_sync": ("read_clock", "write_clock"),
         "read_address_sync": ("write_clock", "read_clock")}
# domain clock -> instance reset synchronizer-nya
RESET_SYNCS = {"write_clock": "write_reset_synchronizer",
               "read_clock": "read_reset_synchronizer"}


def synth(src, data_w, addr_w):
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    files = " ".join(os.path.join(src, f) for f in FILES if os.path.exists(os.path.join(src, f)))
    script = (f"read_verilog -sv {files}; "
              f"chparam -set DATA_WIDTH {data_w} -set ADDRESS_WIDTH {addr_w} cdc_fifo; "
              f"synth -flatten -top cdc_fifo; opt_clean; write_json {out}")
    subprocess.run(["yosys", "-q", "-p", script], check=True)
    with open(out) as f:
        mod = json.load(f)["modules"]["cdc_fifo"]
    os.unlink(out)
    return mod


def is_ff(cell):
    return cell["type"].startswith(("$_DFF", "$_SDFF", "$_DFFE", "$_ALDFF", "$dff", "$adff"))


class Netlist:
    def __init__(self, mod):
        self.mod = mod
        self.cells = mod["cells"]
        self.nets = mod["netnames"]
        self.drivers = {}  # bit -> (nama cell, port)
        for name, c in self.cells.items():
            for port, bits in c["connections"].items():
                if c["port_directions"].get(port) == "output":
                    for b in bits:
                        if isinstance(b, int):
                            self.drivers[b] = (name, port)

    def aliases(self, bit):
        return {n for n, info in self.nets.items() if bit in info["bits"]}

    def clock_nets(self, cell):
        return self.aliases(cell["connections"]["C"][0])

    def bits(self, net):
        return set(self.nets[net]["bits"]) if net in self.nets else set()


def check_gray(nl):
    """[(nama, ok, keterangan)] untuk setiap bit synchronizer pointer."""
    res = []
    for sync, (dst_clk, src_clk) in SYNCS.items():
        for i, qbit in enumerate(nl.nets[f"{sync}.data"]["bits"]):
            ff = nl.cells[nl.drivers[qbit][0]]
            assert is_ff(ff), f"{sync}.data[{i}] tidak digerakkan flop"
            src = nl.drivers.get(ff["connections"]["D"][0])
            if src is None:
                res.append((f"{sync}.data[{i}]", False, "konstanta/input"))
                continue
            scell = nl.cells[src[0]]
            ok = (is_ff(scell) and src[1] == "Q" and src_clk in nl.clock_nets(scell)
                  and dst_clk in nl.clock_nets(ff))
            res.append((f"{sync}.data[{i}]", ok, f"{scell['type']}.{src[1]}"))
    return res


def check_reset(nl):
    """[(nama, ok, keterangan)] untuk setiap flop ber-reset asinkron."""
    sync_q = {b for inst in RESET_SYNCS.values() for b in nl.bits(f"{inst}.sync")}
    res = []
    for name, c in sorted(nl.cells.items()):
        if not is_ff(c) or "R" not in c["connections"]:
            continue
        q = c["connections"]["Q"][0]
        if q in sync_q:
            continue  # flop reset synchronizer itu sendiri
        label = sorted(n for n in nl.aliases(q) if not n.startswith("$"))
        label = label[0] if label else name
        clks = nl.clock_nets(c) & set(RESET_SYNCS)
        if len(clks) != 1:
            res.append((label, False, "clock bukan write_clock/read_clock"))
            continue
        domain = clks.pop()
        rdrv = nl.drivers.get(c["connections"]["R"][0])
        if rdrv is None:
            res.append((label, False, f"{domain}: reset langsung dari input"))
            continue
        rcell = nl.cells[rdrv[0]]
        out_bits = nl.bits(f"{RESET_SYNCS[domain]}.reset_out")
        ok = (is_ff(rcell) and rdrv[1] == "Q" and c["connections"]["R"][0] in out_bits
              and domain in nl.clock_nets(rcell))
        res.append((label, ok, f"{domain}: reset dari {rcell['type']}.{rdrv[1]}"))
    return res


def report(title, res, verbose):
    n_ok = sum(ok for _, ok, _ in res)
    if verbose:
        for name, ok, why in res:
            print(f"  {name:40s} {why:42s} {'OK' if ok else 'TIDAK'}")
    print(f"{title}: {n_ok}/{len(res)} OK")
    return n_ok, len(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--gray", choices=["registered", "combinational"])
    ap.add_argument("--reset", choices=["synced", "unsynced"])
    ap.add_argument("--data-width", type=int, default=4)
    ap.add_argument("--address-width", type=int, default=5)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if not (a.gray or a.reset):
        ap.error("minimal satu dari --gray / --reset")

    nl = Netlist(synth(a.src, a.data_width, a.address_width))
    good = True
    if a.gray:
        ok, n = report("gray: bit synchronizer langsung dari flop domain sumber",
                       check_gray(nl), a.verbose)
        hit = ok == n if a.gray == "registered" else ok < n
        print(("PASS" if hit else "FAIL") + f" struct gray ({a.gray})")
        good &= hit
    if a.reset:
        ok, n = report("reset: flop ber-reset dengan reset tersinkron ke domainnya",
                       check_reset(nl), a.verbose)
        hit = (ok == n and n > 0) if a.reset == "synced" else ok == 0
        print(("PASS" if hit else "FAIL") + f" struct reset ({a.reset})")
        good &= hit
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
