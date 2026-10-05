# CDC FIFO (`rtl/cdc_fifo/`)

Salinan SEGEL dari baseline TT07 #0036 (`Pa1mantri/tt07_cdc_fifo` @
`ff14afce`, Apache-2.0). Isinya:
- perbaikan temuan **F1–F6** dan **sinkronisasi reset** dari
  [`docs/baseline_audit.md`](baseline_audit.md);
- **model metastabilitas** khusus simulasi;
- **netlist Intel Cyclone V** yang ikut diuji.

Baseline di `rtl/baseline/cdc_fifo_0036/` tidak diubah; audit-nya tetap menguji
perilaku aslinya.

## Perubahan terhadap baseline

Lihat `diff -ru rtl/baseline/cdc_fifo_0036/src rtl/cdc_fifo`. Setiap file yang
diubah diberi header yang mencatat asal dan perubahannya, sesuai Apache-2.0
§4(b). `reset_synchronizer.sv` adalah file baru milik SEGEL.

| Temuan | File | Sebelum | Sesudah |
|---|---|---|---|
| — | `tt_um_aduhayabu_cdc_fifo.sv` | `module tt_um_pa1mantri_cdc_fifo` | `module tt_um_aduhayabu_cdc_fifo` |
| F1 | `tt_um_aduhayabu_cdc_fifo.sv` | `assign write_data = ui_in[4];` | `assign write_data = ui_in[7:4];` |
| F2 | `tt_um_aduhayabu_cdc_fifo.sv` | `write_reset = !uio_in[0]` (dan `read_reset` serupa) | `write_reset = !uio_in[0] \| !rst_n` (dan `read_reset` serupa) |
| F3 | `cdc_fifo_write_state.sv` | `full = (write_address + 1 == read_address)`, dihitung 32 bit | Penjumlahan pointer selebar eksplisit (`write_pointer + 1'b1` ke wire berukuran) |
| F4 | `cdc_fifo_write_state.sv`, `cdc_fifo_read_state.sv`, `cdc_fifo.sv` | Pointer `ADDRESS_WIDTH` bit; `full` saat `wa + 1 == ra`, sehingga kapasitas 31 | Pointer `ADDRESS_WIDTH + 1` bit dengan bit wrap; `full` saat bit wrap beda dan bit lain sama, sehingga kapasitas **32** |
| F5 | `cdc_fifo_write_state.sv`, `cdc_fifo_read_state.sv` | Gray = `binary_to_gray(pointer)` kombinasional, langsung ke synchronizer | Gray = `binary_to_gray(pointer_next)` diregister bersama pointer biner |
| F6 | `cdc_fifo.sv` | `uio_in[0]` hanya mereset domain write, `uio_in[1]` hanya domain read | Kedua synchronizer reset menerima `write_reset \| read_reset` |
| Reset | `cdc_fifo.sv`, `reset_synchronizer.sv` | Reset pin langsung ke semua flop, dilepas asinkron | `reset_synchronizer` 2 tahap per domain: assert asinkron, deassert sinkron |
| Model | `synchronizer.sv`, `reset_synchronizer.sv` | — | Model metastabilitas di balik `` `ifdef METASTABILITY_SIM``; hardware yang disintesis tidak berubah |

Pinout sama dengan baseline (`info.yaml` #0036). Kini `ui[4..7]` benar-benar
menjadi `write_data0..3`, dan `rst_n` mereset seluruh FIFO.

**Perbedaan perilaku dari datasheet #0036:**
- **F4:** FIFO kini menampung **32** item, bukan 31.
- **F6:** pin `uio[0]` ("write_reset") dan `uio[1]` ("read_reset") masing-masing
  mereset **seluruh** FIFO, bukan hanya domainnya sendiri. Mereset satu sisi saja
  pasti membuat isinya tidak konsisten, jadi tidak ada cara aman untuk
  mempertahankan perilaku lama.

### Catatan desain

- **F4 memakai pointer dengan bit wrap (pola Cummings).** Kedua pointer lebarnya
  `ADDRESS_WIDTH + 1` bit; RAM dialamatkan dengan `ADDRESS_WIDTH` bit bawah.
  - **`full`:** bit wrap berbeda dan bit sisanya sama, artinya writer tepat satu
    putaran di depan reader.
  - **`empty`:** seluruh pointer sama.
  - **Konsekuensi:** pointer Gray yang menyeberang domain dan kedua synchronizer
    pointer bertambah 1 bit (5 → 6). Total sel `synth` Yosys naik 449 → 478.
- **F2 mempertahankan pin reset `uio`.** `rst_n` ditambahkan dengan OR ke pin
  `uio_in[0]`/`uio_in[1]`; sejak F6, ketiganya mereset seluruh FIFO. Semua
  reset asinkron aktif rendah.
  - Reset yang masuk ke synchronizer adalah keluaran gerbang OR, bukan pin
    langsung. Glitch pada OR bisa memicu reset palsu (assert-nya asinkron),
    tetapi hanya kalau beberapa masukan berubah bersamaan.
  - [Kemungkinan Besar] dapat diterima untuk reset yang dikendalikan manusia
    atau MCU.
- **F5 mengubah struktur, bukan perilaku.** Register Gray diisi
  `gray(pointer + 1)` pada tepi yang sama ketika pointer biner naik, jadi di
  setiap siklus nilainya sama dengan `gray(pointer)`. Ketika F5 diterapkan,
  semua test fungsional memberi angka identik sebelum dan sesudahnya. Biayanya
  8 flop (sel 433 → 445).
- **F6 digabung di dalam `cdc_fifo`, sebelum reset synchronizer.** Reset
  gabungan masuk ke kedua domain secara asinkron, lalu dilepas sinkron ke clock
  masing-masing.
  - Urutan pelepasan apa pun aman: domain yang masih reset menahan pointer-nya
    (dan pointer Gray yang dikirimnya) di 0, dan itu konsisten dengan FIFO
    kosong di domain lain.
  - Ini diuji dengan clock read yang dihentikan saat reset dilepas
    (`test_reset_release_order_is_safe`), dan dengan model metastabilitas yang
    mengacak waktu pelepasan.
- **Sinkronisasi reset ada di dalam `cdc_fifo`, bukan di wrapper.** Jadi inti
  FIFO aman dipakai sendiri, termasuk di FPGA.
  - **Assert** tetap asinkron: FIFO langsung masuk reset walaupun clock berhenti.
  - **Deassert** terjadi tepat di tepi naik ke-2 clock domain itu.
  - **Kalau clock domain berhenti,** domain itu tetap dalam reset sampai clock
    berjalan lagi.
  - Biayanya 4 flop (sel 445 → 449).

## Model metastabilitas (`` `ifdef METASTABILITY_SIM``)

