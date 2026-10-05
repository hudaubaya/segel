#!/usr/bin/env python3
"""Hitung bit error rate dari CSV hasil fpga/phy_loopback/scripts/ber_sweep.tcl.

  python3 sw/ber.py ber_sweep.csv [--json hasil.json]
  python3 sw/ber.py --self-test

Satu baris CSV per (revisi, mode). Definisi (docs/phy_howto.md, "Analisis BER"):
  mode raw     BER kanal = raw_errors / raw_bits: bit PRBS-31 mentah di kabel, setiap bit
               salah dihitung sekali oleh BERT. INI angka BER.
  mode framed  FER = rx_frames_bad / rx_frames, frame hilang = tx_frames - rx_frames,
               pelanggaran simbol = (phy_code + phy_disp) / (tx_cycles / 10).
               "BER payload" = bit_errors / bits_checked hanya indikator: simbol yang
               ditandai galat dibuang phy sehingga sisa frame bergeser dan satu galat bit
               bisa terhitung ratusan bit. Jangan dilaporkan sebagai BER.
  Batas atas   = batas atas satu sisi 95% (Poisson): untuk 0 galat ~ 3,0 / bit. Dengan 0
               galat, klaim yang sah adalah "BER < batas atas", bukan "BER = 0".
Peringatan dicetak kalau counter jenuh, sinkron/lock hilang, atau rx_overflow = 1.
"""

import argparse
import csv
import json
import math
import sys

U16_MAX = 0xFFFF
U32_MAX = 0xFFFFFFFF
INT_COLS = ("tx_rate_khz", "sys_cycles", "tx_cycles", "tx_clk_hz", "tx_frames", "rx_frames",
            "rx_frames_bad", "bits_checked", "bit_errors", "phy_ok", "phy_crc", "phy_code",
            "phy_disp", "phy_ctrl", "phy_frame", "phy_lost", "raw_bits", "raw_errors",
            "raw_loss", "pll_locked", "rx_locked", "rx_overflow", "raw_locked")
PHY_COLS = ("phy_ok", "phy_crc", "phy_code", "phy_disp", "phy_ctrl", "phy_frame", "phy_lost")


def poisson_cdf(k, lam):
    """P(X <= k) untuk X ~ Poisson(lam), dihitung di ruang log."""
    if lam <= 0:
        return 1.0
    total, log_term = 0.0, -lam
    for i in range(k + 1):
        if i:
            log_term += math.log(lam) - math.log(i)
        total += math.exp(log_term)
    return min(total, 1.0)


