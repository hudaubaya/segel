# Simulasi top FPGA DE10-Nano (fpga/phy_loopback/rtl) dengan PLL/DDIO/JTAG model.
# Dari root: `make test-fpga-loopback` (TX_SEL=3 ~25 Mbit/s dan TX_SEL=0 ~5 Mbit/s).
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TX_SEL ?= 3

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
include $(REPO_ROOT)/rtl/phy/sources.mk
FPGA_RTL := $(REPO_ROOT)/fpga/phy_loopback/rtl

SIM_BUILD           ?= sim_build/sel$(TX_SEL)
COCOTB_RESULTS_FILE ?= results_sel$(TX_SEL).xml
VERILOG_SOURCES     += $(PHY_SOURCES) \
                       $(FPGA_RTL)/prbs_framegen.v $(FPGA_RTL)/prbs_checker.v \
                       $(FPGA_RTL)/cdc_event_counter.v $(FPGA_RTL)/prbs_raw.v $(FPGA_RTL)/loopback_regs.v \
                       $(FPGA_RTL)/pll_tx.v $(FPGA_RTL)/fwd_clk_out.v \
                       $(FPGA_RTL)/de10nano_phy_loopback.v \
                       $(REPO_ROOT)/tb/fpga_loopback/phy_jtag_stub.v \
                       $(REPO_ROOT)/tb/fpga_loopback/tb_fpga.v
COMPILE_ARGS        += -DSEGEL_SIM -I$(REPO_ROOT)/rtl/phy -I$(FPGA_RTL) -Ptb_fpga.TX_SEL=$(TX_SEL)

TOPLEVEL = tb_fpga
MODULE   = test
export TX_SEL
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/sw:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
