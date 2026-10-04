# Baseline TT07

Tiga desain Tiny Tapeout 07 (TT07) disalin ke `rtl/baseline/` sebagai titik
awal SEGEL. Setiap baseline disimpan **apa adanya** (tanpa modifikasi) beserta
lisensinya, supaya bisa di-diff langsung terhadap upstream.

Versi yang dipakai adalah **commit yang di-tapeout di TT07**, bukan HEAD repo
upstream. Commit tapeout diambil dari `projects/<top_module>/commit_id.json` di
repo shuttle resmi [TinyTapeout/tinytapeout-07](https://github.com/TinyTapeout/tinytapeout-07)
(commit shuttle `3c541b4b416e60c8aca1efc2eeb3c05875f8c526`, dibaca 2026-10-04).
Salinan `commit_id.json` itu ikut disimpan di direktori tiap baseline.

## Ringkasan

| # TT07 | Direktori | Top module | Sumber | Commit tapeout | Lisensi | Status |
|---|---|---|---|---|---|---|
| 0200 | `rtl/baseline/serdes_0200/` | `tt_um_serdes` | [Santeep/TT_UM_SERDES](https://github.com/Santeep/TT_UM_SERDES) | `b8aba214a7adf76361c6c767eccd904c04f3af1c` (2024-05-16) | Apache-2.0 | RTL + test, lulus |
| 0036 | `rtl/baseline/cdc_fifo_0036/` | `tt_um_pa1mantri_cdc_fifo` | [Pa1mantri/tt07_cdc_fifo](https://github.com/Pa1mantri/tt07_cdc_fifo) | `ff14afce16efaed6cf4bd2bd030ef32e10039362` (2024-05-31) | Apache-2.0 | RTL + test, lulus |
| 0901 | `rtl/baseline/crc8_0901/` | `tt_um_aidenfoxivey` | [aidenfoxivey/tt07-verilog-template](https://github.com/aidenfoxivey/tt07-verilog-template) | `ad99cd0eea15a6364ec62136f5d11c1434b5e5a8` | Apache-2.0 | **RTL tidak tersedia** |

Semua `LICENSE` identik byte-per-byte (Apache License 2.0, sha256 file sama
di ketiga direktori). File `test/test.py` dari template Tiny Tapeout membawa
header `SPDX-License-Identifier: MIT` milik Tiny Tapeout; header itu
dipertahankan.

## serdes_0200 — SerDes (#0200)

- Penulis: Mahaa Santeep G
- Upstream: <https://github.com/Santeep/TT_UM_SERDES> (nama kanonis di GitHub: `Santeep/tt_um_serdes`)
- Commit yang disalin: `b8aba214a7adf76361c6c767eccd904c04f3af1c` — "Update info.yaml", 2024-05-16
- Workflow GDS tapeout: <https://github.com/Santeep/TT_UM_SERDES/actions/runs/9115194729>
- HEAD upstream saat disalin: `a7bde309d5398716ea170452a7cfa8a9e163c45c` (2024-07-06). Selisih
  terhadap commit tapeout hanya `docs/info.md` dan `info.yaml`; `src/` dan `test/` identik.
- File yang disalin: `src/`, `test/`, `docs/`, `info.yaml`, `LICENSE`.
- Catatan:
  - `test/test.py` masih test placeholder template TT (hanya memeriksa
    `uo_out == 0` satu siklus setelah reset). Lulusnya test ini **tidak**
    membuktikan jalur 8b/10b–serializer–deserializer benar.
  - Header `src/project.v` masih berbunyi "Copyright (c) 2024 Your Name"
    (sisa template); pemegang hak cipta sebenarnya adalah penulis repo upstream.

## cdc_fifo_0036 — Clock Domain Crossing FIFO (#0036)

- Penulis: Pavan Mantri
- Upstream: <https://github.com/Pa1mantri/tt07_cdc_fifo>
- Commit yang disalin: `ff14afce16efaed6cf4bd2bd030ef32e10039362` — "updated info.md file", 2024-05-31
- Workflow GDS tapeout: <https://github.com/Pa1mantri/tt07_cdc_fifo/actions/runs/9317048642>
- HEAD upstream saat disalin: `17483ab9199889760ceb3400d975052281af0206` (2026-06-11). Selisih
  terhadap commit tapeout hanya `docs/` dan direktori `gds/` (GDS hasil unggah
  manual); `src/` dan `test/` identik.
- File yang disalin: `src/`, `test/`, `docs/`, `info.yaml`, `LICENSE`.
  Direktori `gds/` tidak disalin (bukan bagian commit tapeout).
- Catatan: test upstream hanya memeriksa flag `empty`/`full` setelah reset dan
  setelah satu penulisan; data yang dibaca tidak diverifikasi.

## crc8_0901 — CRC-8 CCITT (#0901)

- Penulis: Aiden Fox Ivey
- Upstream: <https://github.com/aidenfoxivey/tt07-verilog-template>
- Commit tapeout: `ad99cd0eea15a6364ec62136f5d11c1434b5e5a8`
- Workflow GDS tapeout: <https://github.com/aidenfoxivey/tt07-verilog-template/actions/runs/9011435901>
- **Status: repo upstream sudah tidak dapat diakses** (per 2026-10-04: `git ls-remote`
  meminta autentikasi dan daftar repo publik pemilik tidak memuat repo ini — repo
  dihapus atau dijadikan privat). RTL sumber (`src/project.v`) dan testbench tidak
  bisa disalin.
- Yang disalin, dari repo shuttle `TinyTapeout/tinytapeout-07`
  (`projects/tt_um_aidenfoxivey/`, commit shuttle `3c541b4b`):
  - `LICENSE` (Apache-2.0), `info.yaml`, `docs/info.md`, `commit_id.json`
  - `gl/tt_um_aidenfoxivey.v` — **netlist gate-level pasca-PnR** (sky130_fd_sc_hd, dengan
    pin daya `VPWR`/`VGND`), sha256
    `d63aae59038e9c0e65edb5786f742013c4b9ddd001c95b8ef66fd91b48bdbe0a`.
- Konsekuensi:
  - Tidak ada RTL yang bisa dipakai ulang atau dimodifikasi; netlist ini hanya
    referensi perilaku as-taped-out.
  - Simulasi netlist butuh model sel sky130 (`$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog/`)
    yang tidak ada di CI ini. `make test-baseline-crc8_0901` sengaja gagal dengan
    pesan `BLOCKED` dan tidak termasuk `make test`.
- Tindak lanjut yang diperlukan (salah satu):
  1. Minta RTL `ad99cd0` langsung ke penulis (Discord `aidenfoxivey`), lalu ganti
     direktori ini dengan salinan repo pada commit tersebut; atau
  2. Tulis ulang CRC-8 (polinomial x^8+x^2+x+1, nilai awal 0x00, 2 byte per siklus
     menurut `docs/info.md`) sebagai RTL SEGEL sendiri, dan pakai netlist ini
     sebagai golden reference via simulasi gate-level dengan PDK.

## Cara memperbarui baseline

1. Ambil commit dari `commit_id.json` di repo shuttle TT07.
2. Salin `src/ test/ docs/ info.yaml LICENSE` dari upstream pada commit itu tanpa modifikasi.
3. Jalankan `make test-baseline-<nama>` dan perbarui tabel di atas.