Simulasi RTL biasa bersifat zero-delay: flop selalu menangkap nilai yang benar,
dan latensi synchronizer selalu tepat 2 siklus. Model ini menambahkan
ketidakpastian yang ada di hardware sungguhan.

- **`synchronizer.sv`:** bit yang masukannya berubah dalam jendela
  `META_WINDOW_NS` sebelum tepi clock tujuan dianggap metastabil. Bit itu
  resolve acak (50%) ke nilai baru atau nilai lama. Kalau ke nilai lama, nilai
  baru baru masuk di tepi berikutnya.
- **`reset_synchronizer.sv`:** kalau reset dilepas dalam jendela sebelum tepi
  clock, pelepasannya bisa mundur satu siklus secara acak.
- **Asumsi:**
  - tahap kedua synchronizer selalu stabil (resolusi selesai dalam satu siklus,
    yaitu asumsi MTBF synchronizer 2 flop);
  - hanya bit yang berubah di dalam jendela yang terpengaruh.

  Jendela default 1 ns jauh lebih lebar dari jendela fisik (orde ps). Lebar itu
  sengaja dipilih supaya kejadiannya cukup sering untuk diuji, bukan untuk
  meniru silikon.
- **Pengaturan:** plusarg `+META_WINDOW_NS=<ns>` dan `+META_SEED=<n>`. Dari
  `make`, gunakan `META=1 META_WINDOW_NS=... META_SEED=...`. Penghitung
  `events` dan `delayed` di setiap instance bisa dibaca testbench.
