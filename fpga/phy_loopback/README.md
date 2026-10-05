# fpga/phy_loopback/

Uji loopback lapisan fisik SEGEL (`rtl/phy/`, tanpa kriptografi) di DE10-Nano.
Langkah lengkap, pin, SDC, dan analisis BER: [`docs/phy_howto.md`](../../docs/phy_howto.md).
Belum pernah dikompilasi Quartus atau dijalankan di papan.

| Path | Isi |
|---|---|
| `rtl/de10nano_phy_loopback.v` | Top: PLL TX, phy, PRBS berbingkai dan RAW, register, JTAG master |
| `rtl/pll_tx.v` | `altera_pll`, satu keluaran per revisi (`TX_SEL`) |
| `rtl/fwd_clk_out.v` | Clock yang diteruskan lewat `altddio_out` |
| `rtl/prbs_framegen.v`, `prbs_checker.v` | Frame PRBS-31 lewat phy |
| `rtl/prbs_raw.v` | Generator dan checker BERT untuk bit PRBS-31 mentah |
| `rtl/cdc_event_counter.v` | Counter Gray lintas domain (siklus tx_clk, counter BERT) |
| `rtl/loopback_regs.v` | Register Avalon-MM |
| `qsys/make_phy_jtag.tcl` | Sistem Platform Designer JTAG-to-Avalon Master |
| `quartus/create_project.tcl` | Proyek + revisi `phy_loopback_r05/r10/r20/r25`, pin |
| `quartus/phy_loopback.sdc` | Constraint timing |
| `scripts/build_all.sh` | Platform Designer → proyek → kompilasi → laporan timing |
| `scripts/sta_checks.tcl` | Laporan Timing Analyzer yang wajib diperiksa |
| `scripts/ber_sweep.tcl` | System Console: sweep laju → CSV |

Test tanpa Quartus atau papan: `make test-fpga-loopback test-fpga-scripts`
(`tb/fpga_loopback/`, `tb/fpga_scripts/`).
