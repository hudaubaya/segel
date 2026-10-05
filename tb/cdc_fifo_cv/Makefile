# Test cocotb netlist Cyclone V CDC FIFO. Dari root: `make test-cdc_fifo-cyclonev`
# (membangkitkan netlist dulu dengan Yosys).
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
NETLIST   ?= $(REPO_ROOT)/build/cyclonev/cdc_fifo_cyclonev.v
# Model simulasi sel MISTRAL_* dari Yosys (fungsional; delay specify diabaikan).
INTEL_ALM ?= $(shell dirname $$(dirname $$(which yosys)))/share/yosys/intel_alm/common

SIM_BUILD            = sim_build
COCOTB_RESULTS_FILE ?= results.xml
COMPILE_ARGS        += -Dcyclonev
VERILOG_SOURCES     += $(addprefix $(INTEL_ALM)/,alm_sim.v dff_sim.v mem_sim.v misc_sim.v)
VERILOG_SOURCES     += $(NETLIST) $(abspath tb.v)

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/tb/common:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
