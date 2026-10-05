// Keluaran clock yang diteruskan: register DDR di I/O (altddio_out), datain_h = 0,
// datain_l = 1, sehingga pin = ~tx_clk dengan delay clock-to-out yang sama dengan
// data dan tanpa gerbang logika di jalur clock (docs/phy.md: `~tx_clk` sebagai
// inverter tidak boleh dipakai di FPGA).

`default_nettype none
`timescale 1ns / 1ps

module fwd_clk_out (
    input  wire clk,
    output wire pin
);

`ifdef SEGEL_SIM
    reg q = 1'b0;
    always @(clk) q = ~clk;
    assign pin = q;
`else
    altddio_out #(
        .extend_oe_disable("OFF"),
        .intended_device_family("Cyclone V"),
        .invert_output("OFF"),
        .lpm_hint("UNUSED"),
        .lpm_type("altddio_out"),
        .oe_reg("UNREGISTERED"),
        .power_up_high("OFF"),
        .width(1)
    ) u_ddio (
        .aclr(1'b0),
        .aset(1'b0),
        .datain_h(1'b0),
        .datain_l(1'b1),
        .dataout(pin),
        .oe(1'b1),
        .oe_out(),
        .outclock(clk),
        .outclocken(1'b1),
        .sclr(1'b0),
        .sset(1'b0)
    );
`endif

endmodule

`default_nettype wire
