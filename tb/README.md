# tb/

Testbench cocotb untuk RTL SEGEL (`rtl/`), satu subdirektori per blok. Testbench baseline TT07 tetap di
`rtl/baseline/<nama>/test/` agar salinan upstream tidak berubah.

- `tb/crc8/` — RTL CRC-8 SEGEL dan netlist baseline #0901
- `tb/cdc_fifo/` — CDC FIFO SEGEL (perbaikan F1/F3 dari #0036)
- `tb/audit/` — audit baseline TT07 apa adanya (`docs/baseline_audit.md`):
  `serdes/`, `cdc_fifo/` (RTL) dan `gl/` (netlist tapeout, level pin)
- `tb/ascon/` — Ascon-AEAD128/XOF128 (`rtl/ascon_core.v`): vektor resmi, acak vs model,
  tag salah, siklus, dan uji mutasi (`mutants.py`); lihat `docs/ascon.md`
- `tb/phy/` — PHY serial (`rtl/phy/`): loopback dua PHY (geseran bit, rasio clock,
  injeksi galat bit, batas laju); `tb/phy_units/` — 8b/10b exhaustive dan comma aligner;
  lihat `docs/phy.md`
- `tb/fpga_loopback/` — simulasi top FPGA DE10-Nano (`fpga/phy_loopback`) dengan model
  PLL/DDIO/JTAG; `tb/fpga_scripts/` — SDC, proyek Quartus, dan skrip System Console di
  `tclsh` dengan mock (lihat `docs/phy_howto.md`)
- `tb/common/` — file bersama: stub sel fisik untuk simulasi GL dan bench CDC FIFO
