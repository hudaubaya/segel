// Diturunkan dari TT07 #0036 (Pa1mantri/tt07_cdc_fifo @ ff14afce,
// src/synchronizer.sv), Apache-2.0. Perubahan oleh SEGEL:
//   - model metastabilitas khusus simulasi (`ifdef METASTABILITY_SIM)
// Perangkat keras yang disintesis tidak berubah. Lihat docs/cdc_fifo.md.

module synchronizer #(
  parameter WIDTH = 1
) (
  input logic clock,
  input logic reset,
  input logic [WIDTH-1:0] in,
  output logic [WIDTH-1:0] out);

`ifdef METASTABILITY_SIM
  timeunit 1ns;      // model metastabilitas memakai $realtime dalam ns
  timeprecision 1ps;
`endif

  logic [WIDTH-1:0] data;

`ifndef METASTABILITY_SIM

  always_ff @ (posedge clock or posedge reset) begin
    if (reset) begin
        out <= 0;
        data <= 0;
    end else begin
        {out, data} <= {data, in};
    end
  end

`else
  // ---------------------------------------------------------------------------
  // Model metastabilitas (hanya simulasi).
  //
  // Flop tahap pertama yang masukannya berubah dalam jendela META_WINDOW_NS
  // sebelum tepi clock dianggap metastabil. Ia lalu resolve secara acak (50%)
  // ke nilai BARU atau nilai LAMA. Kalau ke nilai lama, nilai baru baru masuk di
  // tepi berikutnya. Jadi efeknya adalah ketidakpastian latensi satu siklus per
  // bit, yang tidak pernah muncul di simulasi zero-delay biasa.
  //
  // Asumsi model: tahap kedua selalu stabil (resolusi selesai dalam satu siklus,
  // asumsi MTBF synchronizer 2 flop), dan hanya bit yang berubah di dalam
  // jendela yang terpengaruh. Bit yang berubah lebih awal sudah stabil.
  //
  // Plusargs: +META_WINDOW_NS=<real> (default 1.0), +META_SEED=<int> (default 1).
  // Penghitung `events` dan `delayed` bisa dibaca testbench.
  // ---------------------------------------------------------------------------
  real    window_ns;
  integer seed;
  integer events  = 0;   // bit yang berubah di dalam jendela pada tepi clock
  integer delayed = 0;   // dari events, yang resolve ke nilai lama
  real    t_change [WIDTH];
  logic [WIDTH-1:0] in_seen;
  logic [WIDTH-1:0] captured;

  initial begin
    if (!$value$plusargs("META_WINDOW_NS=%f", window_ns)) window_ns = 1.0;
    if ($value$plusargs("META_SEED=%d", seed)) seed = $urandom(seed);
    for (int i = 0; i < WIDTH; i++) t_change[i] = -1.0e9;
    in_seen = in;
  end

  always @(in) begin
    for (int i = 0; i < WIDTH; i++)
      if (in[i] !== in_seen[i]) t_change[i] = $realtime;
    in_seen = in;
  end

  always @(posedge clock or posedge reset) begin
    if (reset) begin
      out  <= 0;
      data <= 0;
    end else begin
      for (int i = 0; i < WIDTH; i++) begin
        captured[i] = in[i];
        if (in[i] !== data[i] && ($realtime - t_change[i]) < window_ns) begin
          events = events + 1;
          if ($urandom % 2) begin
            captured[i] = data[i];
            delayed = delayed + 1;
          end
        end
      end
      {out, data} <= {data, captured};
    end
  end
`endif

endmodule
