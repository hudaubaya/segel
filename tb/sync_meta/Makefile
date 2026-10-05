# Uji unit model metastabilitas synchronizer. Dari root: `make test-sync_meta`.
#   META=1  aktifkan model (`define METASTABILITY_SIM)
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
VERILOG_SOURCES += $(REPO_ROOT)/rtl/cdc_fifo/synchronizer.sv $(abspath tb.v)

ifeq ($(META),1)
SIM_BUILD            = sim_build/meta
COCOTB_RESULTS_FILE ?= results_meta.xml
COMPILE_ARGS        += -DMETASTABILITY_SIM
PLUSARGS            += +META_WINDOW_NS=1.0 +META_SEED=7
export METASTABILITY_SIM := 1
else
SIM_BUILD            = sim_build/rtl
COCOTB_RESULTS_FILE ?= results.xml
endif

TOPLEVEL = tb
MODULE   = test
include $(shell cocotb-config --makefiles)/Makefile.sim
