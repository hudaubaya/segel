# CDC FIFO (`rtl/cdc_fifo/`)

Salinan SEGEL dari baseline TT07 #0036 (`Pa1mantri/tt07_cdc_fifo` @
`ff14afce`, Apache-2.0) dengan perbaikan temuan **F1, F2, F3, F5, dan F6**, serta **sinkronisasi reset**,
dari [`docs/baseline_audit.md`](baseline_audit.md). Baseline di
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
| F6 | `cdc_fifo.sv` | `uio_in[0]` hanya mereset domain write, `uio_in[1]` hanya domain read | Kedua synchronizer reset menerima `write_reset \| read_reset`, sehingga pin reset mana pun mereset kedua domain |
| Reset | `cdc_fifo.sv`, `reset_synchronizer.sv` (baru) | Reset pin langsung ke semua flop, dilepas asinkron | Setiap domain lewat `reset_synchronizer` 2 tahap: assert asinkron, deassert sinkron ke clock domain itu |

Pinout sama dengan baseline (`info.yaml` #0036). Kini `ui[4..7]` benar-benar
menjadi `write_data0..3`, dan `rst_n` mereset seluruh FIFO.

**Perbedaan perilaku dari datasheet #0036 (F6):** pin `uio[0]`
("write_reset") dan `uio[1]` ("read_reset") masing-masing kini mereset
**seluruh** FIFO, bukan hanya domainnya sendiri. Kalau yang direset hanya satu
sisi, isinya pasti tidak konsisten, jadi tidak ada cara aman untuk
mempertahankan perilaku lama.

`reset_synchronizer.sv` adalah file baru milik SEGEL, bukan turunan baseline.

### Catatan desain

- **F2 mempertahankan pin reset `uio`.** `rst_n` ditambahkan dengan OR ke pin
  `uio_in[0]`/`uio_in[1]`; sejak F6, ketiganya mereset seluruh FIFO. Semua
  reset asinkron aktif rendah. Konsekuensinya, reset yang masuk ke synchronizer
  adalah keluaran gerbang OR, bukan pin langsung. Glitch pada OR bisa memicu
  reset palsu (assert-nya asinkron), tetapi hanya kalau beberapa masukan
  berubah bersamaan. [Kemungkinan Besar] dapat diterima untuk reset yang
  dikendalikan manusia atau MCU.
- **F5 mengubah struktur, bukan perilaku.** Register Gray diisi
  `gray(pointer + 1)` pada tepi yang sama ketika pointer biner naik, jadi di
  setiap siklus nilainya sama dengan `gray(pointer)`, sama seperti sebelumnya.
  Semua test fungsional memberi angka identik sebelum dan sesudah F5 (mis.
  3.123 item dan `full` teramati 5.016 kali pada `test_core_random_ratios`).
  Biayanya 8 flop tambahan menurut `synth` Yosys (18 flop pointer dengan
  enable, sebelumnya 10; total sel 433 → 445). Register Gray 5 bit per domain,
  tetapi MSB Gray sama dengan MSB biner sehingga Yosys menggabungkannya.
- **F6 digabung di dalam `cdc_fifo`, sebelum reset synchronizer.** Reset
  gabungan masuk ke kedua domain secara asinkron, lalu dilepas sinkron ke clock
  masing-masing, sehingga kedua domain bisa keluar dari reset pada waktu
  berbeda. Urutan apa pun aman: domain yang masih reset menahan pointer-nya
  (dan pointer Gray yang dikirimnya) di 0, dan itu konsisten dengan FIFO kosong
  yang dilihat domain lain. Hal ini diuji dengan clock read yang dihentikan
  saat reset dilepas (`test_reset_release_order_is_safe`).
- **Sinkronisasi reset ada di dalam `cdc_fifo`, bukan di wrapper.** Jadi inti
  FIFO aman dipakai sendiri, dan `rst_n` maupun pin `uio` sama-sama
  melewatinya. Assert tetap asinkron: FIFO langsung masuk reset walaupun clock
  berhenti. Deassert terjadi tepat di tepi naik ke-2 clock domain itu. Kalau
  clock domain berhenti, domain itu tetap dalam reset sampai clock berjalan
  lagi; ini disengaja, karena tanpa clock state tidak bisa berubah. Biayanya
  4 flop (`$_DFF_PP1_`, total sel 445 → 449).
- **F3 memakai wire berukuran, bukan cukup `+ 1'b1`.** Kedua cara memberi hasil
  5 bit, tetapi wire yang lebarnya dideklarasikan eksplisit tidak bergantung
  pada aturan lebar ekspresi Verilog. Wire yang sama dipakai juga oleh F5.

## Yang tidak diubah

- **F4:** kapasitas 31, bukan 32 (pointer tanpa bit wrap).
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
| `test_reset_deassert_synchronous` | Reset tersinkron naik seketika, lalu turun tepat di tepi naik ke-2, untuk 60 fase pelepasan acak per domain | — |
| `test_reset_held_while_clock_stopped` | Tanpa clock, domain tetap dalam reset; turun 2 tepi setelah clock berjalan; domain lain tidak terpengaruh | — |
| `test_top_reset_paths_use_synchronizer` | `rst_n` dan pin `uio` sama-sama lewat synchronizer | — |
| `test_top_write_domain_reset_empties_fifo` | Reset hanya lewat `uio_in[0]` mengosongkan seluruh FIFO; tanpa data basi; 3 item baru kembali utuh | gagal (F6) |
| `test_top_read_domain_reset_empties_fifo` | Sama, lewat `uio_in[1]` | gagal (F6) |
| `test_reset_release_order_is_safe` | Clock read berhenti saat reset dilepas: domain write keluar lebih dulu dan menulis 8 item; setelah clock read berjalan, kedelapannya terbaca utuh | — |

Semua test acak memeriksa urutan data (tanpa hilang, ganda, atau tertukar),
flag `full`/`empty`, `read_data` = kepala antrean selama `empty=0`, dan langkah
pointer Gray 1 bit.

### Struktur: `make test-cdc_fifo-struct` (`tb/struct/check_cdc_regs.py`)

Simulasi RTL zero-delay tidak bisa menunjukkan glitch maupun pelanggaran
recovery/removal, jadi keduanya dibuktikan dari struktur. Skrip mensintesis
`cdc_fifo` dengan Yosys (`synth -flatten`, gerbang generik), lalu memeriksa:

- **gray:** masukan D setiap flop tingkat pertama synchronizer pointer
  digerakkan langsung oleh keluaran Q flop domain sumber;
- **reset:** pin reset setiap flop ber-reset (selain flop synchronizer reset
  itu sendiri) digerakkan oleh keluaran `reset_synchronizer` domain yang sama
  dengan clock flop tersebut.

| | gray | reset |
|---|---|---|
| Baseline #0036 (`make test-audit-struct-cdc_fifo`) | 2/10 (hanya MSB) | 0/30 |
| `rtl/cdc_fifo/` | **10/10** | **38/38** |

### Mutation check (dijalankan manual)

| Perubahan sengaja | Gagal di |
|---|---|
| F1 dikembalikan | `test_top_random_ratios_4bit` |
| F2 dikembalikan | `test_top_rst_n_resets_fifo`, `test_top_rst_n_async_without_clocks` |
| F3 dikembalikan | 4 test inti (`capacity_after_reset`, `capacity_every_read_pointer`, `random_ratios`, `random_ratios_more_seeds`) |
| F5 dikembalikan di sisi write (Gray kombinasional lagi) | Hanya pemeriksaan struktur (6/10); semua test fungsional tetap lulus |
| F5 salah langkah (register diisi `gray(pointer)`, bukan `gray(pointer + 1)`) | 7 test fungsional, termasuk `test_registered_gray_equals_gray_of_binary`; pemeriksaan struktur tetap lulus |
| Reset M1: `writestate` memakai reset tanpa synchronizer | Hanya struktur reset (29/38) |
| Reset M2: synchronizer pointer domain read direset oleh reset domain write | Hanya struktur reset (28/38) |
| Reset M3: synchronizer hanya 1 tahap | `test_reset_deassert_synchronous`, `test_reset_held_while_clock_stopped`; struktur tetap lulus |
| Reset M4: assert reset menjadi sinkron | 4 test reset; struktur tetap lulus |
| F6 dikembalikan | 2 test reset satu domain + `test_reset_release_order_is_safe` |
| F6 hanya di synchronizer domain read | `test_top_read_domain_reset_empties_fifo` |
| F6 hanya di synchronizer domain write | `test_top_write_domain_reset_empties_fifo`, `test_reset_release_order_is_safe` |

Pola yang sama berlaku untuk F5 dan reset: pemeriksaan struktur menjaga
*sambungan* (tidak ada gerbang di jalur lintas domain, setiap flop memakai reset
domainnya sendiri), sedangkan test cocotb menjaga *nilai dan waktu* (Gray yang
diregister benar, reset turun tepat di tepi ke-2). Untuk F5 secara khusus:
struktur menjaga tidak ada gerbang di jalur lintas domain, sedangkan test
fungsional menjaga nilai yang diregister tetap benar.

Untuk F3, test acak lewat pin tidak mengenai kondisi batasnya. Penjaga F3 adalah
test inti, terutama uji 33 posisi pointer.

### Batasan

- Sintesis memakai gerbang generik Yosys, bukan sky130 + OpenLane. Belum ada
  netlist pasca-PnR yang bisa diuji seperti audit GL baseline.
- Pemeriksaan struktur membuktikan sambungannya: tidak ada gerbang antara flop
  sumber dan synchronizer, dan setiap reset berasal dari synchronizer domain
  yang benar. Ini tidak membuktikan timing atau ketahanan metastabilitas.
