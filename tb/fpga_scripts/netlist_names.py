"""Nama register top FPGA dengan format nama Quartus (entity:instance|...|reg[i]).

Elaborasi Yosys (hierarki dipertahankan, tanpa optimasi yang mengganti nama), lalu
setiap bit Q flop dan setiap bit memori dpram diberi nama seperti di Quartus:
  phy:u_phy|cdc_fifo:u_tx_fifo|cdc_fifo_write_state:writestate|write_pointer_gray[0]
Memori (AUTO_RAM_RECOGNITION OFF di QSF) dinamai memory[word][bit].
Ini PENDEKATAN konvensi nama Quartus; nama sebenarnya harus diperiksa lewat laporan
Ignored Constraints dan pesan "SEGEL SDC" (docs/phy_howto.md).

  python3 netlist_names.py <keluaran.txt>
"""

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FPGA = os.path.join(REPO, "fpga", "phy_loopback", "rtl")
PHY = os.path.join(REPO, "rtl", "phy")
CDC = os.path.join(REPO, "rtl", "cdc_fifo")
SOURCES = [os.path.join(PHY, f) for f in (
    "enc8b10b.v", "dec8b10b.v", "phy_serializer.v", "phy_deserializer.v", "phy_comma_align.v",
    "phy_framer.v", "phy_deframer.v", "phy.v")] + [os.path.join(REPO, "rtl", "crc8", "crc8.v")] + \
    [os.path.join(CDC, f) for f in (
        "cdc_fifo.sv", "dpram.sv", "cdc_fifo_read_state.sv", "cdc_fifo_write_state.sv",
        "binary_to_gray.sv", "gray_to_binary.sv", "synchronizer.sv", "reset_synchronizer.sv")] + \
    [os.path.join(FPGA, f) for f in (
        "prbs_framegen.v", "prbs_checker.v", "cdc_event_counter.v", "prbs_raw.v",
        "loopback_regs.v", "pll_tx.v", "fwd_clk_out.v", "de10nano_phy_loopback.v")]
FF_TYPES = ("$dff", "$adff", "$dffe", "$adffe", "$sdff", "$sdffe", "$aldff", "$dffsr", "$dffsre")


def elaborate():
    out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    script = (f"read_verilog -lib {os.path.join(os.path.dirname(__file__), 'intel_blackbox.v')}; "
              f"read_verilog -sv -I{PHY} -I{FPGA} {' '.join(SOURCES)}; "
              "hierarchy -top de10nano_phy_loopback; proc; opt_dff -nodffe -nosdff; "
              f"write_json {out}")
    subprocess.run(["yosys", "-q", "-p", script], check=True)
    with open(out) as f:
        d = json.load(f)
    os.unlink(out)
    return d["modules"]


def entity(mod_name):
    # Yosys memberi nama modul berparameter seperti "$paramod\\cdc_fifo\\DATA_WIDTH=..."
    if mod_name.startswith("$paramod"):
        return mod_name.split("\\")[1]
    return mod_name.lstrip("\\")


def names(mods, mod, prefix, out):
    m = mods[mod]
    bitname = {}
    for net, info in m["netnames"].items():
        if net.startswith("$"):
            continue
        for i, b in enumerate(info["bits"]):
            if isinstance(b, int) and (b not in bitname or info.get("hide_name", 0) == 0):
                w = len(info["bits"])
                off = info.get("offset", 0)
                bitname[b] = f"{net}[{i + off}]" if w > 1 or info.get("upto") else net
    for memid, info in m.get("memories", {}).items():      # memori tanpa memory_collect
        for w in range(info["size"]):
            for b in range(info["width"]):
                out.append(f"{prefix}{memid.lstrip(chr(92))}[{w + info.get('start_offset', 0)}][{b}]")
    for cname, c in m["cells"].items():
        t = c["type"]
        if t in FF_TYPES:
            for b in c["connections"]["Q"]:
                if isinstance(b, int) and b in bitname:
                    out.append(prefix + bitname[b])
        elif t in ("$mem", "$mem_v2"):
            memid = c["parameters"]["MEMID"].lstrip("\\")
            words, width = int(c["parameters"]["SIZE"], 2), int(c["parameters"]["WIDTH"], 2)
            for w in range(words):
                for b in range(width):
                    out.append(f"{prefix}{memid}[{w}][{b}]")
        elif t in mods:
            inst = cname.lstrip("\\")
            names(mods, t, f"{prefix}{entity(t)}:{inst}|", out)


def main():
    mods = elaborate()
    out = []
    names(mods, "de10nano_phy_loopback", "", out)
    with open(sys.argv[1], "w") as f:
        f.write("\n".join(sorted(set(out))) + "\n")
    print(f"{len(set(out))} register")


if __name__ == "__main__":
    main()
