# Sistem Platform Designer "phy_jtag": JTAG-to-Avalon Master -> Avalon-MM bridge yang
# diekspor ke RTL (de10nano_phy_loopback.v, port avmm_*). Pola perintah mengikuti
# intel/de10-nano-hardware (scripts/create_qsys_*.tcl).
#
#   cd fpga/phy_loopback/qsys
#   qsys-script --script=make_phy_jtag.tcl
#   qsys-generate phy_jtag.qsys --synthesis=VERILOG --output-directory=phy_jtag
#
# Port top hasil generate: clk_clk, reset_reset_n, avmm_{waitrequest,readdata,
# readdatavalid,burstcount,writedata,address,write,read,byteenable,debugaccess}.

package require -exact qsys 16.1

create_system phy_jtag
set_project_property DEVICE_FAMILY "Cyclone V"
set_project_property DEVICE 5CSEBA6U23I7

add_instance clk_0 clock_source
set_instance_parameter_value clk_0 {clockFrequency} {50000000.0}
set_instance_parameter_value clk_0 {clockFrequencyKnown} {1}
set_instance_parameter_value clk_0 {resetSynchronousEdges} {DEASSERT}

add_instance master altera_jtag_avalon_master

add_instance bridge altera_avalon_mm_bridge
set_instance_parameter_value bridge {DATA_WIDTH} {32}
set_instance_parameter_value bridge {SYMBOL_WIDTH} {8}
set_instance_parameter_value bridge {ADDRESS_WIDTH} {8}
set_instance_parameter_value bridge {USE_AUTO_ADDRESS_WIDTH} {0}
set_instance_parameter_value bridge {ADDRESS_UNITS} {SYMBOLS}
set_instance_parameter_value bridge {MAX_BURST_SIZE} {1}
set_instance_parameter_value bridge {MAX_PENDING_RESPONSES} {4}
set_instance_parameter_value bridge {LINEWRAPBURSTS} {0}
set_instance_parameter_value bridge {PIPELINE_COMMAND} {1}
set_instance_parameter_value bridge {PIPELINE_RESPONSE} {1}

add_connection clk_0.clk master.clk clock
add_connection clk_0.clk bridge.clk clock
add_connection clk_0.clk_reset master.clk_reset reset
add_connection clk_0.clk_reset bridge.reset reset

add_connection master.master bridge.s0 avalon
set_connection_parameter_value master.master/bridge.s0 baseAddress {0x0000}

add_interface clk clock sink
set_interface_property clk EXPORT_OF clk_0.clk_in
add_interface reset reset sink
set_interface_property reset EXPORT_OF clk_0.clk_in_reset
add_interface avmm avalon start
set_interface_property avmm EXPORT_OF bridge.m0

save_system phy_jtag.qsys
