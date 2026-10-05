# Ascon (`rtl/ascon_core.v`)

Core Ascon-AEAD128 (enkripsi dan dekripsi) dan Ascon-XOF128 menurut **NIST SP 800-232
final (Agustus 2025)**. Permutasi Ascon-p 320 bit, **satu ronde per siklus**.

Bukan Ascon-128 v1.2 (CAESAR/NIST LWC). Perbedaan yang memengaruhi hasil:

| | Ascon-128 v1.2 | Ascon-AEAD128 (SP 800-232) |
|---|---|---|
| Urutan byte state | big-endian | **little-endian** |
| IV | `0x80400c0600000000` | **`0x00001000808c0001`** |
| Rate | 64 bit | 128 bit (turunan Ascon-128a) |
| Panjang tag | 128 bit | 128 bit, boleh dipotong (≥ 32 bit) |
| Nonce masking | tidak ada | opsional (kunci kedua) |

Ascon-XOF128 memakai IV `0x0000080000cc0003` dan rate 64 bit. Kedua IV dan urutan byte
di atas tidak hanya diambil dari dokumen. Keduanya terbukti benar karena RTL dan model
lulus semua vektor resmi versi final (lihat [Verifikasi](#verifikasi)).

## Sumber dan versi

| Komponen | Sumber | Versi | Lisensi |
|---|---|---|---|
| Spesifikasi | NIST SP 800-232, *Ascon-Based Lightweight Cryptography Standards for Constrained Devices* | final, Agustus 2025 | — |
| Golden model `model/ascon.py` | [meichlseder/pyascon](https://github.com/meichlseder/pyascon) (implementasi referensi Python tim perancang Ascon) | commit `ed24e54abf9507d26fa49b46a56091570c7e743e` (2025-11-18) | CC0 1.0 |
| Vektor ACVP | [usnistgov/ACVP-Server](https://github.com/usnistgov/ACVP-Server) `gen-val/json-files/Ascon-{AEAD128,XOF128}-SP800-232/internalProjection.json` | commit `975de31eb83d87039ec88934fdc47d8c312b892d` (2026-08-12, RELEASE/v1.1.0.43) | NIST |
| KAT | [ascon/ascon-c](https://github.com/ascon/ascon-c) `crypto_aead/asconaead128/LWC_AEAD_KAT_128_128.txt`, `crypto_hash/asconxof128/LWC_XOF_KAT_128_512.txt` | commit `446347f21b209f3921c65ece70027c366cbe1693` (2026-01-28, "update references to NIST SP 800-232 to final version") | CC0 1.0 |

Model diturunkan dari pyascon. Bagian yang disalin tanpa perubahan logika: permutasi, IV,
konversi little-endian, inisialisasi, absorb, finalisasi, dan squeeze. SEGEL
menambahkan tiga hal yang tidak ada di pyascon tetapi dipakai vektor ACVP: panjang dalam
**bit** (bukan byte), tag terpotong, dan nonce masking. README pyascon pada commit itu
masih menyebut "initial public draft". Karena itu model tidak diterima begitu saja,
melainkan dicek terhadap semua vektor resmi versi final (`make test-ascon-model`).

Vektor tidak disalin ke repo. `make ascon-vectors` mengunduhnya ke `.cache/ascon-vectors/`
dari URL `raw.githubusercontent.com` pada commit di atas, lalu memverifikasi SHA-256-nya
(`tb/ascon/vectors.sha256`). Berkas yang tidak ada membuat test **gagal**, bukan di-skip.

| Berkas | SHA-256 |
|---|---|
| `acvp/Ascon-AEAD128-SP800-232/internalProjection.json` | `0c5baffb…eb15b1b` |
| `acvp/Ascon-XOF128-SP800-232/internalProjection.json` | `66efeb34…e66a983` |
| `ascon-c/LWC_AEAD_KAT_128_128.txt` | `bbbc3469…2a4bd33` |
| `ascon-c/LWC_XOF_KAT_128_512.txt` | `d7f5a23f…68e30852` |

Vektor ACVP itu adalah set contoh (`"isSample": true`) yang dipublikasikan NIST di
repo ACVP-Server. Validasi ACVP sungguhan memakai set yang dibangkitkan server untuk
setiap sesi dan tidak publik. "Seluruh vektor resmi yang tersedia" di sini berarti
seluruh isi berkas-berkas di atas.

## Antarmuka

Urutan bit sama dengan SP 800-232: byte ke-*i* string = `bus[8i+7:8i]`, bit ke-*j*
string = `bus[j]`. Kunci, nonce, dan blok data langsung menjadi kata state
(`x0 = bus[63:0]`, `x1 = bus[127:64]`). Untuk panjang yang bukan kelipatan 8, bit yang
dipakai adalah bit **rendah** byte terakhir. Konvensi ini sama dengan vektor ACVP.

| Port | Arah | Keterangan |
|---|---|---|
| `clk`, `rst_n` | in | reset asinkron aktif rendah |
| `start`, `mode[1:0]` | in | 0 = AEAD enkripsi, 1 = AEAD dekripsi, 2 = XOF; diambil saat `busy = 0` |
| `key`, `nonce` | in | 128 bit |
| `key2` | in | kunci kedua nonce masking: nonce efektif = `nonce ^ key2`; 0 = tanpa masking |
| `tag_in` | in | tag yang diverifikasi (dekripsi), diambil saat start |
| `tag_bits[7:0]` | in | 32..128; tag dipotong ke bit rendah. Di luar rentang → `err` |
| `xof_bits[31:0]` | in | panjang keluaran XOF dalam bit |
| `din`, `din_bits`, `din_last`, `din_valid`/`din_ready` | in/out | blok masukan |
| `dout`, `dout_bits`, `dout_valid`/`dout_ready` | out/in | blok keluaran; `dout = 0` saat `dout_valid = 0` |
| `busy`, `done` | out | `done` berpulsa satu siklus setelah keluaran terakhir diterima |
| `tag_out` | out | tag hasil enkripsi (dipotong), 0 pada dekripsi dan XOF |
| `auth_ok`, `err` | out | valid sejak `done` sampai start berikutnya |

Aliran masukan: AEAD mengirim fase AD lalu fase pesan, XOF hanya fase pesan. Setiap fase
terdiri dari nol atau lebih blok penuh (`din_last = 0`, 128 bit untuk AEAD atau 64 bit di
`din[63:0]` untuk XOF), lalu **tepat satu** blok `din_last = 1` dengan
`din_bits = 0..rate-1`. AD kosong dikirim sebagai satu blok last dengan `din_bits = 0`.
Blok last dengan `din_bits ≥ rate` membuat `err` aktif. Pada dekripsi, kondisi itu juga
membuat pesan ditolak.

Parameter `PT_BUF_BLOCKS` (default 4) adalah kapasitas buffer plaintext dekripsi dalam
blok 128 bit.

### Dekripsi: plaintext ditahan sampai tag terverifikasi

1. Setiap blok plaintext hasil dekripsi masuk ke buffer internal. `dout_valid` tidak
   naik selama fase ini.
2. Setelah finalisasi, `tag_in` dibandingkan dengan tag hasil hitung pada `tag_bits` bit
   rendah. Perbandingannya kombinasional dalam satu siklus.
3. **Tag cocok:** isi buffer dikeluarkan blok demi blok lewat `dout`. Setiap entri
   dinolkan saat dikeluarkan.
4. **Tag salah, atau pesan lebih dari `PT_BUF_BLOCKS` blok:** setiap entri buffer
   dinolkan. `dout` tetap 0, `dout_valid` tidak pernah naik, `auth_ok = 0`. Untuk kasus
   overflow, `err = 1`.
5. Tag hasil hitung tidak pernah keluar pada mode dekripsi (`tag_out` tetap 0), karena
   tag itu bisa dipakai sebagai oracle pemalsuan.
6. Jalur rilis dan jalur wipe sama panjang. Dengan `dout_ready = 1`, jumlah siklus
   dekripsi tidak bergantung pada valid atau tidaknya tag (dicek di `test_wrong_tag`).

Di akhir setiap operasi, state, kunci, dan `tag_in` internal dinolkan.

## Verifikasi

`make test-ascon-model test-ascon test-ascon-mutants test-ascon-synth` (bagian dari `make test`):

| Test | Isi | Hasil |
|---|---|---|
| `model/ascon.py` | self-test: KAT pertama, round-trip panjang bit 0..299 | lulus |
| `tb/ascon/check_model.py` | model vs 240 ACVP AEAD, 60 ACVP XOF, 1089 KAT AEAD, 1025 KAT XOF | semua cocok |
| `test_kat_aead` | 1089 KAT ascon-c, enkripsi dan dekripsi | lulus |
| `test_kat_xof` | 1025 KAT ascon-c (keluaran 512 bit) | lulus |
| `test_acvp_aead` | 240 vektor ACVP: panjang bit 0..65536, tag 32..128 bit, nonce masking (tg1/tg3), 60 "modified tag" ditolak | lulus |
| `test_acvp_xof` | 60 vektor ACVP: panjang masukan 0..65536 bit, keluaran 1..65536 bit | lulus |
| `test_random` | 10.000 vektor acak vs model (seed 232): 3495 enkripsi, 2851 dekripsi valid, 1190 dekripsi rusak/ditolak, 2464 XOF; 20% dengan backpressure `dout_ready` acak, 20% dengan jeda `din_valid` acak | lulus |
| `test_wrong_tag` | 5 pesan × 128 bit tag dibalik satu per satu, ditambah ciphertext/AD/nonce/`key2` salah (720 penolakan). Tag 64 bit: bit 0..63 dibalik ditolak, bit 64..127 diabaikan | lulus |
| `test_overflow` | 512 blok (= buffer) diterima; 513 blok dengan tag **benar** tetap ditolak, `err = 1` | lulus |
| `test_errors` | `tag_bits` 0/31/129/255, mode 3, blok last ≥ rate → `err` | lulus |
| `test_cycles` | jumlah siklus (tabel di bawah), dibandingkan dengan rumus | lulus |

Di setiap operasi, pemeriksa di `tb/ascon/tb.v` mengecek **setiap siklus**: `dout != 0`
saat `dout_valid = 0`, `dout_valid = 1` sebelum `auth_ok` pada dekripsi, dan
`tag_out != 0` pada dekripsi. Semua test mensyaratkan jumlah pelanggaran 0. Setelah
setiap dekripsi yang ditolak, isi buffer dibaca dan harus nol semua.

Testbench memakai buffer 512 blok (`-Ptb.PT_BUF_BLOCKS=512`), sama dengan payload ACVP
terpanjang. Durasi suite RTL sekitar 4 menit (Icarus 12, ±3,3 juta siklus). Hambatannya
kecepatan Icarus pada datapath 320 bit (±20 ribu siklus/detik tanpa cocotb), bukan cocotb.

### Uji mutasi

`tb/ascon/mutants.py` menyalin RTL dengan tepat satu substitusi, lalu menjalankan
`test_kat_aead`, `test_acvp_aead`, dan `test_wrong_tag` pada salinan itu. Mutan yang
gagal dikompilasi tidak dihitung terbunuh.

| Mutan | Perubahan | KAT AEAD | ACVP AEAD | tag salah | Pesan pertama |
|---|---|---|---|---|---|
| konstanta ronde | `{~r, r}` → `{r, ~r}` | **gagal** | **gagal** | **gagal** | `Count 1: enkripsi salah` |
| rotasi linear | `rotr(x0, 19)` → `rotr(x0, 18)` | **gagal** | **gagal** | **gagal** | `Count 1: enkripsi salah` |
| perbandingan tag | hanya 64 bit rendah dibandingkan | lulus | **gagal** | **gagal** | `bit tag 64 dibalik diterima` |

Ketiga mutan terbunuh. Mutan perbandingan tag lolos KAT, karena KAT hanya memakai tag
benar. Mutan itu hanya tertangkap oleh vektor tag salah, sehingga uji pembalikan
semua 128 bit diperlukan.

## Jumlah siklus

Siklus dihitung dari tepi clock saat `start` diambil sampai tepi saat `done` naik. Masukan
selalu siap dan `dout_ready = 1`. Kunci 128 bit, tag 128 bit, keluaran XOF 256 bit.

| Operasi | AD | Payload 0 B | Payload 16 B | Payload 32 B |
|---|---|---|---|---|
| AEAD128 enkripsi | 0 B | 27 | 36 | 45 |
| AEAD128 dekripsi | 0 B | 28 | 38 | 48 |
| AEAD128 enkripsi | 16 B | 44 | 53 | 62 |
| AEAD128 dekripsi | 16 B | 45 | 55 | 65 |
| XOF128 (256 bit keluar) | — | 66 | 92 | 118 |

Rumus yang diverifikasi `test_cycles` (`a` = bit AD, `m` = bit pesan):

- Enkripsi: `12 + A + 9·⌊m/128⌋ + 1 + 12 + 1`, dengan `A = 1` kalau AD kosong dan
  `A = 9·(⌊a/128⌋ + 1)` kalau tidak.
- Dekripsi: sama dengan enkripsi, ditambah `⌈m/128⌉ + 1` (rilis atau wipe buffer).
- XOF: `12 + 13·(⌊m/64⌋ + 1) + n + 12·(n − 1) + 1`, dengan `n = ⌈keluaran/64⌉`.

Satu blok AEAD (16 byte) memakan 9 siklus (1 absorb + 8 ronde p8), sehingga throughput
pesan panjang ≈ 14,2 bit/siklus. Satu blok XOF (8 byte) memakan 13 siklus
(≈ 4,9 bit/siklus).

## Sintesis

`make test-ascon-synth`: Yosys 0.33 `synth` generik, `PT_BUF_BLOCKS = 4`, tanpa masalah
struktural (`check -assert`). Hasilnya 13.667 sel, termasuk 1449 flip-flop: 512 untuk
buffer, 320 untuk state, dan sisanya untuk kunci, tag, register keluaran, dan kontrol.
Ini belum sintesis ke teknologi target (sky130/FPGA) dan belum ada analisis timing.

## Keterbatasan

- **Panjang pesan dekripsi dibatasi buffer.** Batasnya `PT_BUF_BLOCKS × 128` bit, yaitu
  64 byte pada default. Setiap blok tambahan memakan 128 flip-flop. Pesan yang lebih
  panjang selalu ditolak (`err`). Untuk pesan panjang di perangkat kecil, alternatifnya
  adalah dua lintasan: verifikasi tag dulu tanpa keluaran, lalu dekripsi ulang. Itu
  belum diimplementasikan.
- Tidak ada proteksi side-channel (masking, DPA/DFA). Yang dijamin hanya waktu yang
  tidak bergantung pada hasil verifikasi tag (lihat di atas).
- `tag_in` harus diberikan saat `start`, bukan setelah ciphertext.
- Inisialisasi XOF menghitung p12 atas IV konstan setiap kali. State hasilnya bisa
  diprakomputasi untuk menghemat 12 siklus, tetapi tidak dilakukan supaya RTL tetap
  mengikuti spesifikasi secara harfiah.
- Ascon-Hash256 dan Ascon-CXOF128 (juga bagian SP 800-232) tidak diimplementasikan.
