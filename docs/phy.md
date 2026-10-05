# PHY serial (`rtl/phy/`)

PHY serial SEGEL terdiri dari:
- 8b/10b dengan flag kode ilegal dan galat disparity;
- serializer/deserializer source-synchronous (clock diteruskan);
- penyelarasan comma K28.5;
- CDC FIFO 9 bit (8 data + flag K);
- framing dengan CRC-8.

Dasarnya adalah audit baseline TT07 di [`docs/baseline_audit.md`](baseline_audit.md)
(temuan S1–S14 untuk SerDes #0200).

## Struktur

```
          domain sys_clk                 domain tx_clk                kanal
tx_data ─► phy_framer ─► cdc_fifo 9b ─► phy_serializer (enc8b10b) ─► tx_ser, tx_clk_out = ~tx_clk
           (crc8)                                                          │
                                                                           ▼  (PHY lawan)
          domain sys_clk                 domain rx_clk = clock yang diteruskan
rx_data ◄─ phy_deframer ◄─ cdc_fifo 9b ◄─ dec8b10b ◄─ phy_comma_align ◄─ phy_deserializer ◄─ rx_ser, rx_clk
           (crc8)
```

| File | Isi |
|---|---|
| `rtl/phy/phy_8b10b_tables.vh` | Tabel 5b/6b dan 3b/4b bersama (dari baseline, dengan perbaikan) |
| `rtl/phy/enc8b10b.v` | Encoder kombinasional dengan running disparity, kode K, `k_err` |
| `rtl/phy/dec8b10b.v` | Decoder kombinasional: `illegal`, `disp_err`, RD baru |
| `rtl/phy/phy_serializer.v` | FIFO → 8b/10b → PISO, MSB (`a`) dulu, IDLE saat FIFO kosong, clock diteruskan |
| `rtl/phy/phy_deserializer.v` | SIPO 10 bit di clock yang diteruskan |
| `rtl/phy/phy_comma_align.v` | Penyelarasan word dengan comma, 10 geseran bit |
| `rtl/phy/phy_framer.v`, `phy_deframer.v` | Frame SOF/payload/CRC-8/EOF, status per frame, counter galat |
| `rtl/phy/phy.v` | Top: tiga domain clock, dua `cdc_fifo` 9 bit, reset synchronizer per domain |
| `rtl/phy/phy_symbols.vh`, `sources.mk` | Konstanta simbol; daftar sumber untuk Makefile |
| `rtl/crc8/crc8.v` | CRC-8 yang sudah ada, ditambah port `clr` (clear sinkron per frame) |
| `rtl/cdc_fifo/*.sv` | CDC FIFO SEGEL (turunan baseline #0036 dengan F1–F6 diperbaiki), dipakai dengan `DATA_WIDTH = 9` |

## Baseline SerDes #0200: apa yang dipakai, apa yang ditulis ulang

Audit menunjukkan hampir seluruh baseline SerDes salah atau tidak ada. Keputusan per
bagian:

| Bagian baseline | Temuan audit | Keputusan | Alasan |
|---|---|---|---|
| Tabel 6b encoder (`serdes_top.v:145-176`) | S1: kolom campuran | **Dipakai** sebagai kolom RD−, **2 entri diperbaiki** (D.0 `011000`→`100111`, D.2 `010010`→`101101`) | 30/32 entri sudah sama persis dengan kolom RD− standar; hanya D.0 dan D.2 memakai bentuk RD+ |
| Tabel 4b encoder (`serdes_top.v:134-141`) | S1 | **Dipakai apa adanya** sebagai kolom RD+ | Kedelapan entri persis kolom RD+ standar; bentuk RD− = komplemen untuk y = 0, 3, 4, 7 |
| Pemilihan kolom / running disparity | S1, S2: tidak ada RD | **Ditulis ulang** | Tanpa RD, sinyal tidak seimbang DC, run > 5 bit, dan comma palsu muncul di data |
| Kode K | S3: tidak ada | **Ditulis baru** | K28.0–7, K23.7, K27.7, K29.7, K30.7; K28.5 dipakai sebagai comma/IDLE |
| D.x.A7 | S1 | **Ditulis baru** | Baseline tidak punya bentuk alternatif A7 |
| Decoder (`serdes_top.v:256-322`) | S7, S8, S9: hanya invers tabel sendiri, kode tak dikenal → 0 tanpa tanda | **Ditulis ulang** | Decoder harus menerima kedua kolom, A7, K, serta menandai kode ilegal dan galat disparity |
| PISO (`serdes_top.v:205-229`) | S5, S12: LSB dulu, satu siklus mati per word | **Ditulis ulang** | Urutan standar `a` dulu; aliran kontinu 10 bit per 10 clock |
| SIPO (`serdes_top.v:232-254`) | S6, S12 | **Ditulis ulang** | Arah geser konsisten dengan PISO, tanpa siklus mati |
| Framing word dari pulsa `par_en` luar | S10: tidak ada penyelarasan | **Ditulis baru** | Penyelarasan comma K28.5 |
| Latch `data_en` bersama | S13 | **Tidak dipakai** | TX dan RX sepenuhnya independen |
| Reset campuran sinkron/asinkron | S14 | **Tidak dipakai** | Reset asinkron per domain lewat `reset_synchronizer` |
| Wrapper TT `project.v` | S4, S11 | **Tidak dipakai** | `ser_out` tidak pernah keluar chip. Pinout TT untuk PHY belum dibuat |

Baseline di `rtl/baseline/serdes_0200/` tidak diubah. Kedua tabel yang dipakai disalin
ke `phy_8b10b_tables.vh` dengan komentar asal baris.

CDC FIFO memakai salinan SEGEL di `rtl/cdc_fifo/` (baseline #0036 + perbaikan F1–F6 dan
sinkronisasi reset, `docs/cdc_fifo.md`), tanpa perubahan kode. Lebarnya 9 bit lewat
parameter `DATA_WIDTH`. Baseline #0036 apa adanya tidak dipakai karena salah pada
`full` (F3) dan reset satu domain (F6). CRC-8 memakai `rtl/crc8/crc8.v` (perilaku baseline
#0901, poly 0x07, init 0x00) dengan tambahan port `clr`. Wrapper TT CRC-8 mengikat `clr = 0`,
jadi perilakunya tidak berubah.

## Format di kabel

- 8b/10b IEEE 802.3 cl. 36, kode `abcdei fghj`, bit `a` dikirim pertama. RD awal RD−.
- Simbol:

  | Simbol | Kode | Arti |
  |---|---|---|
  | IDLE | K28.5 (0xBC) | Comma. Dikirim saat FIFO TX kosong dan 2× setelah setiap EOF. Dibuang RX |
  | SOF | K27.7 (0xFB) | Awal frame |
  | EOF | K29.7 (0xFD) | Akhir frame |

- Frame: `SOF, payload (≥ 1 byte), CRC-8(payload), EOF, IDLE, IDLE`. CRC-8 memakai poly 0x07,
  init 0x00, tanpa refleksi, tanpa XOR akhir. RX menghitung CRC atas payload + byte CRC
  dan mensyaratkan sisa 0.
- IDLE boleh muncul di tengah frame (FIFO TX kosong karena sisi sistem lambat) dan
  bersifat transparan.

## Antarmuka (`phy.v`)

| Port | Domain | Keterangan |
|---|---|---|
| `rst_n` | asinkron | Mereset ketiga domain; dilepas sinkron per domain |
| `tx_data`, `tx_valid`, `tx_last`, `tx_ready` | `sys_clk` | Payload; `tx_last` pada byte terakhir |
| `rx_data`, `rx_valid`, `rx_last` | `sys_clk` | Payload, tanpa backpressure. Byte CRC tidak keluar |
| `rx_err_{crc,code,disp,ctrl,frame}` | `sys_clk` | Status frame, valid bersama `rx_last` |
| `cnt_{ok,crc,code,disp,ctrl,frame,lost}` | `sys_clk` | Counter 16 bit jenuh: frame OK, CRC salah, kode ilegal, galat disparity, simbol K tak terduga, galat framing, penanda simbol hilang |
| `rx_locked`, `rx_overflow` | `sys_clk` (tersinkron) | Aligner terkunci; FIFO RX pernah meluap (sticky) |
| `tx_clk` → `tx_ser`, `tx_clk_out` | `tx_clk` | Satu bit per `tx_clk`; `tx_clk_out = ~tx_clk` |
| `rx_clk`, `rx_ser` | `rx_clk` | Clock dan data dari PHY lawan |

Hubungan clock: ketiga domain bebas frekuensinya, dengan dua syarat.
- **RX:** periode `sys_clk` < 10 × periode `rx_clk`. Deframer mengonsumsi satu simbol
  per siklus `sys_clk`, sedangkan satu simbol datang setiap 10 `rx_clk`.
- **TX:** tidak ada syarat. Kalau `sys_clk` lebih lambat, IDLE disisipkan di tengah frame.

Kalau syarat RX dilanggar, simbol yang dibuang diganti penanda `LOST` begitu FIFO
punya tempat, `rx_overflow = 1`, dan frame yang terkena berstatus `rx_err_frame`. Frame
yang terkena tidak pernah keluar dengan status OK.

### Clock yang diteruskan

Data berubah di tepi naik `tx_clk`. Penerima mengambil sampel di tepi naik
`tx_clk_out = ~tx_clk`, yaitu di tengah bit. Margin terhadap skew clock–data adalah
±½ bit dikurangi setup/hold flop.

Di silikon atau FPGA, `~tx_clk` sebagai gerbang biasa **tidak boleh** dipakai apa
adanya. Clock harus dikeluarkan lewat sel DDR/clock-forwarding (mis. ODDR) dan
diberi constraint timing I/O. Itu belum dikerjakan.

### Penyelarasan comma

Comma 7 bit `0011111`/`1100000` hanya muncul di posisi `abcdeif` kode K28.1/5/7, dan
tidak pernah muncul di aliran data yang valid (diperiksa di self-test model).
`bitcnt` 0..9 berjalan bebas. Geseran bit apa pun hanya menentukan nilai `bitcnt`
saat comma terlihat (`phase`).

- **Belum terkunci:** comma pertama langsung mengunci.
- **Sudah terkunci:** comma di phase lain menjadi *kandidat*. Realign hanya terjadi
  kalau word **berikutnya** (10 bit kemudian) di phase kandidat juga comma. Kalau
  tidak, kandidat gugur.
  - Galat satu bit tidak bisa membuat comma di dua word berurutan, jadi tidak pernah
    menggeser framing.
  - Slip bit nyata terkonfirmasi oleh dua IDLE berurutan setelah EOF.

Saat (re)align, RD decoder diambil dari bentuk comma itu sendiri.

## Verifikasi

`make test-phy-units test-phy test-phy-synth test-phy-fifo-struct` (bagian dari `make test`):

| Test | Isi | Hasil |
|---|---|---|
| `test_encoder_exhaustive` | 256 data + 12 K × 2 RD = model `model/enc8b10b.py`; 488 permintaan K tidak sah → `k_err` | lulus |
| `test_decoder_exhaustive` | 1024 kode × 2 RD: data, K, `illegal` (1120), `disp_err` (392), RD baru = model | lulus |
| `test_align_all_shifts` | 10 geseran bit → 10 phase berbeda, phase = phase₀ + geseran, semua word benar | lulus |
| `test_align_false_comma` | Comma palsu tunggal, atau dua comma palsu di phase sama yang tidak berurutan → tidak realign; slip 3 bit → realign tepat di comma kedua berurutan | lulus |
| `test_loopback_shifts` | Dua PHY saling terhubung; geseran kanal 0..9 + 4 acak; 2×12 frame per geseran utuh, tanpa galat; phase kunci B mencakup 10 posisi | lulus |
| `test_clock_ratios` | 8 konfigurasi periode TX/RX/sistem acak (bilangan prima ps, rasio sistem/RX 0,29–3,3), skew dan tunda kanal 0–0,35 bit; 2×20 frame utuh per konfigurasi | lulus |
| `test_rate_limits` | `sys_clk` TX 15× `tx_clk` (IDLE di tengah frame) → semua utuh; `sys_clk` RX 25× `rx_clk` selama 40 µs → overflow ditandai, frame terkena tidak pernah OK, link pulih tanpa reset | lulus |
| `test_bit_errors` | 300 galat satu bit di kanal A→B (lalu lintas frame terus-menerus) | lihat di bawah |
| `test-phy-synth` | Yosys `synth -flatten`, `check -assert` | 3721 sel, 903 flop |
| `test-phy-fifo-struct` | `cdc_fifo` 9 bit: synchronizer Gray langsung dari flop, reset tersinkron | lulus |

Bersihnya setiap loopback diperiksa dari payload yang identik, semua `rx_err_*` = 0,
`cnt_ok` = jumlah frame, semua counter galat = 0, dan tidak ada overflow.

### Injeksi galat bit

Satu bit dibalik di kanal, dengan jeda 300–900 bit antar injeksi. Hasil `make test-phy` dengan seed 2026
(`tb/phy/phy_bit_errors.json`):

| | Jumlah |
|---|---|
| Galat terdeteksi (minimal satu counter galat naik) | **300/300** |
| …ditandai kode ilegal | 115 |
| …ditandai galat disparity | 221 |
| …ditandai simbol K tak terduga | 5 |
| …ditandai CRC salah | 241 |
| …ditandai galat framing | 36 |
| Terdeteksi sebagai **kode ilegal atau CRC** | **272/300** |
| Frame berstatus OK | 428, semuanya identik dengan yang dikirim |
| Realign akibat galat | 0 |

Satu galat bisa memicu beberapa penanda.

**Galat satu bit tidak selalu terdeteksi sebagai "kode ilegal atau galat CRC".**
28/300 hanya tertangkap sebagai galat disparity, simbol K tak terduga, atau galat
framing. Contoh: bit yang dibalik mengubah kode menjadi kode sah untuk RD lawan, atau
mengubah SOF/EOF sehingga batas frame rusak. Semuanya tetap terdeteksi, dan tidak ada
frame rusak yang lolos berstatus OK. Tetapi kategori "kode ilegal atau CRC" saja tidak
cukup untuk menangkap semuanya; galat disparity dan framing harus ikut diperiksa.

Test mensyaratkan:
1. setiap injeksi menaikkan minimal satu counter galat;
2. setiap frame berstatus OK identik dengan frame yang dikirim (dicocokkan lewat nomor
   urut di payload);
3. `realign_cnt = 0`;
4. 60 µs tanpa injeksi setelahnya menghasilkan ≥ 10 frame OK tanpa galat baru, yaitu
   link tetap hidup.

Syarat (3) dan (4) ditambahkan setelah versi pertama aligner gagal. Saat itu kandidat
realign tidak kedaluwarsa, dan TX tidak mengirim IDLE saat lalu lintas padat. Dua
comma palsu dari dua galat terpisah menggeser framing, dan link tidak pernah pulih.
Versi pertama test tetap lulus karena hanya mengecek deteksi. Regresinya sekarang
dijaga oleh `test_align_false_comma` (terbukti gagal pada aligner lama) dan syarat
(3)–(4).

## Keterbatasan

- **Belum ada state machine kehilangan sinkronisasi.** Aligner tidak pernah melepas
  kunci; ia hanya realign lewat dua comma berurutan. Galat yang berkepanjangan menghasilkan
  banyak kode ilegal sampai pasangan IDLE berikutnya.
- **Frame panjang tanpa IDLE** tidak bisa realign di tengah frame. Pemulihan menunggu
  celah antar frame.
- **Kanal di simulasi ideal**: tunda dan skew tetap, tanpa jitter, tanpa metastabilitas.
  Belum ada sintesis ke sky130/FPGA, analisis timing, atau constraint I/O.
- **RX tanpa backpressure**: syarat periode `sys_clk` < 10 × `rx_clk` wajib dipenuhi
  pengguna. Di bawah overload terus-menerus, hampir semua slot FIFO terisi penanda
  `LOST`, sehingga link praktis berhenti, tetapi tidak pernah mengeluarkan data rusak
  berstatus OK.
- CRC-8 menjamin deteksi semua burst ≤ 8 bit di dalam frame. Galat yang lebih besar
  lolos dengan peluang ±1/256 per frame rusak, kecuali bila 8b/10b menandainya lebih
  dulu.
- Belum ada wrapper Tiny Tapeout (pinout) untuk PHY.
- Uji di FPGA (DE10-Nano, clock diteruskan lewat DDIO, SDC, sweep BER):
  [`docs/phy_howto.md`](phy_howto.md). Belum ada hasil papan.