- **Sintesis:** tanpa define, kodenya sama dengan sebelumnya, sehingga struktur
  hasil sintesis identik.

### Apa yang ditunjukkan model ini

**Unit test synchronizer** (`make test-sync_meta`, `tb/sync_meta/`). Masukan 4
bit diganti 0,2–0,8 ns sebelum tepi clock, sebanyak 200 kali per kasus:

| Transisi | Tanpa model | Dengan model |
|---|---|---|
| Biner multi-bit (mis. `0111 → 1000`), dekat tepi | 200/200 nilai baru | 10 baru, 14 lama, **176 campuran yang tidak pernah ada di sumber** |
| Gray (1 bit), dekat tepi | 200/200 baru | 97 baru, 103 lama, **0 campuran** |
| Biner, jauh dari tepi (5–9 ns) | 200/200 baru | 200/200 baru |

Jadi model ini memang menghasilkan inkoherensi multi-bit, dan pengkodean Gray
memang mencegahnya.

**FIFO dengan model aktif** (`make test-cdc_fifo-meta`). Ke-17 test fungsional
dijalankan ulang dengan model aktif, ditambah `test_metastability_model_active`,
dan semuanya lulus.
- **Synchronizer pointer:** model aktif di keduanya, dan scoreboard serta
  monitor Gray tetap bersih.
  - Selama `test_metastability_model_active` saja: pointer write 86 kejadian
    (34 resolve ke nilai lama), pointer read 64 kejadian (32 ke nilai lama).
  - Sepanjang seluruh run ke-18 test: 394/189 dan 339/171.
  - Penghitung di RTL kumulatif, dan `$urandom` dipakai bersama oleh semua
    test. Jadi angka-angka ini hanya berlaku untuk run penuh
    `make test-cdc_fifo-meta` dengan seed default; test yang dipilih lewat
    `TESTCASE` memberi angka berbeda.
- **Reset synchronizer:** pada `test_reset_deassert_synchronous`, 7 dari 120
  pelepasan mundur satu siklus (test ini menerima 3 tepi hanya kalau pelepasan
  jatuh di dalam jendela).

**Yang TIDAK ditunjukkan model ini.** Mutasi klasik "pointer biner menyeberang
domain" **tidak** membuat scoreboard gagal, baik dengan maupun tanpa model.
Monitor Gray sengaja dimatikan lewat `CDC_GRAY_MONITOR=0` dalam percobaan ini.
- **Alasan [Kemungkinan Besar]:** nilai pointer yang salah hanya bertahan satu
  siklus, dan hanya muncul saat pointer sedang berubah. Pada saat itu minimal
  satu item sungguh ada atau satu slot sungguh kosong, dan FIFO hanya menulis
  atau membaca satu item per siklus.
- **Akibatnya:** di desain ini, penjaga pengkodean Gray adalah monitor Gray
  (`GrayMon`) dan pemeriksaan struktur, bukan scoreboard dengan model
  metastabilitas.

## Netlist Cyclone V (`make cdc_fifo-cyclonev`)

`fpga/cdc_fifo/synth_cyclonev.ys` mensintesis inti `cdc_fifo` (DATA_WIDTH=4,
ADDRESS_WIDTH=5) dengan `synth_intel_alm -family cyclonev -noiopad -noclkbuf`.
Keluarannya ada di `build/cyclonev/` (tidak di-commit; dibangkitkan ulang dari
RTL).

| Sel | Jumlah |
|---|---|
| `MISTRAL_FF` | 52 |
| `MISTRAL_ALUT2/4/5/6` | 10 / 4 / 6 / 3 |
| `MISTRAL_ALUT_ARITH` | 12 |
| `MISTRAL_NOT` | 4 |
| `MISTRAL_MLAB` (RAM 32×4) | 4 |
| **Total** | **95** |

- **`-noiopad -noclkbuf`:** FIFO ini adalah inti yang ditanam di desain FPGA
  yang lebih besar, misalnya di DE10-Nano. Buffer pin dan buffer clock global
  menjadi urusan top-level desain itu.
