// Simbol yang dipakai PHY SEGEL (docs/phy.md). Simbol 9 bit = {k, byte}.
localparam [7:0] SYM_IDLE = 8'hBC;  // K28.5, comma; diisi TX saat FIFO kosong, dibuang RX
localparam [7:0] SYM_SOF  = 8'hFB;  // K27.7, awal frame
localparam [7:0] SYM_EOF  = 8'hFD;  // K29.7, akhir frame
// Penanda galat dari RX ke domain sistem (bukan kode K yang sah, tidak pernah dikirim)
localparam [7:0] SYM_ERR_ILLEGAL = 8'h00;  // kode 10 bit ilegal
localparam [7:0] SYM_ERR_DISP    = 8'h01;  // galat running disparity
localparam [7:0] SYM_ERR_LOST    = 8'h02;  // simbol dibuang karena FIFO RX penuh
