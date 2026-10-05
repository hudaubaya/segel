# Audit baseline TT07

Ketiga baseline di `rtl/baseline/` diuji **apa adanya** dengan cocotb: tanpa
satu baris pun diubah, pada commit yang di-tapeout (lihat `docs/baselines.md`).
Tidak ada yang diperbaiki di sini; dokumen ini hanya mencatat temuan.
Perbaikan dibuat di salinan SEGEL yang terpisah, sementara baseline tetap apa
adanya. Saat ini F1, F2, F3, F5, F6, dan sinkronisasi reset sudah diperbaiki di
`rtl/cdc_fifo/` (lihat
[`docs/cdc_fifo.md`](cdc_fifo.md)).

## Ringkasan

| Baseline | Benar | Salah | Tidak ada |
|---|---|---|---|
| **SerDes #0200** | Sub-blok 6b/4b masing-masing berasal dari tabel standar; decoder adalah invers persis encoder-nya sendiri | Tabel encoder campuran kolom RD−/RD+ (15 byte menghasilkan word tidak valid, 6 di antaranya disparity −4); urutan bit serial salah; loopback TX→RX hanya 8/256 byte; `ser_out` tidak bisa keluar dari chip | Running disparity, kode K (termasuk K28.5), flag kode ilegal, flag galat disparity, penyelarasan word/comma |
| **CDC FIFO #0036** | Inti FIFO: tanpa data hilang/ganda/tertukar pada 24 rasio clock acak selama isi < penuh; `empty` benar; Gray 1 bit per langkah (RTL); `full` benar saat pointer read ≠ 0 | Wrapper hanya meneruskan 1 dari 4 bit data; `full` gagal saat pointer read tersinkron = 0, sehingga 32 data hilang tanpa tanda; reset satu domain membuat data basi terbaca atau data terbaca ulang | Reset lewat `rst_n` (memakai pin `uio`) |
| **CRC-8 #0901** | Netlist = model poly 0x07, init 0x00 untuk semua 65.536 pasangan (state, byte) | Hanya dokumentasi: "dua byte" (nyatanya satu byte per clock); label "CCITT" ambigu | RTL sumber dan testbench upstream |

Cara membaca label keyakinan: **[Pasti]** dibuktikan simulasi atau struktur
netlist; **[Kemungkinan Besar]** inferensi kuat dari kode; **[Menebak]** tidak
bisa dibuktikan dengan alat di repo ini.

## Metode

- Simulator Icarus Verilog 12.0, cocotb 1.8.1.
- **RTL**: sumber baseline apa adanya, toplevel testbench baru di
  `tb/audit/<baseline>/`. Test SerDes dan CDC FIFO juga membaca sinyal internal
  (mis. `serdes_inst.data_10b_encoded`, pointer Gray FIFO) tanpa mengubah desain.
- **Netlist tapeout (GL)**: `rtl/baseline/*/gl/*.v` dari repo shuttle
  `TinyTapeout/tinytapeout-07`, disimulasikan dengan model sel sky130_fd_sc_hd
  (`UNIT_DELAY=#1`, tanpa SDF). Hanya level pin. Test: `tb/audit/gl/`, dan
  `tb/crc8/` untuk CRC-8.
- **Model referensi**: `model/enc8b10b.py` (8b/10b IEEE 802.3 cl. 36) dan
  `model/crc8.py`. Keduanya punya self-test (`make test-model`).
  Self-test model 8b/10b memeriksa nilai K28.5/D.0.0/D.21.5/D.x.A7 yang
  umum dikutip, disparity setiap simbol, keunikan kode, serta tidak adanya
  comma atau run > 5 bit dalam 20.000 simbol acak.
- **Konvensi `expect_fail`**: setiap test memeriksa perilaku *yang benar*.
  Test untuk cacat yang sudah terkonfirmasi diberi `expect_fail=True` dan ID
  temuan (S1, F3, …). Suite tetap hijau selama cacat masih ada, dan menjadi
  merah kalau baseline berubah perilaku, sehingga dokumen ini perlu diperbarui.
  Setiap `expect_fail` gagal karena `AssertionError` dari assertion
  perilaku, bukan karena error testbench (diperiksa di log).
