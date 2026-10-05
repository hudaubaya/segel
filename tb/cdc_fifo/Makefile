# Test cocotb CDC FIFO SEGEL. Jalankan dari root: `make test-cdc_fifo`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
SRC_DIR   := $(REPO_ROOT)/rtl/cdc_fifo
SRCS      := tt_um_aduhayabu_cdc_fifo.sv cdc_fifo.sv dpram.sv cdc_fifo_read_state.sv \
             cdc_fifo_write_state.sv binary_to_gray.sv gray_to_binary.sv synchronizer.sv

SIM_BUILD            = sim_build
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(addprefix $(SRC_DIR)/,$(SRCS)) $(abspath tb.v)
ifeq ($(WAVES),1)
COMPILE_ARGS += -DWAVES
endif

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/tb/common:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
