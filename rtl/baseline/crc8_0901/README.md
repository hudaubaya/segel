# crc8_0901 — RTL tidak tersedia

Repo upstream `aidenfoxivey/tt07-verilog-template` sudah tidak dapat diakses,
jadi direktori ini hanya berisi artefak tapeout dari repo shuttle
`TinyTapeout/tinytapeout-07`. `gl/tt_um_aidenfoxivey.v` adalah netlist
gate-level, bukan RTL. Netlist ini disimulasikan sebagai golden reference
oleh `make test-baseline-crc8_0901`. RTL pengganti: `rtl/crc8/`.
Detail: `docs/baselines.md` dan `docs/crc8.md`.
