// Reset synchronizer: assert asinkron, deassert sinkron (SEGEL).
//
// reset_out naik segera saat reset_in naik, tanpa menunggu clock, dan turun
// sinkron dengan tepi naik `clock` setelah STAGES siklus sejak reset_in turun.
// Flop di domain `clock` yang memakai reset_out tidak pernah melihat pelepasan
// reset di dekat tepi clock-nya (recovery/removal), dan flop tahap pertama yang
// mungkin metastabil punya STAGES-1 siklus untuk stabil.
//
// Kalau `clock` berhenti, reset tetap aktif sampai clock berjalan lagi.

module reset_synchronizer #(
  parameter STAGES = 2
) (
  input  logic clock,
  input  logic reset_in,   // aktif tinggi, asinkron
  output logic reset_out   // aktif tinggi, deassert sinkron ke clock
);

  logic [STAGES-1:0] sync;

  always_ff @ (posedge clock or posedge reset_in) begin
    if (reset_in) begin
      sync <= '1;
    end else begin
      sync <= {sync[STAGES-2:0], 1'b0};
    end
  end

  assign reset_out = sync[STAGES-1];

endmodule
