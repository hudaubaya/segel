# Test cocotb PHY (rtl/phy/). Jalankan dari root: `make test-phy`.
#
#   PHY_SEED=<n>   seed acak (default 2026)
#   TESTCASE=<a,b> hanya test tertentu

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
include $(REPO_ROOT)/rtl/phy/sources.mk

SIM_BUILD           ?= sim_build/rtl
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(PHY_SOURCES) $(REPO_ROOT)/tb/phy/tb.v
COMPILE_ARGS        += -I$(REPO_ROOT)/rtl/phy

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/tb/phy:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
