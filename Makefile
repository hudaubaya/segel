# Makefile utama SEGEL — menjalankan seluruh test dari root repo.
#
#   make test                      semua test (model, RTL, gate-level, baseline)
#   make test-<nama>               satu target: model crc8 crc8-gl baseline-<baseline>
#   make sky130-cells              unduh model sel sky130_fd_sc_hd untuk simulasi GL
#   make clean                     hapus artefak simulasi (cache sel tidak ikut)
#
# Makefile cocotb memakai $(PWD), jadi kita `cd` dulu, bukan `make -C`.
# cocotb 1.8 tidak selalu keluar non-zero saat test gagal, jadi file
# results*.xml diperiksa secara eksplisit oleh check_results.

SHELL        := /bin/bash
SIM          ?= icarus
PYTHON       ?= python3
BASELINE_DIR := rtl/baseline

# Baseline dengan RTL + testbench upstream (Makefile upstream, tidak diubah).
BASELINES    := serdes_0200 cdc_fifo_0036

# Model sel sky130_fd_sc_hd untuk simulasi gate-level, dikunci ke satu commit.
SKY130_SC_HD_URL := https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd
SKY130_SC_HD_REV := 28c101fc5db17bb6cadefa4c2a146693c685f1dc
SKY130_SC_HD     ?= $(CURDIR)/.cache/sky130_fd_sc_hd
SKY130_STAMP     := $(SKY130_SC_HD)/.segel-rev-$(SKY130_SC_HD_REV)
CRC8_GL_NETLIST  := $(BASELINE_DIR)/crc8_0901/gl/tt_um_aidenfoxivey.v
CRC8_GL_CELLS    := $(shell grep -oE '^ *sky130_fd_sc_hd__[a-z0-9]+_[0-9]+' $(CRC8_GL_NETLIST) | \
                      sed -E 's/^ *sky130_fd_sc_hd__(.*)_[0-9]+$$/\1/' | sort -u)

# check_results <file> <label>
define check_results
	@r=$(1); \
	  test -f $$r || { echo "FAIL $(2): $$r tidak ada"; exit 1; }; \
	  grep -q '<testcase' $$r || { echo "FAIL $(2): tidak ada testcase di $$r"; exit 1; }; \
	  ! grep -qE '<(failure|error)' $$r || { echo "FAIL $(2): ada test gagal, lihat $$r"; exit 1; }; \
	  echo "PASS $(2)"
endef

.PHONY: help test test-model test-crc8 test-crc8-gl test-baseline sky130-cells clean \
        $(addprefix test-baseline-,$(BASELINES) crc8_0901)

help:
	@sed -n '3,7p' $(firstword $(MAKEFILE_LIST)) | sed 's/^# \{0,1\}//'

test: test-model test-crc8 test-crc8-gl test-baseline

test-model:
	@$(PYTHON) model/crc8.py

test-crc8:
	@echo "==> crc8 (RTL SEGEL)"
	@cd tb/crc8 && rm -f results_rtl.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/crc8/results_rtl.xml,crc8)

# Testbench crc8 yang sama, dijalankan pada netlist tapeout baseline #0901.
test-crc8-gl: $(SKY130_STAMP)
	@echo "==> crc8 (netlist gate-level baseline #0901)"
	@cd tb/crc8 && rm -f results_gl.xml && \
	  $(MAKE) --no-print-directory SIM=$(SIM) GATES=yes SKY130_SC_HD=$(SKY130_SC_HD)
	$(call check_results,tb/crc8/results_gl.xml,crc8-gl)

test-baseline: $(addprefix test-baseline-,$(BASELINES) crc8_0901)

$(addprefix test-baseline-,$(BASELINES)): test-baseline-%:
	@echo "==> baseline $*"
	@cd $(BASELINE_DIR)/$*/test && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,$(BASELINE_DIR)/$*/test/results.xml,$*)

# Baseline #0901 tidak punya RTL/testbench upstream; satu-satunya yang bisa
# diuji adalah netlist-nya, dengan testbench SEGEL.
test-baseline-crc8_0901: test-crc8-gl

sky130-cells: $(SKY130_STAMP)

$(SKY130_STAMP):
	@echo "==> unduh model sel sky130_fd_sc_hd @ $(SKY130_SC_HD_REV)"
	rm -rf $(SKY130_SC_HD)
	git init -q $(SKY130_SC_HD)
	git -C $(SKY130_SC_HD) remote add origin $(SKY130_SC_HD_URL)
	git -C $(SKY130_SC_HD) sparse-checkout set --no-cone '/models/**' \
	  $(foreach c,$(CRC8_GL_CELLS),'/cells/$(c)/*.v')
	git -C $(SKY130_SC_HD) fetch -q --depth 1 --filter=blob:none origin $(SKY130_SC_HD_REV)
	git -C $(SKY130_SC_HD) checkout -q FETCH_HEAD
	touch $@

clean:
	@for b in $(BASELINES); do \
	  rm -rf $(BASELINE_DIR)/$$b/test/{sim_build,results.xml,tb.vcd,__pycache__}; \
	done
	@rm -rf tb/crc8/{sim_build,results_rtl.xml,results_gl.xml,tb.vcd,__pycache__} model/__pycache__
