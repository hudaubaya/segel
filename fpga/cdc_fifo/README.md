# fpga/cdc_fifo/

Sintesis inti CDC FIFO SEGEL (`rtl/cdc_fifo/`) untuk Intel Cyclone V
(mis. DE10-Nano) dengan Yosys:

```sh
make cdc_fifo-cyclonev            # -> build/cyclonev/cdc_fifo_cyclonev.v (+ statistik)
make test-cdc_fifo-cyclonev       # simulasi cocotb netlist (model sel MISTRAL_* Yosys)
make test-cdc_fifo-cyclonev-struct
```

Ini netlist Yosys, bukan hasil Quartus: tanpa place & route dan tanpa timing.
Detail dan batasannya ada di `docs/cdc_fifo.md`.
