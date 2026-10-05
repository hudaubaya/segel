"""Pemeriksaan struktur F5 (docs/baseline_audit.md) untuk CDC FIFO.

Mensintesis `cdc_fifo` dengan Yosys (`synth -flatten`, gerbang generik), lalu
untuk setiap flop tingkat pertama di kedua synchronizer memeriksa bahwa
setiap bit masukan D digerakkan LANGSUNG oleh keluaran Q sebuah flop yang
di-clock oleh domain sumber, tanpa gerbang di antaranya. Kalau ada gerbang
(mis. XOR dari binary_to_gray), pointer yang menyeberang domain bisa glitch.

  python3 check_cdc_regs.py --src DIR --expect registered     # harus registered
  python3 check_cdc_regs.py --src DIR --expect combinational  # audit baseline

Keluar 0 kalau hasil sesuai --expect, 1 kalau tidak.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

FILES = ["cdc_fifo.sv", "dpram.sv", "cdc_fifo_read_state.sv", "cdc_fifo_write_state.sv",
         "binary_to_gray.sv", "gray_to_binary.sv", "synchronizer.sv"]
# synchronizer -> (net clock tujuan, net clock sumber)
SYNCS = {"write_address_sync": ("read_clock", "write_clock"),
         "read_address_sync": ("write_clock", "read_clock")}


def synth(src, data_w, addr_w):
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    files = " ".join(os.path.join(src, f) for f in FILES)
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


def analyse(mod):
    nets = mod["netnames"]
    drivers = {}  # bit -> (nama cell, port)
    for name, c in mod["cells"].items():
        for port, bits in c["connections"].items():
            if c["port_directions"].get(port) == "output":
                for b in bits:
                    if isinstance(b, int):
                        drivers[b] = (name, port)

    def clock_nets(cell):
        """Semua nama net (alias) yang tersambung ke pin clock flop."""
        bit = cell["connections"]["C"][0]
        return {n for n, info in nets.items() if bit in info["bits"]}

    results = []
    for sync, (dst_clk, src_clk) in SYNCS.items():
        stage1 = nets[f"{sync}.data"]["bits"]
        for i, qbit in enumerate(stage1):
            ff_name, _ = drivers[qbit]
            ff = mod["cells"][ff_name]
            assert is_ff(ff), f"{sync}.data[{i}] tidak digerakkan flop"
            dbit = ff["connections"]["D"][0]
            src = drivers.get(dbit)
            if src is None:
                results.append((sync, i, "konstanta/input", False))
                continue
            sname, sport = src
            scell = mod["cells"][sname]
            ok = is_ff(scell) and sport == "Q"
            if ok:
                ok = src_clk in clock_nets(scell) and dst_clk in clock_nets(ff)
            results.append((sync, i, f"{scell['type']}.{sport}", ok))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--expect", choices=["registered", "combinational"], required=True)
    ap.add_argument("--data-width", type=int, default=4)
    ap.add_argument("--address-width", type=int, default=5)
    a = ap.parse_args()

    res = analyse(synth(a.src, a.data_width, a.address_width))
    for sync, i, drv, ok in res:
        print(f"  {sync}.data[{i}] <- {drv:24s} {'flop sumber' if ok else 'BUKAN flop langsung'}")
    registered = all(ok for *_, ok in res)
    n_bad = sum(not ok for *_, ok in res)
    print(f"{len(res) - n_bad}/{len(res)} bit synchronizer digerakkan langsung oleh flop domain sumber")
    good = registered if a.expect == "registered" else not registered
    print(("PASS" if good else "FAIL") + f" struct ({a.expect})")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
