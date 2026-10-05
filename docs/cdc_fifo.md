# CDC FIFO (`rtl/cdc_fifo/`)

Salinan SEGEL dari baseline TT07 #0036 (`Pa1mantri/tt07_cdc_fifo` @
`ff14afce`, Apache-2.0) dengan perbaikan temuan **F1, F2, F3, dan F5** dari
[`docs/baseline_audit.md`](baseline_audit.md). Baseline di
`rtl/baseline/cdc_fifo_0036/` tidak diubah; audit-nya tetap menguji perilaku
aslinya.

## Perubahan terhadap baseline

Lihat `diff -ru rtl/baseline/cdc_fifo_0036/src rtl/cdc_fifo`. Setiap file yang
diubah diberi header yang mencatat asal dan perubahannya, sesuai Apache-2.0
§4(b). File lainnya disalin byte-per-byte.

| Temuan | File | Sebelum | Sesudah |
|---|---|---|---|
| — | `tt_um_aduhayabu_cdc_fifo.sv` | `module tt_um_pa1mantri_cdc_fifo` | `module tt_um_aduhayabu_cdc_fifo` |
| F1 | `tt_um_aduhayabu_cdc_fifo.sv` | `assign write_data = ui_in[4];` | `assign write_data = ui_in[7:4];` |
| F2 | `tt_um_aduhayabu_cdc_fifo.sv` | `write_reset = !uio_in[0]` (dan `read_reset` serupa) | `write_reset = !uio_in[0] \| !rst_n` (dan `read_reset` serupa) |
| F3 | `cdc_fifo_write_state.sv` | `full = (write_address + 1 == read_address)` | `write_address_next = write_address + 1'b1;` (selebar `ADDRESS_WIDTH`), lalu `full = (write_address_next == read_address)` |
| F5 | `cdc_fifo_write_state.sv`, `cdc_fifo_read_state.sv` | Gray = `binary_to_gray(pointer)` kombinasional, langsung ke synchronizer | Gray = `binary_to_gray(pointer_next)` diregister bersama pointer biner; synchronizer hanya melihat keluaran flop |

