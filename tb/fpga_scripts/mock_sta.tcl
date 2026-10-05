# Mock perintah Timing Analyzer Quartus untuk menjalankan phy_loopback.sdc di tclsh.
# Koleksi = list Tcl. Nama register dari netlist_names.py (pendekatan konvensi Quartus).
# Setiap constraint dicatat ke $::env(SEGEL_LOG), satu baris per perintah:
#   <perintah> \t <opsi> \t <ukuran -from> \t <ukuran -to/target> \t <nilai>

set ::LOG [open $::env(SEGEL_LOG) w]
set ::REGS [split [string trim [read [open $::env(SEGEL_REGS)]]] "\n"]
set ::PORTS {FPGA_CLK1_50 KEY[0] KEY[1] LED[0] LED[1] LED[2] LED[3] LED[4] LED[5] LED[6] LED[7]
             PHY_TX_CLK PHY_TX_DAT PHY_RX_CLK PHY_RX_DAT}
set ::PLL_OUT "u_pll|altera_pll_i|general\[0\].gpll~PLL_OUTPUT_COUNTER|divclk"
set ::PINS [list $::PLL_OUT "u_pll|altera_pll_i|general\[0\].gpll~FRACTIONAL_PLL|locked"]
array set ::CLK {}

proc log {args} { puts $::LOG [join $args "\t"] }

# Pola Quartus: * = apa saja (termasuk '|'), ? = satu karakter, lainnya literal.
proc qmatch {pat names} {
    set re "^"
    foreach ch [split $pat ""] {
        switch -- $ch {
            "*" { append re ".*" }
            "?" { append re "." }
            default { append re [regsub -all {[][\\^$.|+(){}]} $ch {\\&}] }
        }
    }
    append re "\$"
    set out {}
    foreach n $names { if {[regexp -- $re $n]} { lappend out $n } }
    return $out
}
proc strip_opts {argv} {
    set rest {}
    foreach a $argv { if {![string match -* $a]} { lappend rest $a } }
    return $rest
}
proc get_registers {args} { return [qmatch [lindex [strip_opts $args] 0] $::REGS] }
proc get_ports     {args} { return [qmatch [lindex [strip_opts $args] 0] $::PORTS] }
proc get_pins      {args} { return [qmatch [lindex [strip_opts $args] 0] $::PINS] }
proc get_clocks    {args} { return [qmatch [lindex [strip_opts $args] 0] [array names ::CLK]] }
proc get_collection_size {c} { return [llength $c] }
proc foreach_in_collection {var coll body} {
    upvar 1 $var v
    foreach v $coll { uplevel 1 $body }
}

proc getopt {argv name {default ""}} {
    set i [lsearch -exact $argv $name]
    if {$i < 0} { return $default }
    return [lindex $argv [expr {$i + 1}]]
}
proc hasopt {argv name} { return [expr {[lsearch -exact $argv $name] >= 0}] }

proc create_clock {args} {
    set name [getopt $args -name]
    set period [getopt $args -period]
    set wf [getopt $args -waveform [list 0 [expr {$period / 2.0}]]]
    # Semua opsi berpasangan (-opsi nilai); jumlah argumen ganjil = ada target di akhir.
    set targets [expr {[llength $args] % 2 ? [lindex $args end] : {}}]
    set ::CLK($name) [list $period $wf $targets]
    log create_clock $name $period $wf [llength $targets]
}
proc derive_pll_clocks {args} {
    set ::CLK($::PLL_OUT) [list $::env(SEGEL_TX_PERIOD) {} [list $::PLL_OUT]]
    log derive_pll_clocks $::PLL_OUT $::env(SEGEL_TX_PERIOD)
}
proc derive_clock_uncertainty {args} { log derive_clock_uncertainty }
proc get_clock_info {opt c} {
    if {![info exists ::CLK($c)]} { error "get_clock_info: clock $c tidak ada" }
    switch -- $opt {
        -name    { return $c }
        -period  { return [lindex $::CLK($c) 0] }
        -targets { return [lindex $::CLK($c) 2] }
        default  { error "get_clock_info: opsi $opt" }
    }
}
proc create_generated_clock {args} {
    set name [getopt $args -name]
    set src [getopt $args -source]
    if {[llength $src] == 0} { error "create_generated_clock: -source kosong" }
    set target [lindex $args end]
    if {[llength $target] == 0} { error "create_generated_clock: target kosong" }
    set ::CLK($name) [list gen {} $target]
    log create_generated_clock $name [hasopt $args -invert] [llength $src] [llength $target]
}
proc set_clock_groups {args} { log set_clock_groups }
proc need_clock {c} { if {![info exists ::CLK($c)]} { error "clock $c belum dibuat" } }
proc set_input_delay {args} {
    need_clock [getopt $args -clock]
    log set_input_delay [getopt $args -clock] [expr {[hasopt $args -max] ? "max" : "min"}] \
        [llength [lindex $args end]] [lindex $args end-1]
}
proc set_output_delay {args} {
    need_clock [getopt $args -clock]
    log set_output_delay [getopt $args -clock] [expr {[hasopt $args -max] ? "max" : "min"}] \
        [llength [lindex $args end]] [lindex $args end-1]
}
proc fromto {args} {
    return [list [llength [getopt $args -from]] [llength [getopt $args -to]]]
}
proc set_false_path {args} {
    lassign [fromto {*}$args] f t
    log set_false_path [expr {[hasopt $args -hold] ? "hold" : "all"}] $f $t
}
proc set_max_skew {args} {
    lassign [fromto {*}$args] f t
    log set_max_skew - $f $t [lindex $args end]
}
proc set_max_delay {args} {
    lassign [fromto {*}$args] f t
    log set_max_delay - $f $t [lindex $args end]
}
proc post_message {args} {
    log post_message [getopt $args -type] [lindex $args end]
}

source $::env(SEGEL_SDC)
close $::LOG
