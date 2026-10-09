# Laporan Kemajuan SEGEL

Per 5 Oktober 2026 (`main` @ `0ebda35`) · Suzenn

> Salinan dari dokumen [Laporan Kemajuan SEGEL](https://claude.ai/code/artifact/9891cc2d-2ec6-4c07-8cb6-2f13dedc8de8)
> (revisi 8). Isinya berlaku untuk `main` @ `0ebda35`; perubahan sesudah commit itu
> belum tercakup. Detail teknis ada di dokumen per blok di `docs/`.

## Ringkasan

Sepuluh PR sudah di-merge ke `main` (sampai `0ebda35`). Semuanya lulus CI, tetapi **belum ada satu pun hasil silikon, papan, atau kompilasi Quartus**: semua bukti berasal dari simulasi, sintesis Yosys generik, dan mock.

SEGEL kini punya CRC-8, CDC FIFO hasil perbaikan F1–F6, core Ascon-AEAD128/XOF128 (SP 800-232 final), PHY serial 8b/10b source-synchronous, dan proyek uji loopback DE10-Nano.

Tiga hal yang paling perlu diketahui:

- **Klaim BER belum ada.** Proyek FPGA siap dibangun, tetapi baru tim yang bisa mengompilasi dan mengukurnya. Mode PRBS berbingkai tidak boleh dipakai sebagai angka BER: 6 galat satu bit terbaca ±700 "bit salah". Angka BER harus diambil dari mode RAW.
- **Syarat deteksi galat PHY hanya terpenuhi sebagian.** Dari 300 galat satu bit, 300 terdeteksi dan tidak ada frame rusak yang lolos berstatus OK. Namun hanya 272 yang tertangkap lewat kode ilegal atau CRC; 28 lainnya lewat galat disparity, simbol K tak terduga, atau galat framing.
- **Batas pesan dekripsi Ascon.** Plaintext ditahan sampai tag terverifikasi, jadi panjang pesan dekripsi dibatasi buffer: 64 byte pada konfigurasi default.

| Ukuran | Nilai |
| --- | --- |
| PR di-merge | 10 (#1–#10) |
| Vektor resmi Ascon lulus di RTL | 2414 (240 + 60 ACVP, 1089 + 1025 KAT) |
| Kasus 8b/10b exhaustive cocok dengan model | 3072 |
| Galat satu bit PHY terdeteksi | 300 dari 300 |
| Mutan Ascon yang membuat test gagal | 3 dari 3 |
| Hasil papan / Quartus | belum ada |

## Pekerjaan per PR

Semua PR di-merge dalam dua hari (4–5 Oktober 2026). Setiap PR di-merge setelah CI hijau; sejak #8, log CI juga dibaca untuk memastikan target baru benar-benar dijalankan.

| Merge (UTC) | PR | Isi | Hasil kunci |
| --- | --- | --- | --- |
| 5 Okt 10:46 | [#10](https://github.com/hudaubaya/segel/pull/10) | Proyek Quartus DE10-Nano: PLL TX per revisi, pin GPIO, PRBS berbingkai dan RAW, JTAG-to-Avalon, SDC, sweep BER System Console, `sw/ber.py` | Simulasi top 2 × 4/4 lulus; mode RAW: 7 galat diinjeksi → tepat 7 bit salah; skrip Tcl lulus dengan mock |
| 5 Okt 10:10 | [#9](https://github.com/hudaubaya/segel/pull/9) | PHY serial: 8b/10b, SerDes source-synchronous, comma K28.5, CDC FIFO 9 bit, framing CRC-8 | 3072 kasus 8b/10b cocok model; 10 geseran bit; 8 rasio clock; 300/300 galat terdeteksi |
| 5 Okt 09:16 | [#8](https://github.com/hudaubaya/segel/pull/8) | Core Ascon-AEAD128/XOF128 (SP 800-232 final), golden model, uji mutasi | 2414 vektor resmi + 10.000 acak lulus; 3/3 mutan terbunuh |
| 5 Okt 05:39 | [#7](https://github.com/hudaubaya/segel/pull/7) | CDC FIFO: kapasitas 32 (F4), model metastabilitas, netlist Cyclone V (Yosys) | Lulus dengan dan tanpa model metastabilitas |
| 5 Okt 04:59 | [#6](https://github.com/hudaubaya/segel/pull/6) | Reset kedua domain CDC FIFO bersamaan (F6) | Data basi/ganda setelah reset satu domain hilang |
| 5 Okt 04:33 | [#5](https://github.com/hudaubaya/segel/pull/5) | Reset synchronizer per domain CDC FIFO | Pemeriksaan struktur: semua flop memakai reset tersinkron |
| 5 Okt 04:12 | [#4](https://github.com/hudaubaya/segel/pull/4) | CDC FIFO F2 (`rst_n`) dan F5 (pointer Gray diregister) | Synchronizer diumpan langsung dari flop |
| 5 Okt 03:15 | [#3](https://github.com/hudaubaya/segel/pull/3) | CDC FIFO F1 (lebar data wrapper) dan F3 (`full` salah) | Tidak ada data hilang di rasio clock acak |
| 4 Okt 10:28 | [#2](https://github.com/hudaubaya/segel/pull/2) | Audit tiga baseline TT07 apa adanya | Temuan S1–S14 (SerDes), F1–F6 (CDC FIFO), CRC-8 benar |
| 4 Okt 10:04 | [#1](https://github.com/hudaubaya/segel/pull/1) | Struktur repo, salinan baseline TT07, RTL CRC-8 SEGEL, CI | CRC-8 = model untuk 65.536 pasangan (state, byte) |

## Status verifikasi

Perilaku logika semua blok terbukti di simulasi RTL; tidak ada yang terbukti di perangkat keras, timing nyata, atau sintesis teknologi target. Label: \[Pasti\] = dibuktikan test di CI; \[Kemungkinan Besar\] = inferensi kuat; \[Menebak\] = belum bisa dibuktikan dengan alat di repo.

| Blok | Terbukti (CI) | Belum terbukti |
| --- | --- | --- |
| CRC-8 | Sama dengan model untuk 65.536 pasangan (state, byte); netlist baseline #0901 identik \[Pasti\] | Sintesis sky130 dari RTL SEGEL |
| CDC FIFO | Tanpa data hilang/ganda di rasio clock acak, dengan model metastabilitas; struktur synchronizer dan reset (Yosys generik + Cyclone V) \[Pasti\] | Timing/MTBF nyata; netlist Quartus |
| Ascon | 2414 vektor resmi + 10.000 acak; plaintext tidak pernah keluar saat tag salah; 3/3 mutan terbunuh; sintesis Yosys 13.667 sel \[Pasti\] | Proteksi side-channel; timing; sintesis teknologi |
| PHY | 8b/10b exhaustive; 10 geseran bit; 8 rasio clock; 300/300 galat terdeteksi; overload ditandai; sintesis Yosys 3721 sel \[Pasti\] | Kanal dengan jitter/metastabilitas; clock forwarding di silikon |
| FPGA DE10-Nano | Simulasi top dengan model PLL/DDIO/JTAG di \~5 dan \~25 Mbit/s; pola SDC cocok dengan nama register hasil Yosys; skrip proyek, sweep, dan build lulus dengan mock \[Pasti\] | Kompilasi Quartus, laporan timing, hasil papan. Konvensi nama Quartus \[Kemungkinan Besar\]; parameter `altera_pll`/`altddio_out`, port `qsys-generate`, argumen System Console \[Menebak\] |

CI menjalankan semua ini lewat `make test` di setiap PR: Icarus 12, cocotb 1.8.1, Yosys 0.33, Tcl 8.6. Durasi CI terakhir 10,5 menit; suite Ascon adalah bagian terlama (±3,5 menit).

## Temuan penting

Baseline SerDes TT07 hampir seluruhnya tidak bisa dipakai. Hanya dua tabel kodenya yang dipakai ulang, satu di antaranya dengan dua entri diperbaiki; sisanya ditulis ulang.

**Audit baseline (#2).**

- **SerDes #0200:** tabel 8b/10b mencampur kolom RD−/RD+, sehingga 15 byte menghasilkan kode tidak valid. Running disparity, kode K, flag kode ilegal, dan penyelarasan word tidak ada. Loopback hanya benar untuk 8/256 byte.
- **CDC FIFO #0036:** wrapper hanya meneruskan 1 dari 4 bit data. Sinyal `full` gagal saat pointer baca tersinkron = 0, sehingga 32 data bisa hilang tanpa tanda. Reset satu domain membuat data basi terbaca.
- **CRC-8 #0901:** netlist benar. Yang salah hanya dokumentasinya.

**Bug yang ditemukan di kode SEGEL sendiri sebelum merge.** Dua di antaranya lolos dari test versi pertama; kolom terakhir mencatat cara test kini menjaganya.

| Blok | Bug | Mengapa test pertama lolos | Penjaga sekarang |
| --- | --- | --- | --- |
| PHY aligner | Dua comma palsu dari dua galat terpisah menggeser framing; TX tidak mengirim IDLE saat lalu lintas padat, sehingga link mati permanen | Test hanya mengecek galat terdeteksi, bukan link tetap hidup | Unit test (terbukti gagal pada versi lama) + syarat `realign_cnt = 0` dan ≥ 10 frame OK sesudahnya |
| PHY RX | FIFO RX penuh membuang simbol diam-diam; frame terkena hanya dijaga CRC-8 (lolos ±1/256) | Tidak ada test overload | Penanda `LOST` in-band + test overload sementara |
| FPGA PRBS | Mode berbingkai menghitung ratusan "bit salah" per galat, sehingga tidak bisa dipakai sebagai BER | — | Mode RAW (BERT) dengan hitungan tepat |
| FPGA skrip | `raw_locked` dibaca setelah RAW dimatikan; checker RAW memakai lock basi antar putaran | Test simulasi lolos karena latensi synchronizer, bukan karena urutannya benar | Mock System Console + checker ditahan di SEARCH saat RAW mati |
| FPGA PLL | String frekuensi `altera_pll` berawalan byte NUL | — | Literal string per cabang `generate` |
| SDC | `set_false_path` memotong rantai reset synchronizer dan pembacaan balik register | — | False path dipersempit ke sumber asinkron; dicek dengan mock |
| Ascon | Simulasi 4 menit karena clock cocotb membangunkan Python dua kali per siklus | — | Clock di Verilog + lompatan siklus berbasis kejadian |

**Batas yang lebih mendasar.** Syarat "galat bit harus terdeteksi sebagai kode ilegal atau galat CRC" hanya terpenuhi untuk 272/300 galat. Satu bit yang terbalik sering menghasilkan kode yang sah untuk RD lawan, jadi galat disparity harus ikut diperiksa.

## Risiko dan keterbatasan

Risiko terbesar ada di proyek FPGA: proyek itu ditulis tanpa pernah melihat Quartus, jadi kompilasi pertama mungkin gagal atau constraint-nya diam-diam tidak berlaku.

| Blok | Risiko / keterbatasan | Dampak bila diabaikan |
| --- | --- | --- |
| FPGA | Pola nama SDC hanya didekati lewat Yosys; nama register Quartus bisa berbeda | Constraint CDC tidak berlaku tanpa error; laporan Ignored Constraints harus kosong |
| FPGA | Parameter `altera_pll`/`altddio_out`, port `qsys-generate`, `set_max_skew`, argumen System Console ditulis dari ingatan | Kompilasi atau skrip gagal di percobaan pertama |
| FPGA | Fungsi pin clock (Y15 = CLKp) dari basis data Mistral; nomor pin header JP7 dari ingatan | Jumper salah pasang; clock RX tidak lewat jaringan global |
| FPGA | BER < 10⁻¹² butuh ±34 jam di 25 Mbit/s atau 7 hari di 5 Mbit/s dengan 0 galat | Klaim BER rendah tanpa waktu ukur yang cukup tidak sah |
| PHY | Belum ada state machine kehilangan sinkronisasi; frame panjang tanpa IDLE tidak bisa realign di tengah frame | Pemulihan lambat bila galat berkepanjangan |
| PHY | RX tanpa backpressure; syarat periode `sys_clk` < 10 × `rx_clk` | Overload terus-menerus menghentikan link (aman, tetapi tidak berfungsi) |
| PHY | Clock diteruskan sebagai `~tx_clk` di RTL umum; kanal di simulasi tanpa jitter | Perlu sel clock-forwarding dan analisis timing di target |
| Ascon | Panjang pesan dekripsi dibatasi buffer (default 64 byte, 128 flop per blok) | Pesan lebih panjang selalu ditolak |
| Ascon | Tanpa proteksi side-channel; hanya waktu yang tidak bergantung hasil verifikasi tag | Tidak layak untuk ancaman DPA/DFA |
| Semua | Belum ada sintesis sky130/FPGA dengan analisis timing, maupun wrapper Tiny Tapeout untuk Ascon dan PHY | Ukuran dan frekuensi maksimum belum diketahui |
| Proses | Log `make test` lokal terakhir tertimpa saat run berjalan; hanya exit code 0 yang tercatat. Bukti per target diambil dari log CI | Penyebab tertimpanya belum diketahui |

## Langkah berikutnya

Prioritas pertama adalah kompilasi Quartus untuk proyek DE10-Nano, karena itu satu-satunya cara memvalidasi SDC dan pin sebelum ada pengukuran apa pun. Urutan:

1. **Tim (Quartus):** jalankan `fpga/phy_loopback/scripts/build_all.sh r25`. Periksa laporan di `docs/phy_howto.md` §4: Ignored Constraints kosong, tidak ada pesan `SEGEL SDC`, Unconstrained Paths nol, slack ≥ 0. Kirim laporan `*.segel.*.rpt` beserta pesan error bila ada; perbaikan SDC/RTL dilakukan dari laporan itu.
2. **Tim (papan):** cocokkan nomor pin header JP7 dan fungsi pin Y15 dengan manual DE10-Nano dan Pin Planner sebelum memasang jumper.
3. **Tim (papan):** sweep pendek `ber_sweep.tcl detik=10` di keempat laju sebagai uji fungsi, lalu sweep panjang di laju tertinggi. Simpan CSV mentah, versi Quartus, commit, panjang jumper, dan suhu (`docs/phy_howto.md` §7).
4. **Pengembangan:** state machine kehilangan sinkronisasi untuk PHY, dan sintesis teknologi target (sky130 atau Cyclone V lewat Quartus) dengan analisis timing untuk Ascon dan PHY.
5. **Keputusan pemilik proyek:** apakah dekripsi Ascon perlu mendukung pesan > 64 byte (verifikasi dua lintasan atau buffer lebih besar), dan apakah proteksi side-channel masuk lingkup.

Hasil papan baru masuk ke dokumen setelah ada data mentah dan sumbernya.