- **Ini netlist Yosys, bukan Quartus.** Tidak ada place & route, tidak ada
  timing (SDF), dan tidak ada analisis CDC Quartus/TimeQuest. Hasil Quartus
  bisa berbeda. Langkah berikutnya, kalau dibutuhkan, adalah menyintesis RTL
  yang sama di Quartus dan menambahkan constraint `set_false_path` /
  `set_max_skew` untuk jalur synchronizer.

**Simulasi** (`make test-cdc_fifo-cyclonev`, `tb/cdc_fifo_cv/`): netlist
disimulasikan dengan model sel Yosys (`share/yosys/intel_alm/common/*_sim.v`).
Simulasi ini fungsional; delay `specify` diabaikan. Testbench hanya level port,
karena sinyal internal hilang setelah sintesis.

| Test | Cakupan |
|---|---|
| `test_cv_capacity_every_read_pointer` | Pointer read 0..64: tepat 32 write lalu `full=1` |
| `test_cv_random_ratios` | 24 rasio clock acak tanpa batas isi; 3.129 item, isi maks 32, `full` 5.009 kali (sama persis dengan RTL) |
| `test_cv_random_ratios_more_seeds` | 3 seed × 12 rasio acak |
| `test_cv_single_domain_reset` | F6: reset satu domain mengosongkan seluruh FIFO |
| `test_cv_reset_async_without_clocks` | Reset asinkron tanpa clock |

**Struktur** (`make test-cdc_fifo-cyclonev-struct`): pemeriksaan yang sama
dengan target generik, dijalankan pada sel `MISTRAL_FF`. Di sini pin reset-nya
`ACLR`, yang aktif rendah.
- Flop reset synchronizer dikenali dari strukturnya, yaitu `ACLR` yang tidak
  berasal dari flop. Jumlahnya harus tepat 2 per domain.
- Kalau ada flop fungsional yang menerima reset mentah, jumlah itu naik dan
  pemeriksaannya gagal.

## Yang tidak diubah

- **Metastabilitas fisik** tetap di luar jangkauan simulasi. Model di atas
  menguji toleransi fungsional terhadap latensi synchronizer yang tidak pasti,
  bukan MTBF.

## Verifikasi

### Fungsional: `make test-cdc_fifo` (`tb/cdc_fifo/test.py`)

Bench-nya sama dengan audit baseline (`tb/common/cdc_fifo_bench.py`), sehingga
pemeriksaannya identik.

| Test | Cakupan | Baseline |
|---|---|---|
| `test_core_capacity_after_reset` | Setelah reset, tepat 32 write lalu `full=1` | gagal (F3; baseline maks 31) |
| `test_core_capacity_every_read_pointer` | Sama, untuk pointer read 0..64 (kedua nilai bit wrap) | — |
| `test_core_random_ratios` | 24 rasio clock acak tanpa batas isi; seed yang sama dengan audit | gagal (F3) |
| `test_core_random_ratios_more_seeds` | 3 seed × 12 rasio acak tanpa batas isi | — |
| `test_core_random_ratios_below_full` | Regresi: isi ≤ 30 | lulus |
| `test_top_random_ratios_4bit` | Lewat pin TT, data 4 bit acak, tanpa batas isi | gagal (F1) |
| `test_top_unused_outputs` | `uo_out[3:2]`, `uio_out`, `uio_oe` = 0 | lulus |
| `test_top_rst_n_resets_fifo` | `rst_n` mengosongkan kedua domain; FIFO bekerja lagi setelahnya | gagal (F2) |
| `test_top_rst_n_async_without_clocks` | `rst_n` bekerja asinkron saat kedua clock berhenti | — |
| `test_top_uio_resets_still_work` | Pin reset `uio` tetap bekerja saat `rst_n` tinggi | lulus |
| `test_registered_gray_equals_gray_of_binary` | Register Gray == `gray(pointer)` (pointer lengkap dengan bit wrap) setelah setiap tepi clock | — |
| `test_reset_deassert_synchronous` | Reset turun tepat di tepi naik ke-2 (ke-3 hanya kalau model metastabilitas aktif dan pelepasan di dalam jendela), 60 fase acak per domain | — |
| `test_reset_held_while_clock_stopped` | Tanpa clock, domain tetap dalam reset; domain lain tidak terpengaruh | — |
| `test_top_reset_paths_use_synchronizer` | `rst_n` dan pin `uio` sama-sama lewat synchronizer | — |
| `test_top_write_domain_reset_empties_fifo` | Reset hanya lewat `uio_in[0]` mengosongkan seluruh FIFO | gagal (F6) |
| `test_top_read_domain_reset_empties_fifo` | Sama, lewat `uio_in[1]` | gagal (F6) |
| `test_reset_release_order_is_safe` | Clock read berhenti saat reset dilepas; domain write menulis 8 item; semuanya terbaca utuh | — |
| `test_metastability_model_active` | Hanya `META=1`: model aktif di kedua synchronizer, FIFO tetap benar | — |

