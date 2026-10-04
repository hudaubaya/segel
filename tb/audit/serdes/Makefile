# Audit cocotb baseline #0200 (SerDes). Jalankan dari root: `make test-audit-serdes`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../../..)
SRC_DIR   := $(REPO_ROOT)/rtl/baseline/serdes_0200/src

SIM_BUILD            = sim_build
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(SRC_DIR)/project.v $(SRC_DIR)/serdes_top.v
VERILOG_SOURCES     += $(abspath tb.v)
ifeq ($(WAVES),1)
COMPILE_ARGS += -DWAVES
endif

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