Pinout sama dengan baseline (`info.yaml` #0036). Kini `ui[4..7]` benar-benar
menjadi `write_data0..3`, dan `rst_n` mereset seluruh FIFO.

### Catatan desain

- **F2 tetap mempertahankan pin reset `uio`.** `rst_n` ditambahkan dengan OR,
  sehingga datasheet #0036 (reset per domain lewat `uio_in[0]`/`uio_in[1]`)
  tetap berlaku. Kedua reset asinkron aktif rendah. Konsekuensinya, net reset
  setiap domain adalah keluaran gerbang OR, bukan pin langsung. Glitch hanya
  mungkin kalau kedua masukan berubah bersamaan. [Kemungkinan Besar] dapat
  diterima untuk reset yang dikendalikan manusia atau MCU.
- **F5 mengubah struktur, bukan perilaku.** Register Gray diisi
  `gray(pointer + 1)` pada tepi yang sama ketika pointer biner naik, jadi di
  setiap siklus nilainya sama dengan `gray(pointer)`, sama seperti sebelumnya.
  Semua test fungsional memberi angka identik sebelum dan sesudah F5 (mis.
  3.123 item dan `full` teramati 5.016 kali pada `test_core_random_ratios`).
  Biayanya 8 flop tambahan menurut `synth` Yosys (18 flop pointer dengan
  enable, sebelumnya 10; total sel 433 → 445). Register Gray 5 bit per domain,
  tetapi MSB Gray sama dengan MSB biner sehingga Yosys menggabungkannya.
- **F3 memakai wire berukuran, bukan cukup `+ 1'b1`.** Kedua cara memberi hasil
  5 bit, tetapi wire yang lebarnya dideklarasikan eksplisit tidak bergantung
  pada aturan lebar ekspresi Verilog. Wire yang sama dipakai juga oleh F5.

## Yang tidak diubah

- **F4:** kapasitas 31, bukan 32 (pointer tanpa bit wrap).
- **Deassertion reset tidak disinkronkan** ke masing-masing clock. Clock FIFO
  datang dari pin `ui_in[0]`/`ui_in[2]`, jadi synchronizer reset hanya bekerja
  kalau clock tersebut berjalan saat reset dilepas. Ini belum ditangani.
- **Metastabilitas** di synchronizer 2 flop tidak dimodelkan oleh simulasi.

## Verifikasi

### Fungsional: `make test-cdc_fifo` (`tb/cdc_fifo/test.py`)

Bench-nya sama dengan audit baseline (`tb/common/cdc_fifo_bench.py`), sehingga
pemeriksaannya identik.

| Test | Cakupan | Baseline |
|---|---|---|
| `test_core_capacity_after_reset` | Setelah reset, tepat 31 write lalu `full=1` | gagal (F3) |
| `test_core_capacity_every_read_pointer` | Sama, untuk pointer read 0..32 (32 = membungkus ke 0) | — |
| `test_core_random_ratios` | 24 rasio clock acak tanpa batas isi; seed yang sama dengan audit | gagal (F3) |
| `test_core_random_ratios_more_seeds` | 3 seed × 12 rasio acak tanpa batas isi | — |
| `test_core_random_ratios_below_full` | Regresi: isi ≤ 29 | lulus |
| `test_top_random_ratios_4bit` | Lewat pin TT, data 4 bit acak, tanpa batas isi | gagal (F1) |
| `test_top_unused_outputs` | `uo_out[3:2]`, `uio_out`, `uio_oe` = 0 | lulus |
| `test_top_rst_n_resets_fifo` | `rst_n` mengosongkan kedua domain; FIFO bekerja lagi setelahnya | gagal (F2) |
| `test_top_rst_n_async_without_clocks` | `rst_n` bekerja asinkron saat kedua clock berhenti | — |
| `test_top_uio_resets_still_work` | Pin reset `uio` tetap bekerja saat `rst_n` tinggi | lulus |
| `test_registered_gray_equals_gray_of_binary` | Register Gray == `gray(pointer)` setelah setiap tepi clock (4.000 + 1.739 sampel) | — |

Semua test acak memeriksa urutan data (tanpa hilang, ganda, atau tertukar),
flag `full`/`empty`, `read_data` = kepala antrean selama `empty=0`, dan langkah
pointer Gray 1 bit.

### Struktur: `make test-cdc_fifo-struct` (`tb/struct/check_cdc_regs.py`)

Simulasi RTL zero-delay tidak bisa menunjukkan glitch, jadi F5 dibuktikan dari
struktur. Skrip mensintesis `cdc_fifo` dengan Yosys (`synth -flatten`, gerbang
generik). Untuk setiap flop tingkat pertama di kedua synchronizer, skrip
memeriksa bahwa masukan D digerakkan langsung oleh keluaran Q flop yang
di-clock oleh domain sumber.

| | Bit synchronizer langsung dari flop sumber |
|---|---|
| Baseline #0036 (`make test-audit-struct-cdc_fifo`) | 2/10 (hanya MSB) |
| `rtl/cdc_fifo/` | **10/10** |

### Mutation check (dijalankan manual)

| Perubahan sengaja | Gagal di |
|---|---|
| F1 dikembalikan | `test_top_random_ratios_4bit` |
| F2 dikembalikan | `test_top_rst_n_resets_fifo`, `test_top_rst_n_async_without_clocks` |
| F3 dikembalikan | 4 test inti (`capacity_after_reset`, `capacity_every_read_pointer`, `random_ratios`, `random_ratios_more_seeds`) |
| F5 dikembalikan di sisi write (Gray kombinasional lagi) | Hanya pemeriksaan struktur (6/10); semua test fungsional tetap lulus |
| F5 salah langkah (register diisi `gray(pointer)`, bukan `gray(pointer + 1)`) | 7 test fungsional, termasuk `test_registered_gray_equals_gray_of_binary`; pemeriksaan struktur tetap lulus |

Dua baris terakhir menunjukkan kenapa F5 butuh kedua jenis pemeriksaan:
struktur menjaga tidak ada gerbang di jalur lintas domain, sedangkan test
fungsional menjaga nilai yang diregister tetap benar.

Untuk F3, test acak lewat pin tidak mengenai kondisi batasnya. Penjaga F3 adalah
test inti, terutama uji 33 posisi pointer.

### Batasan

- Sintesis memakai gerbang generik Yosys, bukan sky130 + OpenLane. Belum ada
  netlist pasca-PnR yang bisa diuji seperti audit GL baseline.
- Pemeriksaan struktur membuktikan tidak ada gerbang antara flop sumber dan
  synchronizer. Ini tidak membuktikan timing atau ketahanan metastabilitas.
