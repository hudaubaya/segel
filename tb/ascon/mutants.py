"""Uji mutasi rtl/ascon_core.v: setiap mutan HARUS membuat test gagal.

  python3 tb/ascon/mutants.py            (dari root; dipanggil `make test-ascon-mutants`)

Untuk setiap mutan, rtl/ascon_core.v disalin ke build/ascon_mutants/<nama>/ dengan tepat
satu substitusi teks, lalu test cocotb tb/ascon dijalankan pada salinan itu (TESTCASE di
bawah). Mutan dianggap "terbunuh" kalau test pembunuhnya gagal. Mutan yang gagal
dikompilasi TIDAK dihitung terbunuh (hasil XML harus berisi semua testcase).

Keluar 0 kalau semua mutan terbunuh, 1 kalau ada yang lolos.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "rtl", "ascon_core.v")
TB = os.path.join(REPO, "tb", "ascon")
OUT = os.path.join(REPO, "build", "ascon_mutants")
TESTS = ["test_kat_aead", "test_acvp_aead", "test_wrong_tag"]

# (nama, teks asli, teks mutan, test yang wajib gagal, keterangan)
MUTANTS = [
    ("konstanta_ronde",
     "x2 = x2 ^ {56'd0, ~r, r};",
     "x2 = x2 ^ {56'd0, r, ~r};",
     "test_kat_aead",
     "nibble konstanta ronde tertukar ({r, 15-r} alih-alih {15-r, r})"),
    ("rotasi_linear",
     "rotr(x0, 19)",
     "rotr(x0, 18)",
     "test_kat_aead",
     "rotasi x0 di lapisan linear 18 alih-alih 19"),
    ("perbandingan_tag",
     "(((tag_calc ^ tag_in_r) & tag_mask) == 128'd0)",
     "(((tag_calc ^ tag_in_r) & tag_mask & {64'd0, {64{1'b1}}}) == 128'd0)",
     "test_wrong_tag",
     "verifikasi tag hanya membandingkan 64 bit rendah"),
]


def results(path):
    """{nama test: lulus?} dari results XML cocotb."""
    root = ET.parse(path).getroot()
    return {tc.get("name"): tc.find("failure") is None and tc.find("error") is None
            for tc in root.iter("testcase")}


def main():
    with open(SRC) as f:
        orig = f.read()
    killed_all = True
    rows = []
    for name, old, new, killer, desc in MUTANTS:
        n = orig.count(old)
        assert n == 1, f"{name}: teks asli ditemukan {n}x (harus 1)"
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        src = os.path.join(d, "ascon_core.v")
        with open(src, "w") as f:
            f.write(orig.replace(old, new))
        xml = os.path.join(d, "results.xml")
        if os.path.exists(xml):
            os.unlink(xml)
        print(f"==> mutan {name}: {desc}", flush=True)
        log = os.path.join(d, "sim.log")
        with open(log, "w") as lf:
            subprocess.run(["make", "--no-print-directory", f"ASCON_SRC={src}",
                            f"SIM_BUILD={os.path.join(d, 'sim_build')}",
                            f"COCOTB_RESULTS_FILE={xml}", f"TESTCASE={','.join(TESTS)}"],
                           cwd=TB, stdout=lf, stderr=subprocess.STDOUT)
        if not os.path.exists(xml):
            print(f"    TIDAK VALID: tidak ada hasil (gagal kompilasi?), lihat {log}")
            killed_all = False
            continue
        res = results(xml)
        missing = [t for t in TESTS if t not in res]
        if missing:
            print(f"    TIDAK VALID: testcase hilang {missing}, lihat {log}")
            killed_all = False
            continue
        killed = not res[killer]
        killed_all &= killed
        status = "  ".join(f"{t}={'lulus' if res[t] else 'GAGAL'}" for t in TESTS)
        print(f"    {status}")
        print(f"    {'TERBUNUH' if killed else 'LOLOS'} ({killer} {'gagal' if killed else 'lulus'})")
        rows.append((name, killed))
    print(("PASS" if killed_all else "FAIL") +
          f" uji mutasi: {sum(k for _, k in rows)}/{len(MUTANTS)} mutan terbunuh")
    sys.exit(0 if killed_all else 1)


if __name__ == "__main__":
    main()