`test_core_random_ratios`: 3.129 item, isi maksimum 32, `full` teramati 5.009
kali. Uji 65 posisi pointer memakan sekitar 40 detik per target.

### Struktur (`tb/struct/check_cdc_regs.py`)

| | gray | reset |
|---|---|---|
| Baseline #0036 (`make test-audit-struct-cdc_fifo`) | 2/10 | 0/30 |
| `rtl/cdc_fifo/`, generik (`make test-cdc_fifo-struct`) | **12/12** | **46/46** |
| `rtl/cdc_fifo/`, Cyclone V (`make test-cdc_fifo-cyclonev-struct`) | **12/12** | **50/50** (48 flop + 2 cek jumlah synchronizer) |

### Mutation check (dijalankan manual)

| Perubahan sengaja | Gagal di |
|---|---|
| F1 dikembalikan | `test_top_random_ratios_4bit` |
| F2 dikembalikan | `test_top_rst_n_resets_fifo`, `test_top_rst_n_async_without_clocks` |
| F3 dikembalikan | 4 test inti |
| F4-a: `full` gaya lama (`wa+1 == ra`, satu slot dibuang) | 3 test kapasitas/acak |
| F4-b: `full` mengabaikan bit wrap | 3 test kapasitas/acak |
| F4-c: `empty` mengabaikan bit wrap | 3 test kapasitas/acak |
| F5 dikembalikan (Gray kombinasional) | Hanya struktur: generik 6/10 (sebelum F4), Cyclone V 7/12 |
| F5 salah langkah (`gray(pointer)` bukan `gray(pointer+1)`) | 7 test fungsional; struktur tetap lulus |
| Reset M1: `writestate` memakai reset mentah | Hanya struktur: generik 29/38 (sebelum F4); Cyclone V "14 flop (harus 2)" |
| Reset M2: synchronizer pointer direset domain yang salah | Hanya struktur reset (28/38, sebelum F4) |
| Reset M3: synchronizer hanya 1 tahap | 2 test reset; struktur tetap lulus |
| Reset M4: assert reset menjadi sinkron | 4 test reset; struktur tetap lulus |
| F6 dikembalikan / hanya satu sisi | 1–3 test reset satu domain |
| Pointer **biner** menyeberang domain, `CDC_GRAY_MONITOR=0` | **Tidak gagal**, baik tanpa maupun dengan model metastabilitas (lihat penjelasan di atas) |

Pemeriksaan struktur menjaga *sambungan*: tidak ada gerbang di jalur lintas
domain, dan setiap flop memakai reset domainnya sendiri. Test cocotb menjaga
*nilai dan waktu*. Model metastabilitas menjaga *toleransi terhadap latensi yang
tidak pasti*.

### Batasan

- Netlist Cyclone V berasal dari Yosys, bukan Quartus. Tidak ada place &
  route, timing, atau constraint CDC.
- Netlist sky130 + OpenLane untuk salinan ini belum ada.
- Model metastabilitas memakai jendela 1 ns dan resolusi satu siklus. Model ini
  menguji fungsi, bukan MTBF.
- Pemeriksaan struktur membuktikan sambungan, bukan timing.
