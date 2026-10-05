# Mock ::quartus::project untuk menjalankan create_project.tcl di tclsh. Mencatat
# assignment per revisi ke $::env(SEGEL_LOG): <revisi> \t <jenis> \t <nama> \t <nilai> \t <target>
package provide ::quartus::project 1.0
set ::LOG [open $::env(SEGEL_LOG) w]
set ::REV ""
set ::REVS {}
proc project_exists {name} { return 0 }
proc project_new {args} { set ::REV [lindex $args 1]; lappend ::REVS $::REV }
proc project_open {args} { error "tidak dipakai di mock" }
proc revision_exists {r} { return [expr {[lsearch -exact $::REVS $r] >= 0}] }
proc create_revision {r args} { lappend ::REVS $r }
proc set_current_revision {r} {
    if {[lsearch -exact $::REVS $r] < 0} { error "revisi $r belum ada" }
    set ::REV $r
}
proc opt {argv name} { set i [lsearch -exact $argv $name]; return [lindex $argv [expr {$i + 1}]] }
proc set_global_assignment {args} {
    puts $::LOG [join [list $::REV global [opt $args -name] [lindex $args end] ""] "\t"]
}
proc set_location_assignment {pin args} {
    puts $::LOG [join [list $::REV location LOCATION $pin [opt $args -to]] "\t"]
}
proc set_instance_assignment {args} {
    puts $::LOG [join [list $::REV instance [opt $args -name] [lindex $args end-2] [opt $args -to]] "\t"]
}
proc set_parameter {args} {
    puts $::LOG [join [list $::REV parameter [opt $args -name] [lindex $args end] ""] "\t"]
}
proc export_assignments {} { puts $::LOG [join [list $::REV export - - -] "\t"] }
proc project_close {} { close $::LOG }
cd [file dirname $::env(SEGEL_SCRIPT)]
source $::env(SEGEL_SCRIPT)
