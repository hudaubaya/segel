# System Console: jalankan PRBS pada beberapa laju (satu revisi/SOF per laju) dan
# simpan hasil ke CSV. Analisis: sw/ber.py. Langkah lengkap: docs/phy_howto.md.
#
#   system-console -cli --script=ber_sweep.tcl [--] [detik=10] [csv=ber_sweep.csv] \
#       [revs=r05,r10,r20,r25] [modes=raw,framed] [sof_dir=../quartus/output_files] \
#       [download=1]
#
# Untuk setiap revisi: unduh SOF sekali, lalu untuk setiap mode:
#   raw    : RAW_MODE (bit PRBS-31 mentah di kabel), tunggu raw_locked, CLEAR, jalan
#            <detik>, SNAP. Menghasilkan BER kanal (raw_bits, raw_errors).
#   framed : PHY_RST, tunggu rx_locked, CLEAR, PRBS_EN selama <detik>, berhenti, tunggu
#            frame terakhir, SNAP. Menghasilkan statistik frame dan counter phy.
# Satu baris CSV per (revisi, mode).
# Peta register = fpga/phy_loopback/rtl/loopback_regs.v (dicocokkan oleh test).

array set REG {
    ID 0x00  VERSION 0x04  CTRL 0x08  STATUS 0x0C  TX_RATE_KHZ 0x10
    TX_FRAMES 0x14  RX_FRAMES 0x18  RX_FRAMES_BAD 0x1C  BIT_ERRORS 0x20
    BITS_CHK_LO 0x24  BITS_CHK_HI 0x28  SYS_CYC_LO 0x2C  SYS_CYC_HI 0x30
    TX_CYC_LO 0x34  TX_CYC_HI 0x38
    PHY_OK 0x3C  PHY_CRC 0x40  PHY_CODE 0x44  PHY_DISP 0x48  PHY_CTRL 0x4C
    PHY_FRAME 0x50  PHY_LOST 0x54
    RAW_BITS_LO 0x58  RAW_BITS_HI 0x5C  RAW_ERR_LO 0x60  RAW_ERR_HI 0x64  RAW_LOSS 0x68
}
set CTRL_PRBS_EN 0x1
set CTRL_PHY_RST 0x2
set CTRL_CLEAR   0x4
set CTRL_SNAP    0x8
set CTRL_RAW     0x10
set REG_ID_VALUE 0x5345474C
set SYS_CLK_HZ   50000000

set CSV_COLUMNS {revision mode tx_rate_khz seconds sys_cycles tx_cycles tx_clk_hz
                 tx_frames rx_frames rx_frames_bad bits_checked bit_errors
                 phy_ok phy_crc phy_code phy_disp phy_ctrl phy_frame phy_lost
                 raw_bits raw_errors raw_loss
                 pll_locked rx_locked rx_overflow raw_locked timestamp}

# ---------------------------------------------------------------- argumen
proc parse_args {argv} {
    set opt [dict create detik 10 csv ber_sweep.csv revs r05,r10,r20,r25 modes raw,framed \
                 sof_dir ../quartus/output_files download 1]
    foreach a $argv {
        if {$a eq "--"} continue
        if {![regexp {^([a-z_]+)=(.*)$} $a -> k v] || ![dict exists $opt $k]} {
            error "argumen tidak dikenal: $a"
        }
        dict set opt $k $v
    }
    return $opt
}

# ---------------------------------------------------------------- akses register
proc rd {m name} {
    global REG
    return [expr {[lindex [master_read_32 $m $REG($name) 1] 0] & 0xFFFFFFFF}]
}
proc wr {m name value} {
    global REG
    master_write_32 $m $REG($name) [format 0x%08X $value]
}
proc rd64 {m lo hi} { return [expr {([rd $m $hi] << 32) | [rd $m $lo]}] }

proc open_master {} {
    set paths [get_service_paths master]
    if {[llength $paths] == 0} { error "tidak ada JTAG master (SOF sudah diunduh?)" }
    # Pilih master phy_jtag kalau ada beberapa (mis. ada HPS).
    set path [lindex $paths 0]
    foreach p $paths { if {[string match *phy_jtag* $p]} { set path $p } }
    set m [claim_service master $path segel]
    global REG_ID_VALUE
    set id [rd $m ID]
    if {$id != $REG_ID_VALUE} {
        close_service master $m
        error [format "ID register 0x%08X, harap 0x%08X (desain salah?)" $id $REG_ID_VALUE]
    }
    return $m
}

proc wait_status {m bit timeout_ms} {
    set t 0
    while {!(([rd $m STATUS] >> $bit) & 1)} {
        if {$t >= $timeout_ms} { return 0 }
        after 10
        incr t 10
    }
    return 1
}

# ---------------------------------------------------------------- satu laju
proc download {rev sof_dir} {
    set sof [file join $sof_dir phy_loopback_$rev.sof]
    if {![file exists $sof]} { error "SOF tidak ada: $sof" }
    set dev [lindex [get_service_paths device] 0]
    puts "== $rev: unduh $sof"
    device_download_sof $dev $sof
    catch {refresh_connections}
}

