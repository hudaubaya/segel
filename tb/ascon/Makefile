# Test cocotb Ascon (rtl/ascon_core.v). Jalankan dari root: `make test-ascon`.
#
#   ASCON_SRC=<file>      RTL yang diuji (default rtl/ascon_core.v; dipakai uji mutasi)
#   ASCON_VECTORS=<dir>   vektor resmi (default .cache/ascon-vectors, `make ascon-vectors`)
#   ASCON_RANDOM_N=<n>    jumlah vektor acak (default 10000), ASCON_SEED=<s> seed-nya
#   TESTCASE=<a,b>        hanya test tertentu

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
ASCON_SRC ?= $(REPO_ROOT)/rtl/ascon_core.v

SIM_BUILD           ?= sim_build/rtl
COCOTB_RESULTS_FILE ?= results.xml
VERILOG_SOURCES     += $(ASCON_SRC) $(REPO_ROOT)/tb/ascon/tb.v
# Buffer plaintext 512 blok = 65536 bit, payload terpanjang di vektor ACVP.
COMPILE_ARGS        += -Ptb.PT_BUF_BLOCKS=512

TOPLEVEL = tb
MODULE   = test
export PYTHONPATH := $(REPO_ROOT)/model:$(REPO_ROOT)/tb/ascon:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
