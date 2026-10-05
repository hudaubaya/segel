# Constraint timing uji loopback PHY SEGEL di DE10-Nano (Quartus Timing Analyzer).
# Penjelasan dan langkah pemeriksaan: docs/phy_howto.md, "SDC".
#
# Domain clock:
#   clk50       FPGA_CLK1_50, 50 MHz: sistem, framer/deframer, register, JTAG master
#   tx_clk      keluaran PLL (derive_pll_clocks): serializer phy, laju bit TX
#   tx_fwd_clk  clock yang diteruskan di pin PHY_TX_CLK (= ~tx_clk lewat DDIO)
#   rx_clk      pin PHY_RX_CLK (clock yang diteruskan, dari jumper loopback)
#   rx_virt     clock virtual peluncur data di sisi pengirim (untuk input delay)
# Semua lintasan antar domain DIBATASI SATU PER SATU di bagian CDC (tidak memakai
# set_clock_groups), sehingga lintasan lintas domain baru yang tidak dikenal akan
# muncul sebagai pelanggaran, bukan diam-diam terpotong.
#
# Setiap pola nama yang kosong memicu critical warning "SEGEL SDC".

# ---------------------------------------------------------------- parameter papan
# Selisih waktu tiba data terhadap clock di pin penerima (ns), gabungan skew
# clock-to-out TX (DDIO vs register I/O) dan beda panjang jumper. Ukur/perkirakan
# untuk kabel yang dipakai, lalu sesuaikan (docs/phy_howto.md).
set rx_skew_max  1.5
set rx_skew_min -1.5
# Kebutuhan setup/hold penerima di pin, untuk membatasi keluaran TX (ns).
set tx_tsu_ext   2.0
set tx_th_ext    1.0

proc segel_need {what coll} {
    if {[get_collection_size $coll] == 0} {
        post_message -type critical_warning "SEGEL SDC: pola untuk $what tidak cocok dengan node mana pun"
    }
    return $coll
}

# ---------------------------------------------------------------- clock
create_clock -name clk50 -period 20.000 [get_ports {FPGA_CLK1_50}]
derive_pll_clocks
derive_clock_uncertainty

set tx_clks [segel_need "clock keluaran PLL" [get_clocks -nowarn {*u_pll*}]]
if {[get_collection_size $tx_clks] != 1} {
    post_message -type critical_warning "SEGEL SDC: harus tepat satu clock PLL, ada [get_collection_size $tx_clks]"
}
foreach_in_collection c $tx_clks {
    set tx_clk_name [get_clock_info -name $c]
    set tx_period   [get_clock_info -period $c]
    set tx_target   [get_clock_info -targets $c]
}
post_message -type info "SEGEL SDC: tx_clk = $tx_clk_name, periode $tx_period ns"

# Clock yang diteruskan: DDIO dengan datain_h = 0, datain_l = 1 -> pin = ~tx_clk.
create_generated_clock -name tx_fwd_clk -source $tx_target -invert [get_ports {PHY_TX_CLK}]

# Clock yang diterima: periode sama dengan tx_clk (loopback). Data diluncurkan di
# tepi naik rx_virt (sama dengan tx_clk di pengirim); tepi naik rx_clk di pin
# berada di tengah bit (center-aligned), yaitu setengah periode kemudian.
set half [expr {$tx_period / 2.0}]
create_clock -name rx_virt -period $tx_period
create_clock -name rx_clk  -period $tx_period -waveform [list $half $tx_period] [get_ports {PHY_RX_CLK}]

# JTAG (Quartus Standard tidak selalu membuatnya otomatis)
if {[get_collection_size [get_ports -nowarn {altera_reserved_tck}]] > 0} {
    create_clock -name altera_reserved_tck -period 33.333 [get_ports {altera_reserved_tck}]
    set_clock_groups -asynchronous -group [get_clocks {altera_reserved_tck}]
}

# ---------------------------------------------------------------- I/O source-synchronous
# Input: data relatif terhadap peluncur virtual. Setup diperiksa terhadap tepi rx_clk
# setengah periode setelah peluncuran; hold terhadap tepi setengah periode sebelumnya.
set_input_delay -clock rx_virt -max $rx_skew_max [get_ports {PHY_RX_DAT}]
set_input_delay -clock rx_virt -min $rx_skew_min [get_ports {PHY_RX_DAT}]

# Output: data relatif terhadap clock yang diteruskan (tepi naik di tengah bit).
set_output_delay -clock tx_fwd_clk -max $tx_tsu_ext       [get_ports {PHY_TX_DAT}]
set_output_delay -clock tx_fwd_clk -min [expr {-$tx_th_ext}] [get_ports {PHY_TX_DAT}]

# Port lambat/asinkron: delay 0 terhadap clk50 hanya supaya port tidak muncul di
# laporan Unconstrained Paths; lintasannya sendiri dipotong.
set_input_delay  -clock clk50 0 [get_ports {KEY[*]}]
set_output_delay -clock clk50 0 [get_ports {LED[*]}]
set_false_path -from [get_ports {KEY[*]}]
set_false_path -to   [get_ports {LED[*]}]

