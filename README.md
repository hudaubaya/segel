# segel

## Struktur

```
rtl/                 RTL SEGEL (rtl/crc8/: CRC-8, docs/crc8.md; rtl/cdc_fifo/: CDC FIFO, docs/cdc_fifo.md;
                     rtl/ascon_core.v: Ascon-AEAD128/XOF128 SP 800-232, docs/ascon.md;
                     rtl/phy/: PHY serial 8b/10b source-synchronous, docs/phy.md)
rtl/baseline/        Baseline TT07 yang disalin apa adanya (lihat docs/baselines.md)
tb/                  Testbench cocotb untuk RTL SEGEL
model/               Model referensi
fpga/phy_loopback/   Uji loopback PHY di DE10-Nano (Quartus, System Console; docs/phy_howto.md)
fpga/release/        Build FPGA rilis
fpga/cdc_fifo/       Sintesis CDC FIFO untuk Cyclone V (Yosys)
sw/                  Perangkat lunak host (sw/ber.py: analisis BER)
docs/                Dokumentasi
```

## Menjalankan test

Butuh Icarus Verilog (diuji dengan 12.0), Yosys (diuji dengan 0.33, untuk
pemeriksaan struktur dan sintesis), Tcl 8.6 (`tclsh`, untuk test skrip FPGA dengan
mock) dan Python 3.11. Quartus dan papan tidak dibutuhkan untuk `make test`.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make test
```

Netlist Cyclone V dibangkitkan ke `build/` oleh Yosys. Simulasi gate-level
sky130 mengunduh model sel (±4 MB) ke `.cache/` saat
pertama kali dijalankan, dan vektor uji resmi Ascon (±6 MB, NIST ACVP + KAT ascon-c,
diverifikasi SHA-256) diunduh ke `.cache/ascon-vectors/`, jadi butuh akses ke github.com. `make help`
menampilkan target lain. CI (`.github/workflows/test.yml`)
menjalankan `make test` di setiap pull request dan push ke `main`.

## Lisensi

Setiap baseline di `rtl/baseline/` membawa lisensinya sendiri
(Apache-2.0, lihat `docs/baselines.md`). Lisensi untuk kode SEGEL sendiri
belum ditentukan.