- Angka dalam dokumen ini berasal dari `tb/audit/*/audit_*.json` yang ditulis
  oleh test. Angka SerDes juga dicocokkan ulang dengan emulasi Python dari tabel
  `case` di RTL, dan hasilnya sama persis.

Menjalankan semuanya: `make test-audit` (termasuk dalam `make test`).

| Target | Isi |
|---|---|
| `make test-audit-serdes` | 16 test RTL SerDes |
| `make test-audit-cdc_fifo` | 10 test RTL CDC FIFO |
| `make test-audit-gl-serdes` | 2 test netlist SerDes |
| `make test-audit-gl-cdc_fifo` | 4 test netlist CDC FIFO |
| `make test-audit-gl-gray` | Glitch pointer Gray di netlist CDC FIFO (Verilog murni) |
| `make test-audit-struct-cdc_fifo` | Struktur synchronizer dan reset CDC FIFO setelah sintesis Yosys |
| `make test-crc8-gl` | 5 test netlist CRC-8 (sama dengan `tb/crc8`) |

---

## SerDes #0200 (`tt_um_serdes`)

Notasi: kode standar ditulis `abcdei fghj`, dengan `a` dikirim pertama. Word
internal DUT adalah `{temp_4b, temp_6b}`. Saya mengasumsikan literal di RTL
ditulis dengan MSB = `a` (6b) dan MSB = `f` (4b), sehingga word DUT = `{fghj,
abcdei}`. Asumsi ini memengaruhi angka S1 dan S7. Temuan S5 dan S6 tidak
bergantung pada asumsi ini.

### Yang benar

- **Setiap sub-blok yang dikeluarkan encoder adalah entri tabel standar untuk
  indeksnya**: 32/32 kode 6b dan 8/8 kode 4b. [Pasti] —
  `test_subblocks_are_standard`.
- **Decoder adalah invers persis encoder-nya sendiri**: 256/256 byte kembali
  utuh bila word dimasukkan dalam layout native. [Pasti] —
  `test_decoder_inverts_encoder_native`.
- Dengan framing yang benar dari luar (pulsa `par_en` tepat setiap 10 bit),
  aliran word native terdekode benar. [Pasti] — `test_framing_offset_zero`.

### Yang salah

**S1 — Tabel encoder bukan 8b/10b standar.** [Pasti]
`serdes_top.v:133-178` memakai satu tabel tetap:

| Sub-blok | Kolom RD− | Kolom RD+ | Netral |
|---|---|---|---|
| 6b (32 kode) | 12 | 2 (D.0, D.2) | 18 |
| 4b (8 kode) | 0 | 4 (x.0, x.3, x.4, x.7) | 4 |

- Dibandingkan dengan kolom RD− standar: 92/256 byte berbeda. Dibandingkan
  dengan kolom RD+: 107/256 berbeda.
- 15 byte menghasilkan word yang **bukan codeword valid** di RD mana pun.
- 6 byte bahkan berdisparity −4: `0x00 = 011000 0100`, `0x02`, `0x80`,
  `0x82`, `0xE0`, `0xE2`.
- Histogram disparity untuk 256 word: −4: 6, −2: 67, 0: 128, +2: 55.
- Test: `test_encoder_table_rd_minus`, `test_encoder_table_rd_plus`,
  `test_encoder_stats`.

**S5 — Urutan bit serial salah.** [Pasti] PISO mengirim LSB word lebih dulu
(`serdes_top.v:224-225`). Hasilnya urutan `i e d c b a j h g f`, padahal
standar `a b c d e i f g h j`. Contoh 0x5A: terkirim `0110101010`, standar
`0101100101`. Test: `test_serial_bit_order`.

**S6 — Loopback TX→RX rusak.** [Pasti] SIPO menggeser ke kiri, sehingga bit
pertama yang diterima menjadi MSB (`serdes_top.v:250`), sedangkan PISO
mengirim LSB dulu. Dengan kabel ideal dan framing ideal, hanya **8/256** byte
kembali benar. Test: `test_loopback`.

