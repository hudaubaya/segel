# Test unit PHY: 8b/10b exhaustive dan comma aligner. Dari root: `make test-phy-units`.
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)

SIM_BUILD           ?= sim_build/rtl
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(REPO_ROOT)/rtl/phy/enc8b10b.v $(REPO_ROOT)/rtl/phy/dec8b10b.v \
                       $(REPO_ROOT)/rtl/phy/phy_deserializer.v $(REPO_ROOT)/rtl/phy/phy_comma_align.v \
                       $(REPO_ROOT)/tb/phy_units/tb_units.v
COMPILE_ARGS        += -I$(REPO_ROOT)/rtl/phy

TOPLEVEL = tb_units
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
