// Penghitung kejadian dari domain clock lain, dibaca di domain `clk`.
//
// Counter biner 8 bit di domain `meas_clk` (naik saat `inc` = 1) dikodekan Gray dan
// diregister di domain itu, lalu disinkronkan 2 flop ke `clk` (cdc_fifo/synchronizer).
// Selisih antar siklus `clk` diakumulasikan ke `count` (64 bit). Syarat: kenaikan per
// siklus `clk` < 128 (meas_clk < 128 x clk), supaya counter 8 bit tidak membungkus.
// Dengan inc = 1 terus-menerus, ini pengukur frekuensi meas_clk.
// Constraint jalur Gray: fpga/phy_loopback/quartus/phy_loopback.sdc (2).

`default_nettype none

module cdc_event_counter (
    input  wire        meas_clk,
    input  wire        meas_rst,     // aktif tinggi, tersinkron ke meas_clk
    input  wire        inc,
    input  wire        clk,
    input  wire        rst,          // aktif tinggi, tersinkron ke clk
    input  wire        clear,
    output reg  [63:0] count
);

    reg  [7:0] bin_m;
    reg  [7:0] gray_m;               // diregister di domain meas_clk: tanpa glitch
    wire [7:0] bin_n = bin_m + {7'd0, inc};
    always @(posedge meas_clk or posedge meas_rst) begin
        if (meas_rst) begin
            bin_m <= 8'd0; gray_m <= 8'd0;
        end else begin
            bin_m  <= bin_n;
            gray_m <= bin_n ^ (bin_n >> 1);
        end
    end

    wire [7:0] gray_s;
    synchronizer #(.WIDTH(8)) u_sync (.clock(clk), .reset(rst), .in(gray_m), .out(gray_s));

    reg  [7:0] bin_s, bin_prev;
    integer    i;
    always @* begin
        bin_s[7] = gray_s[7];
        for (i = 6; i >= 0; i = i - 1) bin_s[i] = bin_s[i + 1] ^ gray_s[i];
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            bin_prev <= 8'd0; count <= 64'd0;
        end else begin
            bin_prev <= bin_s;
            count    <= (clear ? 64'd0 : count) + {56'd0, bin_s - bin_prev};
        end
    end

endmodule

`default_nettype wire