**S7 — Decoder hanya mengenal tabel encoder-nya sendiri.** [Pasti] Kode
standar dalam layout native salah didekode untuk 65/256 byte (kolom RD−) dan
105/256 byte (kolom RD+). Dalam urutan bit kabel standar, 254/256 salah.
Kode yang tidak dikenal jatuh ke `default` yang bernilai 0 (`serdes_top.v:283,
318`). Test: `test_decoder_standard_codes_native`,
`test_decoder_standard_wire_order`.

**S4 — `ser_out` tidak bisa keluar dari chip.** [Pasti]
- `project.v:23` menulis `wire ser_out = uio_out[0];`. Arah assignment ini
  terbalik: `uio_out[0]` tidak punya driver, dan di simulasi RTL bernilai `z`.
- `info.yaml` menetapkan `uio[1]` sebagai `ser_out`, tetapi `uio_out[1]` diikat
  0 (`project.v:40`).
- `uio_oe` diikat 0 untuk semua bit (`project.v:39`).
- Test: `test_serial_on_pin`, `test_gl_serial_on_datasheet_pin`.

**S11 — Perilaku RTL dan netlist berbeda di `uio_out[0]`.** [Pasti] Sintesis
menyatukan net `ser_out` dengan `uio_out[0]`. Akibatnya, di netlist, bit serial
memang muncul di `uio_out[0]` (0x5A → `0110101010`), sedangkan di RTL nilainya
`z`. Pin itu tetap tidak bisa dipakai untuk keluaran, karena:
- `uio_oe[0]` diikat 0 lewat sel `conb`;
- `uio[0]` juga dipakai sebagai `ser_in`.

Test: `test_gl_tx_reaches_uio_out0_with_oe_low`.

**S12 — Aliran serial kontinu tidak mungkin.** [Pasti, dari RTL]
- SIPO tidak menggeser pada siklus `par_en=1` (`serdes_top.v:247-250`), dan PISO
  tidak menggeser pada siklus load (`ser_en=1`, `serdes_top.v:220-221`).
- Setiap word butuh minimal satu siklus ekstra di kedua sisi. Selama siklus itu,
  `ser_out` menahan bit terakhir.
- Driver di testbench membutuhkan 15 siklus per word TX dan 15 siklus per word RX.

**S13 — TX dan RX tidak independen.** [Pasti, dari RTL] Satu pin `data_en`
mengendalikan keempat latch (8b dan 10b, baik TX maupun RX;
`serdes_top.v:18-24, 34-40, 65-71, 83-89`). Mengaktifkan satu arah ikut
mengubah latch di arah yang lain.

**S14 — Reset tidak konsisten dan dokumentasinya salah.** [Pasti]
- `data_10b_out` (encoder), `data_8b_out` (decoder), `ser_out` (PISO), dan
  `par_out` (SIPO) tidak di-reset. Simulasi menunjukkan `data_10b_encoded =
  xxxxxxxxxx` setelah reset sampai `ser_en` pertama.
- PISO dan SIPO memakai reset sinkron, blok lain reset asinkron.
- `docs/info.md` menyebut "synchronous reset (`rst`)" aktif tinggi. Di RTL
  resetnya `rst_n`, aktif rendah, dan sebagian besar asinkron.

**Catatan:** test upstream (`rtl/baseline/serdes_0200/test/test.py`) hanya
memeriksa `uo_out == 0` setelah reset. Lulusnya test itu tidak bermakna.

### Yang tidak ada

- **Running disparity (S2).** [Pasti] Tidak ada state RD. Pada 2.000 byte acak
  yang dibandingkan dengan encoding standar (RD dilacak, mulai RD−), 760
  simbol berbeda. Pada aliran 10.000 byte acak:
  - running digital sum hanyut ke −1830 (maksimum |RDS| = 1840), jadi tidak
    seimbang DC;
  - run terpanjang 6 bit, padahal standar maksimal 5;
  - pola comma (`0011111`/`1100000`) muncul di tengah data. Penerima standar
    akan salah menyelaraskan.

  Test: `test_encoder_running_disparity`, `test_encoder_stats`.
