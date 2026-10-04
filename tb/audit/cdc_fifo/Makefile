# Audit cocotb baseline #0036 (CDC FIFO). Jalankan dari root: `make test-audit-cdc_fifo`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../..)
SRC_DIR   := $(REPO_ROOT)/rtl/baseline/cdc_fifo_0036/src
# Urutan sama dengan Makefile upstream
SRCS      := tt_um_pa1mantri_cdc_fifo.sv cdc_fifo.sv dpram.sv cdc_fifo_read_state.sv \
             cdc_fifo_write_state.sv binary_to_gray.sv gray_to_binary.sv synchronizer.sv

SIM_BUILD            = sim_build
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(addprefix $(SRC_DIR)/,$(SRCS)) $(abspath tb.v)
ifeq ($(WAVES),1)
COMPILE_ARGS += -DWAVES
endif

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
