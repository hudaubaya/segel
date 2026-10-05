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
  python3 check_cdc_regs.py --src rtl/cdc_fifo --target cyclonev \\
      --gray registered --reset synced                          # netlist Cyclone V
  python3 check_cdc_regs.py --src rtl/baseline/cdc_fifo_0036/src \\
      --gray combinational --reset unsynced                       # audit baseline

--target generic  : `synth -flatten`, gerbang generik Yosys ($_DFF_*, pin R aktif tinggi)
--target cyclonev : `synth_intel_alm -family cyclonev -noiopad -noclkbuf`
                    (MISTRAL_FF, pin ACLR aktif rendah). Flop reset synchronizer
                    dikenali sebagai flop yang ACLR-nya tidak berasal dari flop;
                    jumlahnya harus tepat 2 per domain clock.

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


# Per target: perintah sintesis, nama port flop (D, clock, reset async, Q),
# dan apakah reset async-nya aktif rendah.
TARGETS = {
    "generic": dict(synth="synth -flatten -top cdc_fifo; opt_clean",
                    d="D", c="C", r="R", q="Q"),
    "cyclonev": dict(synth="synth_intel_alm -family cyclonev -noiopad -noclkbuf -top cdc_fifo",
                     d="DATAIN", c="CLK", r="ACLR", q="Q"),
}


def synth(src, data_w, addr_w, target="generic"):
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    files = " ".join(os.path.join(src, f) for f in FILES if os.path.exists(os.path.join(src, f)))
    script = (f"read_verilog -sv {files}; "
              f"chparam -set DATA_WIDTH {data_w} -set ADDRESS_WIDTH {addr_w} cdc_fifo; "
              f"{TARGETS[target]['synth']}; write_json {out}")
    subprocess.run(["yosys", "-q", "-p", script], check=True)
    with open(out) as f:
        mod = json.load(f)["modules"]["cdc_fifo"]
    os.unlink(out)
    return mod


def is_ff(cell):
    return cell["type"].startswith(("$_DFF", "$_SDFF", "$_DFFE", "$_ALDFF", "$dff", "$adff",
                                    "MISTRAL_FF"))


class Netlist:
    def __init__(self, mod, target="generic"):
        self.mod = mod
        t = TARGETS[target]
        self.D, self.C, self.R, self.Q = t["d"], t["c"], t["r"], t["q"]
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
        return self.aliases(cell["connections"][self.C][0])

    def async_reset_bit(self, cell):
        """Bit pin reset async, atau None kalau flop tidak punya reset async."""
        b = cell["connections"].get(self.R, [None])[0]
        return b if isinstance(b, int) else None  # konstanta '0'/'1' = tanpa reset

    def bits(self, net):
        return set(self.nets[net]["bits"]) if net in self.nets else set()


def check_gray(nl):
    """[(nama, ok, keterangan)] untuk setiap bit synchronizer pointer."""
    res = []
    for sync, (dst_clk, src_clk) in SYNCS.items():
        for i, qbit in enumerate(nl.nets[f"{sync}.data"]["bits"]):
            ff = nl.cells[nl.drivers[qbit][0]]
            assert is_ff(ff), f"{sync}.data[{i}] tidak digerakkan flop"
            src = nl.drivers.get(ff["connections"][nl.D][0])
            if src is None:
                res.append((f"{sync}.data[{i}]", False, "konstanta/input"))
                continue
            scell = nl.cells[src[0]]
            ok = (is_ff(scell) and src[1] == nl.Q and src_clk in nl.clock_nets(scell)
                  and dst_clk in nl.clock_nets(ff))
            res.append((f"{sync}.data[{i}]", ok, f"{scell['type']}.{src[1]}"))
    return res


def check_reset(nl):
    """[(nama, ok, keterangan)] untuk setiap flop ber-reset asinkron."""
    # Flop reset synchronizer: generic dikenali dari nama net; cyclonev dari
    # strukturnya (ACLR tidak berasal dari flop), karena Yosys membalik polaritas
    # flop set menjadi flop clear sehingga nama net-nya tidak lagi menempel.
    sync_q = {b for inst in RESET_SYNCS.values() for b in nl.bits(f"{inst}.sync")}
    res, sync_ffs = [], {}
    for name, c in sorted(nl.cells.items()):
        if not is_ff(c):
            continue
        rbit = nl.async_reset_bit(c)
        if rbit is None:
            continue
        q = c["connections"][nl.Q][0]
        clks = nl.clock_nets(c) & set(RESET_SYNCS)
        domain = clks.pop() if len(clks) == 1 else None
        rdrv = nl.drivers.get(rbit)
        rcell = nl.cells[rdrv[0]] if rdrv else None
        from_ff = rcell is not None and is_ff(rcell) and rdrv[1] == nl.Q
        if q in sync_q or (nl.R == "ACLR" and not from_ff):
            sync_ffs.setdefault(domain, []).append(name)
            continue  # flop reset synchronizer itu sendiri
        label = sorted(n for n in nl.aliases(q) if not n.startswith("$"))
        label = label[0] if label else name
        if domain is None:
            res.append((label, False, "clock bukan write_clock/read_clock"))
            continue
        if rdrv is None:
            res.append((label, False, f"{domain}: reset langsung dari input"))
            continue
        if nl.R == "ACLR":
            ok = from_ff and domain in nl.clock_nets(rcell)
        else:
            out_bits = nl.bits(f"{RESET_SYNCS[domain]}.reset_out")
            ok = from_ff and rbit in out_bits and domain in nl.clock_nets(rcell)
        res.append((label, ok, f"{domain}: reset dari {rcell['type']}.{rdrv[1]}"))
    if nl.R == "ACLR":
        # Tepat 2 flop synchronizer per domain; lebih berarti ada flop fungsional
        # yang menerima reset mentah dari pin.
        for domain in RESET_SYNCS:
            n = len(sync_ffs.get(domain, []))
            res.append((f"reset synchronizer {domain}", n == 2, f"{n} flop (harus 2)"))
        stray = sync_ffs.get(None, [])
        if stray:
            res.append(("flop tanpa domain", False, f"{len(stray)} flop"))
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
    ap.add_argument("--target", choices=sorted(TARGETS), default="generic")
    ap.add_argument("--gray", choices=["registered", "combinational"])
    ap.add_argument("--reset", choices=["synced", "unsynced"])
    ap.add_argument("--data-width", type=int, default=4)
    ap.add_argument("--address-width", type=int, default=5)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if not (a.gray or a.reset):
        ap.error("minimal satu dari --gray / --reset")

    nl = Netlist(synth(a.src, a.data_width, a.address_width, a.target), a.target)
    print(f"target: {a.target}")
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
