# Mock System Console untuk menjalankan ber_sweep.tcl di tclsh tanpa papan.
# Model register sederhana: counter bertambah menurut laju revisi yang "diunduh" dan
# waktu virtual (`after` tidak tidur, hanya memajukan waktu). Mode RAW menyuntik
# SEGEL_RAW_ERR galat per putaran; mode berbingkai menandai SEGEL_BAD_FRAMES frame.
set ::T 0.0
set ::RATE_KHZ 0
set ::CTRL 0
set ::DOWNLOADS {}
set ::OPS {}
array set ::LIVE {}
array set ::SH {}
array set ::RATES {r05 4990 r10 9980 r20 19960 r25 24750}
set ::RAW_ERR [expr {[info exists ::env(SEGEL_RAW_ERR)] ? $::env(SEGEL_RAW_ERR) : 0}]
set ::BAD_FRAMES [expr {[info exists ::env(SEGEL_BAD_FRAMES)] ? $::env(SEGEL_BAD_FRAMES) : 0}]

rename after tcl_after
proc after {ms args} {
    if {[llength $args]} { error "mock: after dengan script tidak didukung" }
    advance [expr {$ms / 1000.0}]
}
proc advance {dt} {
    set ::T [expr {$::T + $dt}]
    set hz [expr {$::RATE_KHZ * 1000.0}]
    foreach k {SYS TX} { if {![info exists ::LIVE($k)]} { set ::LIVE($k) 0 } }
    set ::LIVE(SYS) [expr {$::LIVE(SYS) + round($dt * 50e6)}]
    set ::LIVE(TX)  [expr {$::LIVE(TX) + round($dt * $hz)}]
    if {$::CTRL & 0x10} {
        set ::LIVE(RAWBITS) [expr {$::LIVE(RAWBITS) + round($dt * $hz)}]
    } elseif {($::CTRL & 0x1) && !($::CTRL & 0x2)} {
        set f [expr {int($dt * $hz / 690)}]
        incr ::LIVE(TXF) $f
        incr ::LIVE(RXF) $f
        incr ::LIVE(OK) $f
        set ::LIVE(BITS) [expr {$::LIVE(BITS) + $f * 480}]
    }
}
proc clear_live {} {
    foreach k {SYS TX TXF RXF BAD BITERR BITS OK CRC CODE DISP RAWBITS RAWERR RAWLOSS} {
        set ::LIVE($k) 0
    }
}
clear_live

proc get_service_paths {type} {
    switch -- $type {
        master { return [list "/devices/5CSEBA6|1@1#USB-1/(link)/JTAG/phy_jtag.master"] }
        device { return [list "/devices/5CSEBA6|1@1#USB-1"] }
    }
}
proc claim_service {type path lib args} { lappend ::OPS claim; return "claim0" }
proc close_service {type c} { lappend ::OPS close }
proc device_download_sof {dev sof} {
    regexp {phy_loopback_(r\d+)\.sof} $sof -> rev
    set ::RATE_KHZ $::RATES($rev)
    lappend ::DOWNLOADS $rev
    clear_live
}
proc refresh_connections {} {}

array set ::ADDR {0x00 ID 0x04 VER 0x08 CTRL 0x0C STATUS 0x10 RATE}
proc master_write_32 {c addr value} {
    set v [expr {$value}]
    set a [expr {$addr}]
    if {$a != 0x08} { error "mock: tulis ke alamat [format 0x%02X $a]" }
    lappend ::OPS [format "W%02X" $v]
    if {$v & 0x4} {
        clear_live
        if {$v & 0x10} { set ::LIVE(RAWERR) $::RAW_ERR }
    }
    if {($v & 0x1) && !($::CTRL & 0x1)} {
        set ::LIVE(BAD) $::BAD_FRAMES
        set ::LIVE(CRC) $::BAD_FRAMES
        set ::LIVE(BITERR) [expr {$::BAD_FRAMES * 100}]
    }
    if {$v & 0x8} {
        set i 0
        foreach k {TXF RXF BAD BITERR BITS_LO BITS_HI SYS_LO SYS_HI TX_LO TX_HI OK CRC CODE DISP
                   CTRLC FRAME LOST RAWBITS_LO RAWBITS_HI RAWERR_LO RAWERR_HI RAWLOSS} {
            set ::SH([expr {0x14 + 4 * $i}]) [live32 $k]
            incr i
        }
    }
    set ::CTRL [expr {$v & 0x13}]
}
proc live32 {k} {
    switch -glob -- $k {
        *_LO { set base [string range $k 0 end-3]; return [expr {[live64 $base] & 0xFFFFFFFF}] }
        *_HI { set base [string range $k 0 end-3]; return [expr {[live64 $base] >> 32}] }
        CTRLC - FRAME - LOST { return 0 }
        default { return [expr {$::LIVE($k) & 0xFFFFFFFF}] }
    }
}
proc live64 {k} { return $::LIVE($k) }
proc master_read_32 {c addr n} {
    set a [expr {$addr}]
    if {$a == 0x00} { set v 0x5345474C } elseif {$a == 0x04} { set v 1 } \
    elseif {$a == 0x08} { set v $::CTRL } \
    elseif {$a == 0x0C} {
        set raw [expr {($::CTRL & 0x10) ? 1 : 0}]
        set rx  [expr {($::CTRL & 0x12) ? 0 : 1}]
        set v [expr {1 | ($rx << 1) | ($raw << 5)}]
    } elseif {$a == 0x10} { set v $::RATE_KHZ } \
    elseif {[info exists ::SH($a)]} { set v $::SH($a) } else { set v 0 }
    return [list [format 0x%08x $v]]
}

cd [file dirname $::env(SEGEL_SCRIPT)]
set argv $::env(SEGEL_ARGS)
source $::env(SEGEL_SCRIPT)
set f [open $::env(SEGEL_OPS) w]
puts $f "downloads $::DOWNLOADS"
puts $f "ops $::OPS"
close $f
