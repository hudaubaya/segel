# Uji loopback PHY di DE10-Nano: langkah untuk tim

Proyek ini ada di `fpga/phy_loopback/`. Isinya lapisan fisik SEGEL (`rtl/phy/`, [docs/phy.md](phy.md)) di DE10-Nano, tanpa kriptografi:
- PLL domain TX;
- pin GPIO untuk clock dan data;
- generator dan pemeriksa PRBS;
- register yang dibaca lewat JTAG-to-Avalon Master;
- SDC;
- skrip System Console untuk sweep laju;
- `sw/ber.py` untuk menghitung BER.

> **Status: belum pernah dikompilasi Quartus dan belum pernah dijalankan di papan.**
> Lingkungan pengembangnya tidak punya Quartus maupun DE10-Nano. Dokumen ini tidak
> memuat satu pun hasil papan atau hasil timing.
>
> Yang sudah diverifikasi di repo (`make test-fpga-loopback test-fpga-scripts`):
> - Simulasi Icarus top FPGA, dengan model perilaku untuk PLL, DDIO, dan JTAG master, pada ~25 dan ~5 Mbit/s.
> - SDC, `create_project.tcl`, `ber_sweep.tcl`, dan `build_all.sh` dijalankan di
>   `tclsh` dengan mock perintah Quartus/System Console.
>
> Mock SDC mencocokkan pola nama dengan daftar register hasil elaborasi Yosys. Daftar
> itu hanya **pendekatan** konvensi nama Quartus. Jadi langkah pemeriksaan di bagian
> [Pemeriksaan timing](#4-pemeriksaan-timing-wajib-per-revisi) wajib dikerjakan.
> Hasil pertama di papan dicatat oleh tim, dan sumbernya disebutkan.

## 1. Yang dibutuhkan

- **DE10-Nano.** Device: 5CSEBA6U23I7.
- **Quartus Prime Lite atau Standard ≥ 18.1** dengan dukungan Cyclone V. Quartus Pro tidak mendukung Cyclone V.
  - `qsys-script`, `qsys-generate`, `quartus_sh`, `quartus_sta`, dan `system-console` harus ada di `PATH`.
- **Kabel USB mini-B** ke USB-Blaster II on-board.
- **Dua kabel jumper female-female** dengan panjang sama, sependek mungkin (≤ 10 cm).
  - Catat panjangnya; nilai itu dipakai di SDC (bagian 6).
- Python 3 untuk `sw/ber.py`.

## 2. Pin

Semua sinyal link ada di header **GPIO 1** dan di satu bank I/O (4A), sehingga keempatnya memakai I/O standard dan tegangan yang sama (3.3-V LVTTL).

| Sinyal | Port top | GPIO | Pin FPGA | Header (JP7) | Arah |
|---|---|---|---|---|---|
| Clock RX (diteruskan) | `PHY_RX_CLK` | GPIO_1[0] | **Y15** (CLKp) | pin 1 | masuk |
| Data RX | `PHY_RX_DAT` | GPIO_1[4] | AG28 | pin 5 | masuk |
| Clock TX (diteruskan) | `PHY_TX_CLK` | GPIO_1[5] | AF28 | pin 6 | keluar |
| Data TX | `PHY_TX_DAT` | GPIO_1[7] | AF27 | pin 8 | keluar |
| 50 MHz | `FPGA_CLK1_50` | — | V11 | — | masuk |
| Reset | `KEY[0]` | — | AH17 | — | masuk, aktif rendah |
| LED | `LED[7:0]` | — | W15 AA24 V16 V15 AF26 AE26 Y16 AA23 | — | keluar |

**Pengkabelan loopback (satu papan).** Pasang dua jumper:
- **pin 6 → pin 1** (clock);
- **pin 8 → pin 5** (data).

Untuk uji dua papan, TX papan A masuk ke RX papan B dengan pin yang sama, dan GND kedua papan disambung (pin 12 atau 30).

**Mengapa pin ini.**
- **Clock RX di pin clock khusus.** Clock yang diteruskan masuk lewat pin input clock khusus, sehingga langsung masuk jaringan clock global tanpa routing umum. Akibatnya delay sisipan kecil dan stabil.
  - Pin GPIO yang terhubung ke input clock khusus (CLKp) ada tiga:
    - **GPIO_0[0] = V12**;
    - **GPIO_0[16] = D12**;
    - **GPIO_1[0] = Y15**.
  - Pasangan CLKn-nya adalah GPIO_0[2] = W12, GPIO_0[18] = C12, dan GPIO_1[2] = AA15. Pin GPIO_0[3] = D11, GPIO_0[25] = W11, dan GPIO_0[34] = AA13 juga input clock (n).
  - Y15 dipilih karena semua pin lain di bank 4A di header yang sama tersedia untuk data dan clock TX.
- **Data di bank yang sama dengan clock RX** (4A), dan bukan pin CLKn pasangan Y15 (AA15 dibiarkan kosong).
- **TX di bank yang sama.** Clock dan data TX memakai bank yang sama dan berdekatan di header, sehingga panjang jumpernya bisa sama.

**Sumber dan tingkat keyakinan.**

| Klaim | Sumber | Keyakinan |
|---|---|---|
| Nomor pin FPGA untuk setiap sinyal DE10-Nano | Repo resmi Intel [`intel/de10-nano-hardware`](https://github.com/intel/de10-nano-hardware) @`9b5fc81`, `scripts/create_quartus_de10-nano-base.tcl` (MIT) | [Pasti] |
| Pin mana yang input clock khusus | Basis data Cyclone V proyek [Mistral](https://github.com/Ravenslofty/mistral) @`d509238` (`data/sx120f-p2p.txt`, `sx120f-pkg.txt`, die 5CSEBA6, paket U23). Pemeriksaan silang: ketiga pin `FPGA_CLK*_50` (V11, Y13, E11) muncul di daftar yang sama | [Kemungkinan Besar] — bukan dokumen Intel |
| Bank I/O | Basis data Mistral yang sama | [Kemungkinan Besar] |
| Nomor pin header (GPIO_x[0..9] = pin 1–10, 5 V = pin 11, GND = pin 12, …) | Ingatan tentang tata letak header Terasic | [Kemungkinan Besar] |

**Sebelum memasang jumper:**
1. Cocokkan kolom "Header" dengan gambar header GPIO di *DE10-Nano User Manual*. Manual itu tidak bisa diunduh dari lingkungan pengembang.
2. Konfirmasi fungsi pin Y15 di Pin Planner Quartus: kolom fungsi harus memuat `CLK…p`.

## 3. Membangun

```sh
cd fpga/phy_loopback
./scripts/build_all.sh            # semua revisi; atau: ./scripts/build_all.sh r25
```

Langkah yang dijalankan skrip itu (bisa juga dijalankan manual):

1. `cd qsys && qsys-script --script=make_phy_jtag.tcl` membuat `phy_jtag.qsys`, berisi JTAG-to-Avalon Master dan Avalon-MM bridge yang diekspor sebagai `avmm_*`.
2. `qsys-generate phy_jtag.qsys --synthesis=VERILOG --output-directory=phy_jtag`.
3. `cd quartus && quartus_sh -t create_project.tcl` membuat `phy_loopback.qpf` dengan empat revisi:

   | Revisi | `TX_SEL` | tx_clk nominal | Rasio terhadap 50 MHz |
   |---|---|---|---|
   | `phy_loopback_r05` | 0 | 4,989919 MHz | 99/992 |
   | `phy_loopback_r10` | 1 | 9,979839 MHz | 99/496 |
   | `phy_loopback_r20` | 2 | 19,959677 MHz | 99/248 |
   | `phy_loopback_r25` | 3 | 24,750000 MHz | 99/200 |

   Satu bit per siklus tx_clk, jadi laju bit = frekuensi tx_clk. Rasio terhadap 50 MHz sengaja dibuat tidak sederhana. Fase tx_clk terhadap clock sistem baru berulang setiap 200–992 siklus sistem, sehingga lintasan CDC melewati semua hubungan fase.
4. `quartus_sh --flow compile phy_loopback -c <revisi>` untuk setiap revisi.
5. `quartus_sta -t ../scripts/sta_checks.tcl phy_loopback <revisi>` menulis laporan `output_files/<revisi>.segel.*.rpt` (bagian 4).

Satu revisi per laju dipilih alih-alih rekonfigurasi PLL saat runtime. Alasannya, setiap revisi punya PLL yang sederhana dan SDC yang tepat untuk lajunya. IP rekonfigurasi PLL juga tidak bisa diuji tanpa Quartus.

## 4. Pemeriksaan timing (wajib, per revisi)

Hasil yang tidak lolos pemeriksaan ini tidak boleh dipakai untuk mengukur BER.

| Laporan | Di mana | Yang harus terlihat |
|---|---|---|
| **Ignored Constraints** | `*.segel.ignored.rpt`, atau Timing Analyzer → Reports → Diagnostic → Report Ignored Constraints | **Kosong.** Satu baris saja di sini berarti ada constraint SDC yang tidak berlaku, biasanya karena pola nama tidak cocok |
| Pesan `SEGEL SDC` | Compilation Report → Timing Analyzer → Messages | **Tidak ada** critical warning `SEGEL SDC: pola untuk … tidak cocok`. Pesan info `tx_clk = …, periode … ns` harus ada |
| **Unconstrained Paths** | `*.segel.ucp.rpt`, atau Report Unconstrained Paths | Semua kategori **0**: illegal clocks, unconstrained clocks, input/output ports, input/output port paths |
| `check_timing` | `*.segel.check.rpt` | Tidak ada clock tanpa definisi, port tanpa delay, atau loop kombinasional |
| **Clock Transfers (CDC)** | `*.segel.transfers.rpt` | Hanya pasangan berikut. Semuanya dibatasi lewat `set_max_delay`/`set_max_skew` atau `set_false_path` di SDC bagian CDC, bukan lewat `set_clock_groups`. Pasangan lain berarti ada lintasan lintas domain yang tidak dikenal |
| **Metastability** | `*.segel.meta.rpt` | Semua synchronizer dikenali sebagai rantai 2 flop (lihat daftar di bawah). Catat MTBF terburuk |
| **CDC (Design Assistant)** | Compilation Report → Design Assistant (aktif karena `ENABLE_DRC_SETTINGS ON`) | Tidak ada pelanggaran aturan clock domain crossing, kecuali yang dijelaskan di tabel CDC bagian 6. Nama dan nomor aturan berbeda antar versi Quartus [Kemungkinan Besar], jadi catat versi yang dipakai |
| **Max Skew** | `*.segel.skew.rpt` | 8 bus Gray (4 pointer FIFO, 4 counter lintas domain), semuanya slack ≥ 0 |
| Slack | `*.segel.{setup,hold,recovery,removal}.*.rpt` | ≥ 0 di semua corner. `sta_checks.tcl` keluar 1 kalau ada yang negatif |
| PLL | Fitter → Resource Section → PLL Usage Summary | Frekuensi keluaran aktual. Catat; bandingkan dengan `tx_clk_hz` hasil ukur di CSV |
| Clock RX | Fitter → Resource Section → Global & Other Fast Signals | `PHY_RX_CLK` masuk lewat pin clock khusus, tanpa routing umum |
| Register I/O | Fitter → Resource Section → Input Pins / Output Pins, kolom "Input/Output Register" | `PHY_RX_DAT` dan `PHY_TX_DAT` memakai register di I/O (`FAST_INPUT/OUTPUT_REGISTER`). Juga periksa Fitter → **Ignored Assignments** |

Pasangan clock transfer yang diharapkan:

| Dari → Ke | Isi |
|---|---|
| `clk50 → tx_clk` | Pointer tulis FIFO TX, memori FIFO TX, sinkron `RAW_MODE` |
| `tx_clk → clk50` | Pointer baca FIFO TX, counter siklus `tx_clk` |
| `rx_clk → clk50` | Pointer tulis FIFO RX, memori FIFO RX, status aligner, `raw_locked`, counter BERT |
| `clk50 → rx_clk` | Pointer baca FIFO RX, sinkron `RAW_MODE` |
| `tx_clk → tx_fwd_clk` | Data keluar `PHY_TX_DAT` (output delay) |
| `rx_virt → rx_clk` | Data masuk `PHY_RX_DAT` (input delay) |
| `altera_reserved_tck ↔ clk50` | Di dalam IP JTAG (constraint IP + `set_clock_groups`) |

Synchronizer yang diharapkan muncul di laporan Metastability:
- `reset_synchronizer`: sys/tx/rx di phy, `u_rst_sys`, `u_rst_tx`, `u_rst_rxr`, dan di kedua FIFO;
- pointer FIFO: `write_address_sync`, `read_address_sync`;
- status: `u_phy|u_sync_status`, `u_sync_lock`, `u_sync_raw`, `u_sync_rawrx`;
- counter lintas domain: `u_fm|u_sync`, `u_cnt_*|u_sync`.

Kalau satu pola SDC tidak cocok, cari nama yang benar di Timing Analyzer (`Name Finder`, filter Registers), perbaiki pola di `phy_loopback.sdc`, lalu kompilasi ulang. Pola diasumsikan memakai format `entity:instance|…|reg[i]`, dengan `*` cocok melintasi `|`.

## 5. Menjalankan sweep laju dan menghitung BER

```sh
cd fpga/phy_loopback/scripts
system-console -cli --script=ber_sweep.tcl -- detik=60 csv=ber_sweep.csv
python3 ../../../sw/ber.py ber_sweep.csv --json ber_sweep.json
```

Kalau versi System Console yang dipakai tidak meneruskan argumen ke `argv`, jalankan
`system-console`, lalu di konsolnya:
`set ::segel_args {detik=60 csv=ber_sweep.csv}; source ber_sweep.tcl`.

| Opsi | Default | Arti |
|---|---|---|
| `detik` | 10 | Lama setiap pengukuran |
| `revs` | `r05,r10,r20,r25` | Revisi (laju) yang dijalankan |
| `modes` | `raw,framed` | Mode per revisi |
| `sof_dir` | `../quartus/output_files` | Lokasi SOF |
| `download` | 1 | 0 = jangan unduh SOF (pakai yang sudah ada di FPGA) |
| `csv` | `ber_sweep.csv` | Ditambahkan (append); header ditulis kalau file baru |

Untuk setiap revisi, skrip mengunduh SOF lalu menjalankan dua mode.

**Mode `raw` (BER kanal).**
- Bit PRBS-31 (x³¹ + x²⁸ + 1) dikirim langsung ke pin, tanpa 8b/10b.
- Checker BERT di domain `rx_clk` menyinkronkan diri setelah 64 bit cocok, lalu membandingkan dengan generator lokal. Setiap bit salah dihitung satu kali.
- Kalau ≥ 16 galat terjadi dalam 64 bit, sinkronisasi dianggap hilang (`raw_loss`), dan baris itu tidak valid.
- PHY ditahan reset selama mode ini.

**Mode `framed` (frame dan deteksi).**
- Frame PHY berisi 4 byte seed + 60 byte PRBS-31.
- Menghasilkan: frame terkirim/diterima/bertanda, counter PHY (CRC, kode ilegal, disparity, simbol K, framing, simbol hilang), dan pelanggaran simbol per simbol.

**Perbedaan kedua mode.** Kolom "BER" di baris `framed` **bukan BER**.
- Simbol yang ditandai galat dibuang oleh PHY, sehingga sisa frame bergeser.
- Di simulasi, 6 galat satu bit menghasilkan ±700 "bit salah" payload.
- BER kanal selalu diambil dari baris `raw`.

Keluaran `sw/ber.py` per baris:
- BER;
- batas atas satu sisi 95% (Poisson);
- FER dan jumlah frame hilang;
- pelanggaran per simbol;
- peringatan bila counter jenuh, lock atau sinkron hilang, `rx_overflow = 1`, atau `tx_clk` terukur menyimpang > 1000 ppm dari nominal.

Dengan 0 galat, klaim yang sah hanya "**BER < batas atas**". Waktu ukur minimum agar batas atas 95% di bawah target (0 galat, ≈ 3 / jumlah bit):

| Target BER | ~5 Mbit/s | ~10 Mbit/s | ~20 Mbit/s | ~25 Mbit/s |
|---|---|---|---|---|
| < 10⁻⁹ | 10 menit | 5 menit | 2,5 menit | 2 menit |
| < 10⁻¹⁰ | 1,7 jam | 50 menit | 25 menit | 20 menit |
| < 10⁻¹² | 7 hari | 3,5 hari | 42 jam | 34 jam |

Counter PHY 16 bit (jenuh di 65535) dan `bit_errors` 32 bit (jenuh) bisa penuh pada pengukuran panjang yang banyak galatnya. `ber.py` memberi peringatan dalam kasus itu. Counter `raw_*` dan jumlah bit 64 bit.

### Peta register (JTAG-to-Avalon Master, alamat byte)

Sumber kebenarannya `fpga/phy_loopback/rtl/loopback_regs.v`. Tabel `REG` di `ber_sweep.tcl` dicocokkan dengannya oleh test.

| Alamat | Nama | Isi |
|---|---|---|
| 0x00 | ID | `0x5345474C` ("SEGL") |
| 0x04 | VERSION | 1 |
| 0x08 | CTRL | bit0 PRBS_EN, bit1 PHY_RST, bit2 CLEAR (pulsa), bit3 SNAP (pulsa), bit4 RAW_MODE |
| 0x0C | STATUS | bit0 pll_locked, bit1 rx_locked, bit2 rx_overflow, bit3 gen_busy, bit4 err_seen, bit5 raw_locked |
| 0x10 | TX_RATE_KHZ | Nominal revisi ini |
| 0x14–0x38 | TX_FRAMES, RX_FRAMES, RX_FRAMES_BAD, BIT_ERRORS, BITS_CHK (64), SYS_CYC (64), TX_CYC (64) | Shadow, diisi oleh SNAP |
| 0x3C–0x54 | PHY_OK, PHY_CRC, PHY_CODE, PHY_DISP, PHY_CTRL, PHY_FRAME, PHY_LOST | Counter PHY 16 bit, nol saat PHY_RST |
| 0x58–0x68 | RAW_BITS (64), RAW_ERR (64), RAW_LOSS | Counter BERT mode RAW |

Untuk pemeriksaan cepat di konsol System Console:

```tcl
set m [claim_service master [lindex [get_service_paths master] 0] segel]
master_read_32 $m 0x00 1       ;# harus 0x5345474c
```

LED: 0 pll_locked, 1 rx_locked/raw_locked, 2 rx_overflow, 3 err_seen, 4 PRBS/RAW aktif, 5 detak tx_clk, 6 detak 50 MHz, 7 PHY_RST.

## 6. SDC (`fpga/phy_loopback/quartus/phy_loopback.sdc`)

### Clock

| Clock | Definisi |
|---|---|
| `clk50` | `create_clock` 20 ns di `FPGA_CLK1_50` |
| tx_clk | `derive_pll_clocks` (generated clock PLL). SDC mencari satu clock `*u_pll*`, lalu mengambil periode dan target-nya untuk dipakai di bawah |
| `tx_fwd_clk` | `create_generated_clock -invert` di port `PHY_TX_CLK`, sumber = keluaran PLL. Pin = ~tx_clk lewat DDIO (`fwd_clk_out.v`) |
| `rx_clk` | `create_clock` di `PHY_RX_CLK`, periode = tx_clk, waveform {T/2, T} |
| `rx_virt` | Clock virtual, periode = tx_clk, tepi naik di 0: tepi peluncur data di pengirim |

### Input delay untuk clock yang diteruskan

Data diluncurkan di tepi naik tx_clk, dan clock yang diteruskan naik setengah bit kemudian (center-aligned).

```
set_input_delay -clock rx_virt -max  rx_skew_max  PHY_RX_DAT     (default +1,5 ns)
set_input_delay -clock rx_virt -min  rx_skew_min  PHY_RX_DAT     (default -1,5 ns)
```

- Setup diperiksa terhadap tepi `rx_clk` di T/2 setelah peluncuran, dan hold terhadap tepi T/2 sebelumnya.
- Margin kasar = T/2 − |skew| − tsu/th register I/O. Pada 25 Mbit/s, T/2 = 20,2 ns, jadi margin sangat lebar. Batas yang ketat baru muncul di laju yang jauh lebih tinggi.
- `rx_skew_*` = selisih waktu tiba data terhadap clock di pin penerima, gabungan dari:
  - beda clock-to-out DDIO vs register I/O di TX;
  - beda panjang jumper (≈ 5 ns/m, jadi selisih 10 cm ≈ 0,5 ns).
- Sesuaikan nilainya dengan kabel yang dipakai.
- `tx_tsu_ext`/`tx_th_ext` (output delay terhadap `tx_fwd_clk`) membatasi skew TX itu sendiri.

### CDC

Tidak ada `set_clock_groups` antar domain desain. Setiap lintasan lintas domain dibatasi satu per satu, sehingga lintasan baru yang tidak dikenal muncul sebagai pelanggaran, bukan terpotong diam-diam.

| Lintasan | Constraint | Alasan |
|---|---|---|
| Pointer Gray FIFO TX/RX (4 bus, 6 bit) | `set_max_skew` 0,8 × periode sumber; `set_max_delay` min(periode sumber, tujuan); hold dipotong | Bus Gray hanya aman kalau skew antar bit < satu periode sumber, karena paling banyak satu bit berubah per siklus |
| Counter Gray lintas domain (`u_fm`, `u_cnt_rbit/rerr/rloss`, 8 bit) | Sama | Sama |
| Memori FIFO → domain baca | `set_max_delay` satu periode tujuan; hold dipotong | Entri baru terbaca paling cepat 2 siklus tujuan setelah ditulis (latensi synchronizer pointer). Memori dipaksa jadi register (`AUTO_RAM_RECOGNITION OFF`) supaya pola `memory*` berlaku |
| Sinyal level 1 bit (`u_sync_status`, `u_sync_lock`, `u_sync_raw`, `u_sync_rawrx`) | `set_false_path -to` tahap pertama | Synchronizer 2 flop; tahap 1 → 2 tetap dianalisis |
| Sumber reset asinkron (KEY, PLL locked, PHY_RST → phy) | `set_false_path -from` | Hanya masuk ke `reset_synchronizer`. Rantai di dalamnya tetap dianalisis |

## 7. Mencatat hasil

Simpan bersama setiap pengukuran:
- `ber_sweep.csv` mentah;
- keluaran `ber.py`;
- laporan `*.segel.*.rpt`;
- versi Quartus;
- revisi git (`git rev-parse HEAD`);
- nomor seri papan;
- panjang jumper;
- suhu ruang;
- frekuensi PLL dari laporan fitter.

Hasil hanya ditulis ke dokumen setelah ada data mentah ini. Sertakan sumbernya (file CSV dan commit), dan tandai hasil yang berasal dari satu papan.

## 8. Masalah umum

| Gejala | Periksa |
|---|---|
| ID register salah atau tidak ada master | SOF salah atau belum diunduh. Di konsol System Console: `get_service_paths master` |
| `pll_locked = 0` | Pin `FPGA_CLK1_50`, `KEY[0]` (harus tidak ditekan) |
| `rx_locked` tidak naik (mode framed) | Jumper clock pin 6 → 1, jumper data pin 8 → 5. Coba mode `raw`: kalau `raw_locked` juga 0, masalahnya di kabel atau pin |
| `raw_loss > 0` | Kanal terlalu buruk pada laju ini (≥ 16 galat per 64 bit). Laporkan sebagai gagal, bukan sebagai BER |
| `tx_clk_hz` jauh dari nominal | Bandingkan dengan PLL Usage Summary. Kalau keduanya cocok, nominal di `pll_tx.v` yang perlu diperbarui |
| `rx_overflow = 1` | Tidak boleh terjadi: `sys_clk` 50 MHz jauh di atas syarat 10 × periode `rx_clk` |