- **Kode K, termasuk K28.5 (S3).** [Pasti] Masukan hanya 8 bit data, tanpa
  flag kontrol. Byte 0xBC dikodekan sebagai D28.5 (`001110 1010`), bukan
  K28.5 (`001111 1010` / `110000 0101`). Test: `test_k28_5`.
- **Flag kode ilegal (S8).** [Pasti] Tidak ada keluaran error.
  `0000000000`, `1111111111`, `0000111111`, dan word DUT sendiri untuk 0x00
  (disparity −4) menghasilkan pin yang identik dengan dekode kode legal.
  Test: `test_decoder_flags_illegal_code`.
- **Flag galat disparity (S9).** [Pasti] D.1.1 bentuk RD− dikirim dua kali
  berturut-turut (yang kedua seharusnya bentuk RD+). Kedua keluaran identik
  (0x21) tanpa indikasi apa pun. Test: `test_decoder_flags_disparity_error`.
- **Penyelarasan word / deteksi comma (S10).** [Pasti] Framing ditentukan
  semata oleh waktu pulsa `par_en` dari luar. Dengan aliran yang tergeser
  3 bit, 40 word terdekode salah semua dan penerima tidak pernah kembali
  sinkron. Test: `test_word_alignment`.

---

## CDC FIFO #0036 (`tt_um_pa1mantri_cdc_fifo`)

Parameter dari wrapper: `DATA_WIDTH=4`, `ADDRESS_WIDTH=5`. Clock write dan read
berasal dari pin `ui_in[0]` dan `ui_in[2]`.

- **Inti** (`cdc_fifo` diinstansiasi langsung dengan parameter yang sama)
  diuji terpisah dari **wrapper** (lewat pin TT).
- Rasio clock diacak per segmen: periode 4–120 ns, fase acak, ditambah enam
  profil beban (seimbang, writer cepat, reader cepat, keduanya penuh, hanya
  write, hanya read).
- Scoreboard memeriksa urutan data, flag, `read_data` = kepala antrean selama
  `empty=0`, serta setiap perubahan pointer Gray sebelum dan sesudah
  sinkronisasi.

### Yang benar

- **Inti FIFO tidak menghilangkan, menggandakan, atau menukar data selama isi
  < penuh.** [Pasti] 24 rasio clock acak (T_write/T_read 0,10–4,52), isi
  dibatasi ≤ 29 oleh testbench:
  - 2.761 item ditulis dan dibaca, tidak ada galat scoreboard;
  - FIFO terkuras habis di akhir.

  Test: `test_core_random_ratios_below_full`.
- **`empty` benar.** [Pasti] Tidak pernah `empty=0` saat antrean kosong, dan
  `read_data` selalu sama dengan kepala antrean selama `empty=0`.
- **`full` benar saat pointer read ≠ 0.** [Pasti] Dengan pointer read = 5,
  tepat 31 write diterima lalu `full=1`, baik di RTL maupun netlist. Test:
  `test_core_capacity_read_ptr_nonzero`, `test_gl_capacity_read_ptr_nonzero`.
- **Pointer Gray berubah tepat 1 bit per langkah (RTL).** [Pasti]
  - 5.522 perubahan pada test dibatasi dan 6.342 pada test tak dibatasi,
    tanpa pelanggaran;
  - setiap nilai pasca-sinkronisasi adalah nilai Gray yang pernah ada di sumber.
- **Lewat pin, FIFO bekerja untuk bit data 0.** [Pasti] 932 item pada 12 rasio
  acak (RTL) dan 20 item (netlist) keluar utuh dan berurutan. Test:
  `test_top_random_ratios_bit0`, `test_gl_data_bit0`.
- `uo_out[3:2]`, `uio_out`, dan `uio_oe` selalu 0. Reset lewat
  `uio_in[0]`/`uio_in[1]` (aktif rendah) bekerja sesuai `docs/info.md`.

### Yang salah

**F1 — Wrapper hanya meneruskan bit data 0.** [Pasti]
`tt_um_pa1mantri_cdc_fifo.sv:28` menulis `assign write_data = ui_in[4];`. Bus
4 bit diisi 1 bit, sehingga bit 1–3 selalu 0. Padahal `info.yaml` memetakan
`ui[4..7]` ke `write_data0..3`.
- **Netlist:** `ui_in[5]`, `ui_in[6]`, dan `ui_in[7]` sama sekali tidak
  tersambung. Menulis 0..15 lalu membacanya kembali menghasilkan
  `0,1,0,1,…`.
