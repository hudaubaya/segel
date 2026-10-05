# sw/

Perangkat lunak host untuk mengendalikan dan menguji desain.

- `ber.py`: hitung BER, batas atas 95%, FER, dan pelanggaran simbol dari CSV
  `fpga/phy_loopback/scripts/ber_sweep.tcl` (lihat `docs/phy_howto.md`).
  Self-test: `python3 sw/ber.py --self-test`.
