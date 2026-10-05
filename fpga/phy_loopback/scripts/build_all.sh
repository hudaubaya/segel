#!/usr/bin/env bash
# Bangun semua revisi uji loopback PHY untuk DE10-Nano (docs/phy_howto.md).
#
#   cd fpga/phy_loopback && ./scripts/build_all.sh [r05 r10 r20 r25]
#
# Butuh Quartus Prime Lite/Standard (qsys-script, qsys-generate, quartus_sh, quartus_sta)
# di PATH. Langkah: sistem JTAG Platform Designer -> proyek + revisi -> kompilasi ->
# laporan timing SEGEL. Berhenti di kegagalan pertama.
set -euo pipefail
cd "$(dirname "$0")/.."
revs=("${@:-r05 r10 r20 r25}")
read -r -a revs <<< "${revs[*]}"

echo "== Platform Designer: phy_jtag"
(cd qsys && qsys-script --script=make_phy_jtag.tcl \
         && qsys-generate phy_jtag.qsys --synthesis=VERILOG --output-directory=phy_jtag)

echo "== proyek Quartus"
(cd quartus && quartus_sh -t create_project.tcl)

for r in "${revs[@]}"; do
    rev="phy_loopback_${r}"
    echo "== kompilasi ${rev}"
    (cd quartus && quartus_sh --flow compile phy_loopback -c "${rev}")
    echo "== laporan timing ${rev}"
    (cd quartus && quartus_sta -t ../scripts/sta_checks.tcl phy_loopback "${rev}")
done
echo "SOF: quartus/output_files/phy_loopback_<revisi>.sof"
