# tb/

Testbench cocotb untuk RTL SEGEL (`rtl/`), satu subdirektori per blok. Testbench baseline TT07 tetap di
`rtl/baseline/<nama>/test/` agar salinan upstream tidak berubah.

- `tb/crc8/` — RTL CRC-8 SEGEL dan netlist baseline #0901
- `tb/cdc_fifo/` — CDC FIFO SEGEL (perbaikan F1/F3 dari #0036)
- `tb/audit/` — audit baseline TT07 apa adanya (`docs/baseline_audit.md`):
  `serdes/`, `cdc_fifo/` (RTL) dan `gl/` (netlist tapeout, level pin)
- `tb/common/` — file bersama: stub sel fisik untuk simulasi GL dan bench CDC FIFO
