# segel

## Struktur

```
rtl/                 RTL SEGEL (rtl/crc8/: CRC-8, docs/crc8.md; rtl/cdc_fifo/: CDC FIFO, docs/cdc_fifo.md)
rtl/baseline/        Baseline TT07 yang disalin apa adanya (lihat docs/baselines.md)
tb/                  Testbench cocotb untuk RTL SEGEL
model/               Model referensi
fpga/phy_loopback/   Desain FPGA uji loopback PHY
fpga/release/        Build FPGA rilis
sw/                  Perangkat lunak host
docs/                Dokumentasi
```

## Menjalankan test

Butuh Icarus Verilog (diuji dengan 12.0), Yosys (diuji dengan 0.33, untuk
pemeriksaan struktur CDC FIFO) dan Python 3.11.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make test
```

Simulasi gate-level mengunduh model sel sky130 (±4 MB) ke `.cache/` saat
pertama kali dijalankan, jadi butuh akses ke github.com. `make help`
menampilkan target lain. CI (`.github/workflows/test.yml`)
menjalankan `make test` di setiap pull request dan push ke `main`.

## Lisensi

Setiap baseline di `rtl/baseline/` membawa lisensinya sendiri
(Apache-2.0, lihat `docs/baselines.md`). Lisensi untuk kode SEGEL sendiri
belum ditentukan.
