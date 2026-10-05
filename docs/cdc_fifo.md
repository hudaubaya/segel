# CDC FIFO (`rtl/cdc_fifo/`)

Salinan SEGEL dari baseline TT07 #0036 (`Pa1mantri/tt07_cdc_fifo` @
`ff14afce`, Apache-2.0) dengan perbaikan temuan **F1** dan **F3** dari
[`docs/baseline_audit.md`](baseline_audit.md). Baseline di
`rtl/baseline/cdc_fifo_0036/` tidak diubah; audit-nya tetap menguji perilaku
aslinya.

## Perubahan terhadap baseline

Selain nama modul top, logika hanya berubah di dua tempat (`diff -ru rtl/baseline/cdc_fifo_0036/src rtl/cdc_fifo`).
Setiap file yang diubah diberi header yang mencatat asal dan perubahannya,
sesuai Apache-2.0 §4(b). File lainnya disalin byte-per-byte.

| Temuan | File | Sebelum | Sesudah |
|---|---|---|---|
| — | `tt_um_aduhayabu_cdc_fifo.sv` | `module tt_um_pa1mantri_cdc_fifo` | `module tt_um_aduhayabu_cdc_fifo` |
| F1 | `tt_um_aduhayabu_cdc_fifo.sv` | `assign write_data = ui_in[4];` | `assign write_data = ui_in[7:4];` |
| F3 | `cdc_fifo_write_state.sv` | `full = (write_address + 1 == read_address)` | `write_address_next = write_address + 1'b1;` (selebar `ADDRESS_WIDTH`), lalu `full = (write_address_next == read_address)` |

**Mengapa F3 diperbaiki dengan wire berukuran, bukan cukup `+ 1'b1`?** Kedua
cara memberi hasil 5 bit. Namun wire `write_address_next` yang lebarnya
dideklarasikan eksplisit tidak bergantung pada aturan lebar ekspresi Verilog,
jadi lebih sulit rusak lagi kalau ekspresinya diubah di kemudian hari.

Pinout sama dengan baseline (`info.yaml` #0036). Kini `ui[4..7]` benar-benar
menjadi `write_data0..3`.

## Yang tidak diubah

Temuan berikut masih berlaku untuk salinan ini (detail di audit):

- **F2:** `rst_n` global diabaikan; reset lewat `uio_in[0]`/`uio_in[1]`.
- **F4:** kapasitas 31, bukan 32.
- **F5:** pointer Gray dibentuk kombinasional dari register biner, bukan
  diregister.
- Deassertion reset tidak disinkronkan ke masing-masing clock.

## Verifikasi

`make test-cdc_fifo` menjalankan `tb/cdc_fifo/test.py`. Bench-nya sama dengan
audit baseline (`tb/common/cdc_fifo_bench.py`), sehingga pemeriksaannya
identik.

| Test | Cakupan | Baseline |
|---|---|---|
| `test_core_capacity_after_reset` | Setelah reset, tepat 31 write lalu `full=1` | gagal (F3) |
| `test_core_capacity_every_read_pointer` | Sama, untuk pointer read 0..32 (32 = membungkus ke 0) | — |
| `test_core_random_ratios` | 24 rasio clock acak tanpa batas isi; seed yang sama dengan audit | gagal (F3) |
| `test_core_random_ratios_more_seeds` | 3 seed × 12 rasio acak tanpa batas isi | — |
| `test_core_random_ratios_below_full` | Regresi: isi ≤ 29 | lulus |
| `test_top_random_ratios_4bit` | Lewat pin TT, data 4 bit acak, tanpa batas isi | gagal (F1) |
| `test_top_unused_outputs` | `uo_out[3:2]`, `uio_out`, `uio_oe` = 0 | lulus |

Semua test memeriksa urutan data (tanpa hilang, ganda, atau tertukar), flag
`full`/`empty`, `read_data` = kepala antrean selama `empty=0`, dan langkah
pointer Gray 1 bit. Pada `test_core_random_ratios`, 3.123 item lewat dengan
isi mencapai 31 dan `full` teramati 5.016 kali.

Mutation check (dijalankan manual):

- **F1 dikembalikan:** `test_top_random_ratios_4bit` gagal.
- **F3 dikembalikan:** empat test inti gagal (`capacity_after_reset`,
  `capacity_every_read_pointer`, `random_ratios`, `random_ratios_more_seeds`).
  `test_top_random_ratios_4bit` tetap lulus karena seed-nya tidak pernah
  mengenai kondisi batas. Jadi penjaga F3 adalah test inti, bukan test pin.

### Batasan

- Hanya simulasi RTL (Icarus). Salinan ini belum disintesis, jadi belum ada
  netlist yang bisa diuji seperti audit GL baseline.
- Metastabilitas tidak dimodelkan; risiko F5 tetap ada.
