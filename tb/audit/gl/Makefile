# Audit cocotb gate-level (netlist tapeout TT07), level pin saja.
#   make DESIGN=serdes | DESIGN=cdc_fifo
# Jalankan dari root: `make test-audit-gl-serdes` / `make test-audit-gl-cdc_fifo`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
DESIGN ?= cdc_fifo

REPO_ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../..)
SKY130_SC_HD ?= $(REPO_ROOT)/.cache/sky130_fd_sc_hd

ifeq ($(DESIGN),serdes)
GL_NETLIST := $(REPO_ROOT)/rtl/baseline/serdes_0200/gl/tt_um_serdes.v
else ifeq ($(DESIGN),cdc_fifo)
GL_NETLIST := $(REPO_ROOT)/rtl/baseline/cdc_fifo_0036/gl/tt_um_pa1mantri_cdc_fifo.v
else
$(error DESIGN harus serdes atau cdc_fifo)
endif

SIM_BUILD            = sim_build/$(DESIGN)
COCOTB_RESULTS_FILE ?= results_$(DESIGN).xml
COMPILE_ARGS        += -DGL_TEST -DFUNCTIONAL -DUSE_POWER_PINS -DSIM -DUNIT_DELAY=\#1
COMPILE_ARGS        += -grelative-include
GL_CELL_SOURCES     := $(shell grep -oE '^ *sky130_fd_sc_hd__[a-z0-9]+_[0-9]+' $(GL_NETLIST) | tr -d ' ' | sort -u | \
                         sed -E 's|^sky130_fd_sc_hd__(.*)_([0-9]+)$$|$(SKY130_SC_HD)/cells/\1/sky130_fd_sc_hd__\1_\2.v|')
VERILOG_SOURCES     += $(REPO_ROOT)/tb/common/gl_stubs.v $(GL_CELL_SOURCES) $(GL_NETLIST)
VERILOG_SOURCES     += $(abspath tb_$(DESIGN).v)

TOPLEVEL = tb_$(DESIGN)
MODULE   = test_gl_$(DESIGN)
export PYTHONPATH := $(REPO_ROOT)/model:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
