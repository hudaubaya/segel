# Test cocotb CDC FIFO SEGEL. Jalankan dari root: `make test-cdc_fifo`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
SRC_DIR   := $(REPO_ROOT)/rtl/cdc_fifo
SRCS      := tt_um_aduhayabu_cdc_fifo.sv cdc_fifo.sv dpram.sv cdc_fifo_read_state.sv \
             cdc_fifo_write_state.sv binary_to_gray.sv gray_to_binary.sv synchronizer.sv \
             reset_synchronizer.sv

# META=1: aktifkan model metastabilitas di synchronizer (rtl/cdc_fifo,
# `ifdef METASTABILITY_SIM). Jendela dan seed bisa diatur lewat META_WINDOW_NS
# dan META_SEED.
ifeq ($(META),1)
SIM_BUILD            = sim_build/meta
COCOTB_RESULTS_FILE ?= results_meta.xml
COMPILE_ARGS        += -DMETASTABILITY_SIM
META_WINDOW_NS      ?= 1.0
META_SEED           ?= 1
PLUSARGS            += +META_WINDOW_NS=$(META_WINDOW_NS) +META_SEED=$(META_SEED)
export METASTABILITY_SIM := 1
else
SIM_BUILD            = sim_build/rtl
COCOTB_RESULTS_FILE ?= results.xml
endif
VERILOG_SOURCES     += $(addprefix $(SRC_DIR)/,$(SRCS)) $(abspath tb.v)
ifeq ($(WAVES),1)
COMPILE_ARGS += -DWAVES
endif

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/tb/common:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
