# Membuat proyek Quartus Prime Standard/Lite untuk uji loopback PHY di DE10-Nano.
#
#   cd fpga/phy_loopback/quartus
#   quartus_sh -t create_project.tcl
#
# Menghasilkan phy_loopback.qpf dan empat revisi, satu per laju bit (TX_SEL):
#   phy_loopback_r05 (~5 Mbit/s), _r10, _r20, _r25 (~25 Mbit/s)
# Semua revisi identik kecuali parameter TX_SEL. Sistem JTAG harus sudah
# dibangkitkan (../qsys/phy_jtag/synthesis/phy_jtag.qip), lihat docs/phy_howto.md.
#
# Pin: tabel PINS di bawah. Sumber nomor pin: intel/de10-nano-hardware
# (scripts/create_quartus_de10-nano-base.tcl @9b5fc81). Pemilihan pin dan alasannya:
# docs/phy_howto.md, "Pin".

package require ::quartus::project

set project  phy_loopback
set family   "Cyclone V"
set device   5CSEBA6U23I7
set top      de10nano_phy_loopback
set repo     ../../..

# revisi -> TX_SEL
set REVISIONS {
    phy_loopback_r05 0
    phy_loopback_r10 1
    phy_loopback_r20 2
    phy_loopback_r25 3
}

# port -> {pin  arah  catatan}
set PINS {
    FPGA_CLK1_50 {V11  in  "50 MHz, pin clock khusus"}
    KEY[0]       {AH17 in  "reset, aktif rendah"}
    KEY[1]       {AH16 in  "tidak dipakai"}
    LED[0]       {W15  out ""}
    LED[1]       {AA24 out ""}
    LED[2]       {V16  out ""}
    LED[3]       {V15  out ""}
    LED[4]       {AF26 out ""}
    LED[5]       {AE26 out ""}
    LED[6]       {Y16  out ""}
    LED[7]       {AA23 out ""}
    PHY_RX_CLK   {Y15  in  "GPIO_1[0], CLKp (input clock khusus), bank 4A"}
    PHY_RX_DAT   {AG28 in  "GPIO_1[4], bank 4A"}
    PHY_TX_CLK   {AF28 out "GPIO_1[5], bank 4A"}
    PHY_TX_DAT   {AF27 out "GPIO_1[7], bank 4A"}
}

set SOURCES [list \
    $repo/rtl/phy/enc8b10b.v $repo/rtl/phy/dec8b10b.v $repo/rtl/phy/phy_serializer.v \
    $repo/rtl/phy/phy_deserializer.v $repo/rtl/phy/phy_comma_align.v \
    $repo/rtl/phy/phy_framer.v $repo/rtl/phy/phy_deframer.v $repo/rtl/phy/phy.v \
    $repo/rtl/crc8/crc8.v \
    $repo/rtl/cdc_fifo/cdc_fifo.sv $repo/rtl/cdc_fifo/dpram.sv \
    $repo/rtl/cdc_fifo/cdc_fifo_read_state.sv $repo/rtl/cdc_fifo/cdc_fifo_write_state.sv \
    $repo/rtl/cdc_fifo/binary_to_gray.sv $repo/rtl/cdc_fifo/gray_to_binary.sv \
    $repo/rtl/cdc_fifo/synchronizer.sv $repo/rtl/cdc_fifo/reset_synchronizer.sv \
    ../rtl/prbs_framegen.v ../rtl/prbs_checker.v ../rtl/cdc_event_counter.v ../rtl/prbs_raw.v \
    ../rtl/loopback_regs.v ../rtl/pll_tx.v ../rtl/fwd_clk_out.v \
    ../rtl/de10nano_phy_loopback.v \
]

proc apply_common {} {
    global family device top PINS SOURCES repo
    set_global_assignment -name FAMILY $family
    set_global_assignment -name DEVICE $device
    set_global_assignment -name TOP_LEVEL_ENTITY $top
    set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
    set_global_assignment -name SEARCH_PATH $repo/rtl/phy
    set_global_assignment -name SEARCH_PATH ../rtl
    foreach f $SOURCES {
        if {[string match *.sv $f]} {
            set_global_assignment -name SYSTEMVERILOG_FILE $f
        } else {
            set_global_assignment -name VERILOG_FILE $f
        }
    }
    set_global_assignment -name QIP_FILE ../qsys/phy_jtag/synthesis/phy_jtag.qip
    set_global_assignment -name SDC_FILE phy_loopback.sdc
    # Timing: semua corner, dan laporan CDC/metastabilitas
    set_global_assignment -name TIMING_ANALYZER_MULTICORNER_ANALYSIS ON
    set_global_assignment -name SYNCHRONIZER_IDENTIFICATION AUTO
    set_global_assignment -name ENABLE_DRC_SETTINGS ON
    # Memori FIFO (rtl/cdc_fifo/dpram.sv, baca kombinasional) tetap register, bukan
    # MLAB/M10K: SDC membatasi lintasan dari register memory* (phy_loopback.sdc (3)).
    # Desain ini tidak punya RAM lain.
    set_global_assignment -name AUTO_RAM_RECOGNITION OFF
    # Pin yang tidak dipakai: input tri-state (aman untuk header yang tersambung)
    set_global_assignment -name RESERVE_ALL_UNUSED_PINS_WEAK_PULLUP "AS INPUT TRI-STATED"

    foreach {port info} $PINS {
        lassign $info pin dir note
        set_location_assignment PIN_$pin -to $port
        set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to $port
    }
    # Register I/O untuk jalur source-synchronous: delay pin-ke-register dan
    # register-ke-pin tetap dan sama antara data dan clock.
    set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to PHY_TX_DAT
    set_instance_assignment -name FAST_INPUT_REGISTER ON -to PHY_RX_DAT
}

if {[project_exists $project]} {
    project_open -revision [lindex $REVISIONS 0] $project
} else {
    project_new -revision [lindex $REVISIONS 0] $project
}

foreach {rev sel} $REVISIONS {
    if {![revision_exists $rev]} {
        create_revision $rev
    }
    set_current_revision $rev
    apply_common
    set_parameter -name TX_SEL $sel
    export_assignments
    puts "revisi $rev: TX_SEL = $sel"
}

set_current_revision [lindex $REVISIONS end-1]
project_close
