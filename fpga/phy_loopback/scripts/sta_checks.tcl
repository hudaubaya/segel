# Laporan Timing Analyzer yang WAJIB diperiksa untuk setiap revisi (docs/phy_howto.md).
#
#   cd fpga/phy_loopback/quartus
#   quartus_sta -t ../scripts/sta_checks.tcl phy_loopback phy_loopback_r25
#
# Menulis output_files/<revisi>.segel.*.rpt. Yang dicek otomatis HANYA slack negatif
# (setup/hold/recovery/removal, semua corner; exit 1 kalau ada). Laporan Ignored
# Constraints, Unconstrained Paths, Clock Transfers, Metastability dan Max Skew harus
# dibaca manusia: docs/phy_howto.md, "Pemeriksaan timing".

package require ::quartus::sta
package require ::quartus::project

if {[llength $quartus(args)] != 2} {
    puts "pemakaian: quartus_sta -t sta_checks.tcl <proyek> <revisi>"
    exit 2
}
lassign $quartus(args) project revision
project_open $project -revision $revision
create_timing_netlist
read_sdc
update_timing_netlist

set out "output_files/$revision.segel"
set bad 0

# 1. Constraint yang diabaikan (pola tidak cocok, target salah, dll.)
report_sdc -ignored -panel_name "SEGEL Ignored Constraints" -file "$out.ignored.rpt"
# 2. Lintasan tanpa constraint
report_ucp -panel_name "SEGEL Unconstrained Paths" -file "$out.ucp.rpt"
# 3. Transfer antar clock (CDC): setiap pasangan harus dikenal dan dibatasi
report_clock_transfers -panel_name "SEGEL Clock Transfers" -file "$out.transfers.rpt"
# 4. Synchronizer dan MTBF
report_metastability -panel_name "SEGEL Metastability" -file "$out.meta.rpt"
# 5. Skew bus Gray (set_max_skew)
report_max_skew -panel_name "SEGEL Max Skew" -file "$out.skew.rpt" -npaths 50
# 6. Pemeriksaan umum (clock tanpa definisi, input/output tanpa delay, loop)
check_timing -file "$out.check.rpt"
report_clocks -file "$out.clocks.rpt"

# 7. Slack per corner
foreach_in_collection op [get_available_operating_conditions] {
    set_operating_conditions $op
    update_timing_netlist
    foreach kind {setup hold recovery removal} {
        set r [report_timing -$kind -npaths 20 -detail summary \
                   -file "$out.$kind.[get_operating_conditions_info -display_name $op].rpt"]
        set worst [lindex $r 1]
        if {[lindex $r 0] > 0 && $worst < 0} {
            puts "SEGEL: slack $kind negatif ($worst ns) di [get_operating_conditions_info -display_name $op]"
            incr bad
        }
    }
}

puts "SEGEL: laporan ditulis ke $out.*.rpt"
if {$bad} { puts "SEGEL: $bad pemeriksaan slack GAGAL" }
delete_timing_netlist
project_close
exit [expr {$bad ? 1 : 0}]