- Test: `test_top_random_ratios_4bit`, `test_gl_data_4bit`.
- **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
  Lihat `docs/cdc_fifo.md`.

**F3 — `full` tidak naik saat pointer read tersinkron = 0; 32 data hilang
tanpa tanda.** [Pasti]
`cdc_fifo_write_state.sv:14` menulis `full = (write_address + 1 ==
read_address)`. Literal `1` tidak berukuran (32 bit), jadi penjumlahan
dihitung dalam 32 bit. Saat `write_address = 31`, hasilnya 32 ≠ 0, sehingga
`full` tetap 0 ketika pointer read (dalam domain write) bernilai 0.

Akibatnya:
- write ke-32 diterima, dan pointer write membungkus ke 0 = pointer read;
- FIFO tampak **kosong**, dan 32 item hilang tanpa tanda;
- write berikutnya menimpa data.

Kondisi ini terjadi setiap kali FIFO terisi penuh saat pointer read berada di
0, yaitu setelah reset dan sekali setiap 32 read.

Bukti:
- **Inti RTL setelah reset:** 40/40 write diterima, `full=0`, dan FIFO
  akhirnya terlihat berisi 8 item.
- **Netlist:** sama, 40/40 diterima dan `full=0`.
- **Uji acak tanpa batas isi:** galat pertama "isi=31 tapi full=0", dan pada
  akhir uji ada 96 item yang tidak terbaca.
- Test: `test_core_capacity_after_reset`, `test_core_random_ratios`,
  `test_gl_capacity_after_reset`.
- **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
  Lihat `docs/cdc_fifo.md`.

**F6 — Reset satu domain membuat isi FIFO tidak konsisten.** [Pasti]
`uio_in[0]` hanya mereset domain write dan `uio_in[1]` hanya domain read
(`tt_um_pa1mantri_cdc_fifo.sv:44-45`, `cdc_fifo.sv:51-91`). Kalau hanya satu
sisi yang direset saat FIFO berisi, pointer di sisi lain tetap di nilai lama.

Bukti (lewat pin TT; 6 item ditulis lalu 2 dibaca sebelum reset; data dibatasi
ke bit 0 agar tidak tercampur F1):
- **Reset domain write saja:** sisi read tetap `empty=0` dan **30 item basi**
  terbaca dari slot memori yang tidak berlaku lagi.
- **Reset domain read saja:** 6 item terbaca lagi, termasuk 2 yang **sudah
  dibaca sebelumnya** (duplikasi).
- Test: `test_top_write_domain_reset_empties_fifo`,
  `test_top_read_domain_reset_empties_fifo`.
- **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
  Lihat `docs/cdc_fifo.md`.

### Yang tidak ada / catatan

- **F2 — `rst_n` global diabaikan.** [Pasti] Reset hanya lewat `uio_in[0]` dan
  `uio_in[1]`. Ini sesuai `docs/info.md`, tetapi menyimpang dari konvensi Tiny
  Tapeout. Test: `test_top_rst_n_resets_fifo`.
  **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
- **F4 — Kapasitas 31, bukan 32.** [Pasti] Pointer tidak punya bit wrap,
  sehingga satu slot selalu kosong. Ini pilihan desain yang valid, tetapi tidak
  didokumentasikan.
- **F5 — Pointer Gray dibentuk kombinasional dari register biner**
  (`binary_to_gray`, `cdc_fifo_write_state.sv:25-30`,
  `cdc_fifo_read_state.sv:23-28`) dan langsung masuk ke flop pertama
  synchronizer. Ini bukan Gray yang diregister.
  - **Struktur:** [Pasti] setelah sintesis generik Yosys (`synth -flatten`),
    8 dari 10 bit masukan flop pertama synchronizer digerakkan gerbang
    (`$_XOR_`, `$_NOT_`, `$_NAND_`), bukan langsung oleh flop. Hanya MSB, yang
    sama di biner dan Gray, datang langsung dari flop. Test:
    `make test-audit-struct-cdc_fifo` (`tb/struct/check_cdc_regs.py`).
  - Simulasi netlist unit-delay (`make test-audit-gl-gray`, sampling 0,25 ns,
    3.978 perubahan pointer write dan 3.976 perubahan pointer read) tidak menunjukkan glitch multi-bit.
    Net yang dipantau selalu sama dengan `gray(biner)` di setiap tepi clock.
  - Unit delay tidak memodelkan skew nyata, jadi apakah glitch terjadi di
    silikon tidak bisa dibuktikan di sini. [Menebak]
  - Praktik umum adalah meregister pointer Gray di domain sumber.
  - **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