def poisson_upper(k, conf=0.95):
    """Batas atas satu sisi untuk rata-rata Poisson setelah mengamati k kejadian."""
    lo, hi = 0.0, max(10.0, 3.0 * k + 10.0)
    while poisson_cdf(k, hi) > 1 - conf:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if poisson_cdf(k, mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return hi


def analyze(row):
    r = {k: (int(row[k]) if k in INT_COLS else row[k]) for k in row}
    mode = r.get("mode", "framed")
    out = dict(revision=r["revision"], mode=mode, tx_rate_khz=r["tx_rate_khz"],
               seconds=float(r["seconds"]), warnings=[])
    w = out["warnings"]
    if mode == "raw":
        n, k = r["raw_bits"], r["raw_errors"]
        out["ber_kind"] = "kanal (RAW)"
        if not r["raw_locked"]:
            w.append("raw_locked = 0 di akhir")
        if r["raw_loss"]:
            w.append(f"BERT kehilangan sinkron {r['raw_loss']}x: BER tidak valid "
                     "(bit selama SEARCH tidak dihitung)")
    else:
        n, k = r["bits_checked"], r["bit_errors"]
        out["ber_kind"] = "payload (indikator, bukan BER)"
        if not r["rx_locked"]:
            w.append("rx_locked = 0")
        if r["rx_overflow"]:
            w.append("rx_overflow = 1 (sys_clk tidak mengikuti laju RX)")
        if k == U32_MAX:
            w.append("bit_errors jenuh")
        for c in PHY_COLS:
            if r[c] == U16_MAX:
                w.append(f"{c} jenuh (16 bit)")
    out["bits"], out["bit_errors"] = n, k
    out["ber"] = k / n if n else None
    out["ber_upper95"] = poisson_upper(k) / n if n else None
    out["frames_tx"], out["frames_rx"] = r["tx_frames"], r["rx_frames"]
    out["frames_lost"] = max(r["tx_frames"] - r["rx_frames"], 0)
    out["frame_error_ratio"] = (r["rx_frames_bad"] / r["rx_frames"]
                                if mode != "raw" and r["rx_frames"] else None)
    symbols = r["tx_cycles"] // 10
    out["symbols"] = symbols
    out["symbol_violations"] = r["phy_code"] + r["phy_disp"]
    out["symbol_violation_rate"] = (out["symbol_violations"] / symbols
                                    if mode != "raw" and symbols else None)
    out["tx_clk_hz"] = r["tx_clk_hz"]
    nominal = r["tx_rate_khz"] * 1000
    out["tx_clk_ppm"] = (r["tx_clk_hz"] - nominal) / nominal * 1e6 if nominal else None
    if not r["pll_locked"]:
        w.append("pll_locked = 0")
    if n == 0:
        w.append("tidak ada bit yang diperiksa")
    if out["tx_clk_ppm"] is not None and abs(out["tx_clk_ppm"]) > 1000:
        w.append(f"tx_clk terukur menyimpang {out['tx_clk_ppm']:.0f} ppm dari nominal")
    return out


def fmt(v, spec=".3e"):
    return "-" if v is None else format(v, spec)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.csv:
        ap.error("butuh file CSV")
    with open(a.csv, newline="") as f:
        rows = [analyze(r) for r in csv.DictReader(f)]
    print(f"{'revisi':10s} {'mode':6s} {'kHz':>6s} {'bit':>14s} {'galat':>9s} {'BER':>10s} "
          f"{'BER<(95%)':>10s} {'frame rx':>9s} {'FER':>9s} {'hilang':>6s} {'viol/simbol':>11s}")
    for o in rows:
        print(f"{o['revision']:10s} {o['mode']:6s} {o['tx_rate_khz']:6d} {o['bits']:14d} "
              f"{o['bit_errors']:9d} {fmt(o['ber']):>10s} {fmt(o['ber_upper95']):>10s} "
              f"{o['frames_rx']:9d} {fmt(o['frame_error_ratio']):>9s} {o['frames_lost']:6d} "
              f"{fmt(o['symbol_violation_rate']):>11s}")
        for w in o["warnings"]:
            print(f"  PERINGATAN {o['revision']}/{o['mode']}: {w}")
    print("BER kanal = baris mode raw. Baris framed: FER dan pelanggaran simbol; kolom BER di "
          "baris itu hanya indikator payload (lihat --help).")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rows, f, indent=1)
    return 0


def self_test():
    # Batas atas Poisson 95% satu sisi = chi2(0.95, 2k+2) / 2
    for k, ref in ((0, 2.995732), (1, 4.743865), (10, 16.962)):
        got = poisson_upper(k)
        assert abs(got - ref) / ref < 1e-3, (k, got, ref)
    base = dict(revision="r25", tx_rate_khz="24750", seconds="10", sys_cycles="500000000",
                tx_cycles="247500000", tx_clk_hz="24750000", tx_frames="1000", rx_frames="998",
                rx_frames_bad="2", bits_checked="479040", bit_errors="5", phy_ok="996",
                phy_crc="2", phy_code="1", phy_disp="3", phy_ctrl="0", phy_frame="0",
                phy_lost="0", raw_bits="0", raw_errors="0", raw_loss="0", pll_locked="1",
                rx_locked="1", rx_overflow="0", raw_locked="0", timestamp="-")
    o = analyze(dict(base, mode="framed"))
    assert o["ber"] == 5 / 479040 and o["frames_lost"] == 2 and o["frame_error_ratio"] == 2 / 998
    assert abs(o["ber_upper95"] - poisson_upper(5) / 479040) < 1e-15
    assert o["symbol_violations"] == 4 and o["symbols"] == 24750000
    assert o["tx_clk_ppm"] == 0 and not o["warnings"], o["warnings"]
    o = analyze(dict(base, mode="framed", bit_errors="0", phy_code="65535", rx_overflow="1"))
    assert o["ber"] == 0 and abs(o["ber_upper95"] * 479040 - 2.995732) < 1e-3
    assert any("jenuh" in w for w in o["warnings"]) and any("overflow" in w for w in o["warnings"])
    raw = dict(base, mode="raw", raw_bits="247500000", raw_errors="3", raw_locked="1",
               rx_locked="0", phy_code="0", phy_disp="0")
    o = analyze(raw)
    assert o["bits"] == 247500000 and o["ber"] == 3 / 247500000 and not o["warnings"], o
    assert o["frame_error_ratio"] is None and o["symbol_violation_rate"] is None
    o = analyze(dict(raw, raw_loss="2"))
    assert any("sinkron" in w for w in o["warnings"])
    # Tanpa kolom mode (CSV lama) = framed
    o = analyze({k: v for k, v in base.items()})
    assert o["mode"] == "framed"
    print("sw/ber.py: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
