# CRC-8 (`rtl/crc8/`)

RTL CRC-8 milik SEGEL, ditulis ulang karena RTL baseline TT07 #0901
(`tt_um_aidenfoxivey`) tidak lagi tersedia (lihat `docs/baselines.md`).
Targetnya adalah **perilaku yang identik dengan netlist yang di-tapeout**,
bukan dengan deskripsi di `docs/info.md` upstream.

## Spesifikasi

| Parameter | Nilai |
|---|---|
| Algoritma | CRC-8/SMBUS |
| Polinomial | x^8 + x^2 + x + 1 (`0x07`) |
| Nilai awal | `0x00` |
| Urutan bit | MSB dulu, tanpa refleksi masukan/keluaran |
| XOR akhir | tidak ada |
| Check value | `crc8("123456789") = 0xF4` |
| Throughput | 1 byte per siklus clock |
| Reset | `rst_n` asinkron, aktif rendah |

## File

| File | Isi |
|---|---|
| `rtl/crc8/crc8.v` | Inti CRC-8, parameter `POLY`/`INIT`; port `clr` (clear sinkron ke `INIT`, prioritas di atas `en`) dipakai framer/deframer PHY (`docs/phy.md`), diikat 0 di wrapper TT |
| `rtl/crc8/tt_um_aduhayabu_crc8.v` | Wrapper Tiny Tapeout, pinout sama dengan #0901 |
| `model/crc8.py` | Model referensi Python + self-test |
| `tb/crc8/` | Testbench cocotb untuk RTL **dan** netlist baseline |

## Pinout (`tt_um_aduhayabu_crc8`)

| Pin | Fungsi |
|---|---|
| `ui_in[7:0]` | Byte masukan |
| `uio_in[0]` | Enable: 1 = serap `ui_in` pada tepi naik `clk` |
| `uo_out[7:0]` | Nilai register CRC saat ini |
| `uio_in[7:1]`, `ena` | Tidak dipakai |
| `uio_out`, `uio_oe` | Selalu `0x00` |

## Verifikasi

`make test-crc8` menjalankan `tb/crc8/test.py` pada RTL, dan `make test-crc8-gl`
menjalankan file test yang sama pada netlist gate-level baseline #0901:

| Test | Cakupan |
|---|---|
| `test_check_value` | Check value standar `0xF4` |
| `test_exhaustive_next_state` | Semua 65.536 pasangan (state, byte) dengan `en=1` |
| `test_enable_holds` | `en=0` menahan nilai, untuk semua 256 state × 4 byte acak |
| `test_random_stream` | 20.000 siklus dengan `en`, `ena`, `uio_in[7:1]` acak; `uio_out`/`uio_oe` = 0 |
| `test_async_reset` | `rst_n` mengosongkan CRC di tengah fase clock, tanpa tepi clock |

Kedua target lulus. Karena state hanya 8 bit dan semua state tercapai, lulus
`test_exhaustive_next_state` pada keduanya berarti fungsi next-state untuk
`en=1` sama persis antara RTL dan netlist tapeout.

Mutation check (dijalankan manual saat RTL ditulis): mengganti polinomial ke
`0x31`, mengabaikan `en`, dan menjadikan reset sinkron masing-masing membuat
setidaknya satu test gagal.

### Batasan

- Ini bukti berbasis simulasi, bukan pembuktian ekuivalensi formal. Jalur
  `en=0` dan pin yang tidak dipakai diuji dengan sampel acak, tidak exhaustive.
- Simulasi gate-level memakai `UNIT_DELAY=#1` tanpa SDF. Timing nyata tidak
  diverifikasi.
- Model sel diambil dari `google/skywater-pdk-libs-sky130_fd_sc_hd` commit
  `28c101fc`, sedangkan tapeout TT07 memakai open_pdks `cd1748bb`. Model
  fungsional kedua sumber diharapkan sama, tetapi itu belum dibandingkan
  langsung.