- **Deassertion reset (dari pin, asinkron) tidak disinkronkan** ke
  masing-masing clock.
  - **Struktur:** [Pasti] setelah sintesis Yosys, 0 dari 30 flop ber-reset
    menerima reset yang tersinkron ke domainnya; semuanya langsung dari pin.
    Test: `make test-audit-struct-cdc_fifo`.
  - **Dampak:** reset yang dilepas dekat tepi clock melanggar
    recovery/removal, sehingga flop bisa metastabil. [Kemungkinan Besar]
    risikonya rendah karena pointer mulai dari 0 dan langkah pertamanya hanya
    mengubah 1 bit. Namun kalau `increment` aktif saat reset dilepas, data
    bisa ditulis tanpa pointer ikut naik. Simulasi RTL tidak bisa
    memperlihatkannya.
  - **Status:** diperbaiki di `rtl/cdc_fifo/` (SEGEL); baseline tetap apa adanya.
- Test upstream hanya memeriksa `empty`/`full` setelah satu write, dan tidak
  memeriksa data.

---

## CRC-8 #0901 (`tt_um_aidenfoxivey`)

Satu-satunya artefak adalah netlist tapeout. Audit ini sama dengan
`make test-crc8-gl` (testbench `tb/crc8/`, rincian di `docs/crc8.md`).

### Yang benar

- **Netlist identik dengan model poly 0x07, init 0x00** (MSB dulu, tanpa
  refleksi, tanpa XOR akhir; CRC-8/SMBUS). [Pasti]
  - semua 65.536 pasangan (state, byte) dengan `en=1`;
  - hold saat `en=0`, untuk 256 state × 4 byte acak;
  - 20.000 siklus acak dengan `en`, `ena`, dan `uio_in[7:1]` acak;
  - reset asinkron;
  - check value `0xF4`.
- `uio_out` dan `uio_oe` selalu 0. `ena` dan `uio_in[7:1]` tidak berpengaruh.

### Yang salah (dokumentasi saja)

- `docs/info.md` menyebut "two bytes", padahal netlist menyerap **satu byte per
  clock** dari `ui_in`. [Pasti]
- Judul "CRC-8 CCITT" ambigu. Kalau yang dimaksud CRC-8/I-432-1 (ITU, XOR
  akhir 0x55, check 0xA1), netlist tidak menerapkan XOR akhir tersebut;
  keluarannya CRC-8/SMBUS. Keluaran netlist itu sendiri [Pasti]; maksud
  penulis [Menebak].
- `docs/info.md` menyuruh menjalankan `make` di `/test`, tetapi test itu tidak
  bisa diperoleh lagi.

### Yang tidak ada

- RTL sumber dan testbench upstream (repo upstream tidak dapat diakses; lihat
  `docs/baselines.md`).

---

## Batasan audit

- Semua bukti berbasis simulasi. Tidak ada pembuktian formal dan tidak ada
  timing (GL memakai unit delay tanpa SDF).
- Model sel dari `google/skywater-pdk-libs-sky130_fd_sc_hd@28c101fc`, bukan
  open_pdks `cd1748bb` yang dipakai tapeout.
- Angka S1/S7 bergantung pada interpretasi urutan bit literal di RTL SerDes
  (lihat notasi di atas). Temuan S2–S6 dan S8–S14 tidak bergantung pada
  interpretasi itu.
- Uji acak CDC FIFO memakai seed tetap dan rasio clock acak per segmen, tanpa
  jitter di dalam segmen. Metastabilitas tidak dimodelkan.