proc run_mode {rev mode seconds} {
    global CTRL_PRBS_EN CTRL_PHY_RST CTRL_CLEAR CTRL_SNAP CTRL_RAW SYS_CLK_HZ
    set m [open_master]
    set khz [rd $m TX_RATE_KHZ]
    puts "== $rev/$mode: tx_clk nominal $khz kHz"

    wr $m CTRL $CTRL_PHY_RST
    after 10
    if {$mode eq "raw"} {
        # phy ditahan reset: bit mentah bukan 8b/10b, counter phy tetap nol
        set base [expr {$CTRL_RAW | $CTRL_PHY_RST}]
        wr $m CTRL $base
        if {![wait_status $m 5 2000]} { puts "PERINGATAN: $rev/raw: raw_locked tidak naik dalam 2 s" }
        wr $m CTRL [expr {$base | $CTRL_CLEAR}]
        after [expr {int($seconds * 1000)}]
        wr $m CTRL [expr {$base | $CTRL_SNAP}]
        set st [rd $m STATUS]                        ;# sebelum RAW mati (raw_locked)
    } elseif {$mode eq "framed"} {
        wr $m CTRL 0
        if {![wait_status $m 1 2000]} { puts "PERINGATAN: $rev/framed: rx_locked tidak naik dalam 2 s" }
        wr $m CTRL $CTRL_CLEAR
        wr $m CTRL $CTRL_PRBS_EN
        after [expr {int($seconds * 1000)}]
        wr $m CTRL 0
        after 50                                     ;# frame terakhir selesai dan tiba
        wr $m CTRL $CTRL_SNAP
        set st [rd $m STATUS]
    } else {
        error "mode tidak dikenal: $mode"
    }

    set r [dict create revision $rev mode $mode tx_rate_khz $khz seconds $seconds]
    dict set r sys_cycles    [rd64 $m SYS_CYC_LO SYS_CYC_HI]
    dict set r tx_cycles     [rd64 $m TX_CYC_LO TX_CYC_HI]
    set sc [dict get $r sys_cycles]
    dict set r tx_clk_hz     [expr {$sc > 0 ? round(double([dict get $r tx_cycles]) * $SYS_CLK_HZ / $sc) : 0}]
    dict set r tx_frames     [rd $m TX_FRAMES]
    dict set r rx_frames     [rd $m RX_FRAMES]
    dict set r rx_frames_bad [rd $m RX_FRAMES_BAD]
    dict set r bits_checked  [rd64 $m BITS_CHK_LO BITS_CHK_HI]
    dict set r bit_errors    [rd $m BIT_ERRORS]
    foreach {k reg} {phy_ok PHY_OK phy_crc PHY_CRC phy_code PHY_CODE phy_disp PHY_DISP
                     phy_ctrl PHY_CTRL phy_frame PHY_FRAME phy_lost PHY_LOST} {
        dict set r $k [rd $m $reg]
    }
    dict set r raw_bits      [rd64 $m RAW_BITS_LO RAW_BITS_HI]
    dict set r raw_errors    [rd64 $m RAW_ERR_LO RAW_ERR_HI]
    dict set r raw_loss      [rd $m RAW_LOSS]
    dict set r pll_locked  [expr {$st & 1}]
    dict set r rx_locked   [expr {($st >> 1) & 1}]
    dict set r rx_overflow [expr {($st >> 2) & 1}]
    dict set r raw_locked  [expr {($st >> 5) & 1}]
    dict set r timestamp   [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S]
    wr $m CTRL 0
    close_service master $m
    if {$mode eq "raw"} {
        puts [format "== %s/raw: %s bit dibandingkan, %s bit salah, %d kehilangan sinkron" \
                  $rev [dict get $r raw_bits] [dict get $r raw_errors] [dict get $r raw_loss]]
    } else {
        puts [format "== %s/framed: %d frame TX, %d frame RX (%d bertanda)" \
                  $rev [dict get $r tx_frames] [dict get $r rx_frames] [dict get $r rx_frames_bad]]
    }
    return $r
}

# ---------------------------------------------------------------- main
proc main {argv} {
    global CSV_COLUMNS
    set opt [parse_args $argv]
    set csv [dict get $opt csv]
    set new [expr {![file exists $csv]}]
    set f [open $csv a]
    if {$new} { puts $f [join $CSV_COLUMNS ,] }
    foreach rev [split [dict get $opt revs] ,] {
        if {[dict get $opt download]} { download $rev [dict get $opt sof_dir] }
        foreach mode [split [dict get $opt modes] ,] {
            set r [run_mode $rev $mode [dict get $opt detik]]
            set row {}
            foreach c $CSV_COLUMNS { lappend row [dict get $r $c] }
            puts $f [join $row ,]
            flush $f
        }
    }
    close $f
    puts "CSV: $csv  (analisis: python3 sw/ber.py $csv)"
}

# Argumen: dari baris perintah ($argv), atau set ::segel_args sebelum `source` di
# konsol interaktif, mis. `set ::segel_args {detik=5 revs=r25 download=0}`.
if {![info exists ::segel_no_main]} {
    if {[info exists ::segel_args]} { main $::segel_args } else { main $argv }
}