# ---------------------------------------------------------------- CDC
# Periode tiap domain untuk batas di bawah.
set p_sys 20.000
set p_tx  $tx_period
set p_rx  $tx_period

# (1) Sumber reset asinkron: tombol, PLL locked, register PHY_RST. Ketiganya hanya
#     masuk ke reset_synchronizer (assert asinkron, deassert 2 flop per domain).
#     PHY_RST hanya mencapai phy lewat rst_n -> reset_synchronizer; pembacaan balik CTRL
#     (clk50 -> clk50) tetap dianalisis.
set_false_path -from [segel_need "register PHY_RST" [get_registers {*u_regs|phy_rst}]] \
               -to   [segel_need "register phy" [get_registers {*u_phy|*}]]
set_false_path -from [segel_need "PLL locked" [get_pins -nowarn -compatibility_mode {*u_pll*locked*}]]

# (2) Pointer Gray CDC FIFO. Bus Gray hanya aman kalau skew antar bit < satu periode
#     domain SUMBER (paling banyak satu bit berubah per siklus sumber) dan delay total
#     cukup kecil agar synchronizer tidak kehilangan langkah. Kedua batas dipasang
#     eksplisit; hold tidak relevan (lintas domain asinkron) sehingga dipotong.
proc segel_gray {name from to p_src p_dst} {
    set f [segel_need "$name (sumber)" [get_registers $from]]
    set t [segel_need "$name (tujuan)" [get_registers $to]]
    set_max_skew  -from $f -to $t [expr {0.8 * $p_src}]
    set_max_delay -from $f -to $t [expr {$p_src < $p_dst ? $p_src : $p_dst}]
    set_false_path -hold -from $f -to $t
}
# FIFO TX: tulis di clk50, baca di tx_clk
segel_gray "FIFO TX ptr tulis" {*u_tx_fifo|*writestate|write_pointer_gray*} \
                               {*u_tx_fifo|*write_address_sync|data*}  $p_sys $p_tx
segel_gray "FIFO TX ptr baca"  {*u_tx_fifo|*readstate|read_pointer_gray*} \
                               {*u_tx_fifo|*read_address_sync|data*}   $p_tx  $p_sys
# FIFO RX: tulis di rx_clk, baca di clk50
segel_gray "FIFO RX ptr tulis" {*u_rx_fifo|*writestate|write_pointer_gray*} \
                               {*u_rx_fifo|*write_address_sync|data*}  $p_rx  $p_sys
segel_gray "FIFO RX ptr baca"  {*u_rx_fifo|*readstate|read_pointer_gray*} \
                               {*u_rx_fifo|*read_address_sync|data*}   $p_sys $p_rx
# Counter lintas domain (cdc_event_counter, Gray 8 bit): siklus tx_clk (tx -> clk50)
# dan counter BERT mode RAW (rx -> clk50)
segel_gray "tx_cycles"         {*u_fm|gray_m*}        {*u_fm|*u_sync|data*}        $p_tx $p_sys
foreach cnt {u_cnt_rbit u_cnt_rerr u_cnt_rloss} {
    segel_gray "RAW $cnt"      "*$cnt|gray_m*"        "*$cnt|*u_sync|data*"        $p_rx $p_sys
}

# (3) Data FIFO: memori ditulis di domain tulis dan dibaca kombinasional di domain baca
#     (first-word fall-through). Entri baru terbaca paling cepat 2 siklus tujuan setelah
#     ditulis (latensi synchronizer pointer), jadi batas satu periode tujuan aman.
proc segel_mem {name mem p_dst} {
    set f [segel_need "$name memori" [get_registers $mem]]
    set_max_delay -from $f [expr {$p_dst}]
    set_false_path -hold -from $f
}
segel_mem "FIFO TX" {*u_tx_fifo|*fifo_memory|memory*} $p_tx
segel_mem "FIFO RX" {*u_rx_fifo|*fifo_memory|memory*} $p_sys

# (4) Sinyal level satu bit ke synchronizer 2 flop (berubah jarang, dibaca sebagai level):
#     locked/overflow aligner rx -> clk50; raw_locked rx -> clk50 dan pll_locked -> clk50;
#     RAW_MODE clk50 -> tx dan clk50 -> rx. Hanya tahap pertama yang dipotong; tahap
#     pertama -> kedua tetap dianalisis.
foreach {what pat} {
    "synchronizer status RX"   {*u_phy|*u_sync_status|data*}
    "synchronizer lock"        {*u_sync_lock|data*}
    "synchronizer RAW ke tx"   {*u_sync_raw|data*}
    "synchronizer RAW ke rx"   {*u_sync_rawrx|data*}
} {
    set_false_path -to [segel_need $what [get_registers $pat]]
}

# Reset synchronizer (rtl/cdc_fifo/reset_synchronizer.sv) TIDAK dipotong: semua
# sumber reset asinkronnya sudah dipotong di (1), dan rantai flop di dalamnya
# (tahap 1 -> tahap 2) adalah lintasan satu domain yang harus tetap dianalisis.
