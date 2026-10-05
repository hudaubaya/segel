// Deklarasi kotak hitam primitif Intel dan sistem Platform Designer, hanya untuk
// elaborasi Yosys di tb/fpga_scripts (nama register untuk mock SDC).
(* blackbox *)
module altera_pll #(
    parameter fractional_vco_multiplier = "false",
    parameter reference_clock_frequency = "0 MHz",
    parameter operation_mode = "direct",
    parameter number_of_clocks = 1,
    parameter output_clock_frequency0 = "0 MHz",
    parameter phase_shift0 = "0 ps",
    parameter duty_cycle0 = 50,
    parameter pll_type = "General",
    parameter pll_subtype = "General"
) (input rst, output [0:0] outclk, output locked, output fboutclk, input fbclk, input refclk);
endmodule

(* blackbox *)
module altddio_out #(
    parameter extend_oe_disable = "OFF", parameter intended_device_family = "Cyclone V",
    parameter invert_output = "OFF", parameter lpm_hint = "UNUSED",
    parameter lpm_type = "altddio_out", parameter oe_reg = "UNREGISTERED",
    parameter power_up_high = "OFF", parameter width = 1
) (input aclr, input aset, input [0:0] datain_h, input [0:0] datain_l, output [0:0] dataout,
   input oe, output [0:0] oe_out, input outclock, input outclocken, input sclr, input sset);
endmodule

(* blackbox *)
module phy_jtag (
    input clk_clk, input reset_reset_n, input avmm_waitrequest, input [31:0] avmm_readdata,
    input avmm_readdatavalid, output [0:0] avmm_burstcount, output [31:0] avmm_writedata,
    output [7:0] avmm_address, output avmm_write, output avmm_read, output [3:0] avmm_byteenable,
    output avmm_debugaccess);
endmodule
