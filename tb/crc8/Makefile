# Test cocotb CRC-8. Jalankan dari root repo: `make test-crc8` / `make test-crc8-gl`.
#
#   GATES=yes    simulasikan netlist gate-level baseline #0901, bukan RTL SEGEL.
#                Butuh model sel sky130_fd_sc_hd di $(SKY130_SC_HD)
#                (Makefile root mengunduhnya otomatis).

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
TB_DIR       := $(REPO_ROOT)/tb/crc8
SKY130_SC_HD ?= $(REPO_ROOT)/.cache/sky130_fd_sc_hd
GL_NETLIST   ?= $(REPO_ROOT)/rtl/baseline/crc8_0901/gl/tt_um_aidenfoxivey.v

ifneq ($(GATES),yes)

SIM_BUILD            = sim_build/rtl
COCOTB_RESULTS_FILE ?= results_rtl.xml
VERILOG_SOURCES     += $(REPO_ROOT)/rtl/crc8/crc8.v
VERILOG_SOURCES     += $(REPO_ROOT)/rtl/crc8/tt_um_hu_crc8.v

else

SIM_BUILD            = sim_build/gl
COCOTB_RESULTS_FILE ?= results_gl.xml
COMPILE_ARGS        += -DGL_TEST -DFUNCTIONAL -DUSE_POWER_PINS -DSIM -DUNIT_DELAY=\#1
COMPILE_ARGS        += -grelative-include
# Satu file wrapper per sel yang benar-benar dipakai netlist,
# mis. sky130_fd_sc_hd__dfrtp_4 -> cells/dfrtp/sky130_fd_sc_hd__dfrtp_4.v
GL_CELL_SOURCES     := $(shell grep -oE '^ *sky130_fd_sc_hd__[a-z0-9]+_[0-9]+' $(GL_NETLIST) | tr -d ' ' | sort -u | \
                         sed -E 's|^sky130_fd_sc_hd__(.*)_([0-9]+)$$|$(SKY130_SC_HD)/cells/\1/sky130_fd_sc_hd__\1_\2.v|')
VERILOG_SOURCES     += $(TB_DIR)/gl_stubs.v $(GL_CELL_SOURCES) $(GL_NETLIST)

endif

ifeq ($(WAVES),1)
COMPILE_ARGS += -DWAVES
endif

VERILOG_SOURCES += $(TB_DIR)/tb.v
TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
