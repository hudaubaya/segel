# Makefile utama SEGEL — menjalankan seluruh test cocotb dari root repo.
#
#   make test                      semua test yang bisa dijalankan
#   make test-baseline             semua baseline TT07 yang punya RTL
#   make test-baseline-<nama>      satu baseline, mis. test-baseline-serdes_0200
#   make clean                     hapus artefak simulasi
#
# Test baseline dijalankan dengan Makefile upstream masing-masing (tidak
# diubah). Makefile upstream memakai $(PWD), jadi kita `cd` dulu, bukan
# `make -C`. cocotb 1.8 tidak selalu keluar non-zero saat test gagal, jadi
# results.xml diperiksa secara eksplisit.

SHELL        := /bin/bash
SIM          ?= icarus
BASELINE_DIR := rtl/baseline

# Baseline dengan RTL + testbench upstream yang bisa disimulasikan.
BASELINES    := serdes_0200 cdc_fifo_0036

# Baseline tanpa RTL sumber (hanya netlist gate-level). Lihat docs/baselines.md.
BASELINES_NO_RTL := crc8_0901

.PHONY: help test test-baseline clean \
        $(addprefix test-baseline-,$(BASELINES) $(BASELINES_NO_RTL))

help:
	@sed -n '3,6p' $(firstword $(MAKEFILE_LIST)) | sed 's/^# \{0,1\}//'

test: test-baseline

test-baseline: $(addprefix test-baseline-,$(BASELINES))

$(addprefix test-baseline-,$(BASELINES)): test-baseline-%:
	@echo "==> baseline $*"
	@cd $(BASELINE_DIR)/$*/test && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	@r=$(BASELINE_DIR)/$*/test/results.xml; \
	  test -f $$r || { echo "FAIL $*: $$r tidak ada"; exit 1; }; \
	  grep -q '<testcase' $$r || { echo "FAIL $*: tidak ada testcase di $$r"; exit 1; }; \
	  ! grep -qE '<(failure|error)' $$r || { echo "FAIL $*: ada test gagal, lihat $$r"; exit 1; }; \
	  echo "PASS $*"

$(addprefix test-baseline-,$(BASELINES_NO_RTL)): test-baseline-%:
	@echo "BLOCKED $*: RTL sumber tidak tersedia, hanya netlist gate-level."
	@echo "        Lihat docs/baselines.md bagian '$*'."
	@exit 1

clean:
	@for b in $(BASELINES); do \
	  rm -rf $(BASELINE_DIR)/$$b/test/{sim_build,results.xml,tb.vcd,__pycache__}; \
	done
