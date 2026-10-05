// Register Avalon-MM (domain sys_clk) untuk JTAG-to-Avalon Master.
// Alamat dalam byte, data 32 bit, read latency tetap 1 (readdatavalid), tanpa wait.
// Peta register ini juga dipakai scripts/ber_sweep.tcl dan tb/fpga_loopback; test
// mencocokkan keduanya (docs/phy_howto.md, "Peta register").
//
//   0x00 ID            R   0x5345474C ("SEGL")
//   0x04 VERSION       R   1
//   0x08 CTRL          RW  bit0 PRBS_EN, bit1 PHY_RST (phy direset selama 1),
//                          bit2 CLEAR (tulis 1: nolkan counter, bit kembali 0),
//                          bit3 SNAP  (tulis 1: salin semua counter ke shadow),
//                          bit4 RAW_MODE (bit PRBS mentah ke kabel, tanpa 8b/10b)
//   0x0C STATUS        R   bit0 pll_locked, bit1 rx_locked, bit2 rx_overflow,
//                          bit3 gen_busy, bit4 err_seen, bit5 raw_locked
//   0x10 TX_RATE_KHZ   R   frekuensi nominal tx_clk revisi ini (kHz)
//   Shadow (diisi SNAP):
//   0x14 TX_FRAMES     0x18 RX_FRAMES     0x1C RX_FRAMES_BAD  0x20 BIT_ERRORS
//   0x24 BITS_CHK_LO   0x28 BITS_CHK_HI   0x2C SYS_CYC_LO     0x30 SYS_CYC_HI
//   0x34 TX_CYC_LO     0x38 TX_CYC_HI
//   0x3C PHY_OK  0x40 PHY_CRC  0x44 PHY_CODE  0x48 PHY_DISP  0x4C PHY_CTRL
//   0x50 PHY_FRAME  0x54 PHY_LOST       (counter 16 bit phy, jenuh, nol saat PHY_RST)
//   0x58 RAW_BITS_LO   0x5C RAW_BITS_HI   0x60 RAW_ERR_LO     0x64 RAW_ERR_HI
//   0x68 RAW_LOSS      (mode RAW: bit dibandingkan, bit salah, kehilangan sinkron)

`default_nettype none

module loopback_regs #(
    parameter [31:0] TX_RATE_KHZ = 32'd0
) (
    input  wire        clk,
    input  wire        rst,

    input  wire [7:0]  avs_address,
    input  wire        avs_read,
    input  wire        avs_write,
    input  wire [31:0] avs_writedata,
    input  wire [3:0]  avs_byteenable,
    output reg  [31:0] avs_readdata,
    output reg         avs_readdatavalid,
    output wire        avs_waitrequest,

    output reg         prbs_en,
    output reg         phy_rst,
    output reg         clear,           // pulsa 1 siklus
    output reg         raw_mode,

    input  wire [5:0]  status,
    input  wire [31:0] tx_frames,
    input  wire [31:0] rx_frames,
    input  wire [31:0] rx_frames_bad,
    input  wire [31:0] bit_errors,
    input  wire [63:0] bits_checked,
    input  wire [63:0] tx_cycles,
    input  wire [111:0] phy_cnt,        // {lost, frame, ctrl, disp, code, crc, ok} x 16
    input  wire [63:0] raw_bits,
    input  wire [63:0] raw_errors,
    input  wire [63:0] raw_loss
);

    localparam integer NSH = 22;        // shadow 0x14..0x68

    assign avs_waitrequest = 1'b0;

    reg  [63:0] sys_cycles;
    reg  [31:0] sh [0:NSH-1];
    reg  [31:0] tx_frames_base;         // TX_FRAMES relatif terhadap CLEAR terakhir
    integer     i;

    wire [31:0] live [0:NSH-1];
    assign live[0]  = tx_frames - tx_frames_base;
    assign live[1]  = rx_frames;
    assign live[2]  = rx_frames_bad;
    assign live[3]  = bit_errors;
    assign live[4]  = bits_checked[31:0];
    assign live[5]  = bits_checked[63:32];
    assign live[6]  = sys_cycles[31:0];
    assign live[7]  = sys_cycles[63:32];
    assign live[8]  = tx_cycles[31:0];
    assign live[9]  = tx_cycles[63:32];
    genvar g;
    generate
        for (g = 0; g < 7; g = g + 1) begin : g_phy
            assign live[10 + g] = {16'd0, phy_cnt[16 * g +: 16]};
        end
    endgenerate
    assign live[17] = raw_bits[31:0];
    assign live[18] = raw_bits[63:32];
    assign live[19] = raw_errors[31:0];
    assign live[20] = raw_errors[63:32];
    assign live[21] = (raw_loss[63:32] != 0) ? 32'hFFFF_FFFF : raw_loss[31:0];

    wire wr_ctrl = avs_write && avs_address == 8'h08 && avs_byteenable[0];

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            prbs_en <= 1'b0; phy_rst <= 1'b1; clear <= 1'b0; raw_mode <= 1'b0;
            sys_cycles <= 64'd0; tx_frames_base <= 32'd0;
            avs_readdata <= 32'd0; avs_readdatavalid <= 1'b0;
            for (i = 0; i < NSH; i = i + 1) sh[i] <= 32'd0;
        end else begin
            clear <= 1'b0;
            sys_cycles <= clear ? 64'd0 : sys_cycles + 64'd1;
            if (clear) tx_frames_base <= tx_frames;
            if (wr_ctrl) begin
                prbs_en <= avs_writedata[0];
                phy_rst <= avs_writedata[1];
                clear   <= avs_writedata[2];
                raw_mode <= avs_writedata[4];
                if (avs_writedata[3])
                    for (i = 0; i < NSH; i = i + 1) sh[i] <= live[i];
            end
            avs_readdatavalid <= avs_read;
            if (avs_read) begin
                case (avs_address)
                    8'h00: avs_readdata <= 32'h5345_474C;
                    8'h04: avs_readdata <= 32'd1;
                    8'h08: avs_readdata <= {27'd0, raw_mode, 2'b00, phy_rst, prbs_en};
                    8'h0C: avs_readdata <= {26'd0, status};
                    8'h10: avs_readdata <= TX_RATE_KHZ;
                    default:
                        if (avs_address >= 8'h14 && avs_address <= 8'h68 && avs_address[1:0] == 2'b00)
                            avs_readdata <= sh[(avs_address - 8'h14) >> 2];
                        else
                            avs_readdata <= 32'hDEAD_BEEF;
                endcase
            end
        end
    end

endmodule

`default_nettype wire
