// Reset synchronizer: assert asinkron, deassert sinkron (SEGEL).
//
// reset_out naik segera saat reset_in naik, tanpa menunggu clock, dan turun
// sinkron dengan tepi naik `clock` setelah STAGES siklus sejak reset_in turun.
// Flop di domain `clock` yang memakai reset_out tidak pernah melihat pelepasan
// reset di dekat tepi clock-nya (recovery/removal), dan flop tahap pertama yang
// mungkin metastabil punya STAGES-1 siklus untuk stabil.
//
// Kalau `clock` berhenti, reset tetap aktif sampai clock berjalan lagi.
//
// Dengan `define METASTABILITY_SIM, pelepasan reset di dekat tepi clock bisa
// mundur satu siklus secara acak (model metastabilitas, hanya simulasi).

module reset_synchronizer #(
  parameter STAGES = 2
) (
  input  logic clock,
  input  logic reset_in,   // aktif tinggi, asinkron
  output logic reset_out   // aktif tinggi, deassert sinkron ke clock
);

`ifdef METASTABILITY_SIM
  timeunit 1ns;      // model metastabilitas memakai $realtime dalam ns
  timeprecision 1ps;
`endif

  logic [STAGES-1:0] sync;

`ifndef METASTABILITY_SIM

  always_ff @ (posedge clock or posedge reset_in) begin
    if (reset_in) begin
      sync <= '1;
    end else begin
      sync <= {sync[STAGES-2:0], 1'b0};
    end
  end

`else
  // Model metastabilitas (hanya simulasi), sama dengan synchronizer.sv: kalau
  // reset_in dilepas dalam jendela META_WINDOW_NS sebelum tepi clock, flop
  // tahap pertama melanggar recovery dan resolve acak. Kalau resolve ke nilai
  // lama (1), pelepasan reset mundur satu siklus.
  real    window_ns;
  integer seed;
  integer events  = 0;
  integer delayed = 0;
  real    t_release = -1.0e9;
  logic   first;

  initial begin
    if (!$value$plusargs("META_WINDOW_NS=%f", window_ns)) window_ns = 1.0;
    if ($value$plusargs("META_SEED=%d", seed)) seed = $urandom(seed);
  end

  always @(negedge reset_in) t_release = $realtime;

  always @(posedge clock or posedge reset_in) begin
    if (reset_in) begin
      sync <= '1;
    end else begin
      first = 1'b0;
      if (sync[0] && ($realtime - t_release) < window_ns) begin
        events = events + 1;
        if ($urandom % 2) begin
          first   = 1'b1;
          delayed = delayed + 1;
        end
      end
      sync <= {sync[STAGES-2:0], first};
    end
  end
`endif

  assign reset_out = sync[STAGES-1];

endmodule
