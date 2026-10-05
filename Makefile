# Makefile utama SEGEL — menjalankan seluruh test dari root repo.
#
#   make test                      semua test (model, RTL, gate-level, baseline, audit)
#   make test-<nama>               satu target: model crc8 crc8-gl cdc_fifo baseline-<b> audit audit-<a>
#                                  (struktur CDC butuh yosys)
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
# Netlist tapeout semua baseline; sel yang diunduh = gabungan sel yang dipakai.
GL_NETLISTS      := $(wildcard $(BASELINE_DIR)/*/gl/*.v)
GL_CELLS         := $(shell grep -ohE '^ *sky130_fd_sc_hd__[a-z0-9]+_[0-9]+' $(GL_NETLISTS) | \
                      sed -E 's/^ *sky130_fd_sc_hd__(.*)_[0-9]+$$/\1/' | sort -u)
GL_CELLS_HASH    := $(shell echo $(GL_CELLS) | md5sum | cut -c1-8)
SKY130_STAMP     := $(SKY130_SC_HD)/.segel-rev-$(SKY130_SC_HD_REV)-$(GL_CELLS_HASH)

# Audit baseline (docs/baseline_audit.md)
AUDITS           := serdes cdc_fifo
AUDITS_GL        := serdes cdc_fifo

# check_results <file> <label>
define check_results
	@r=$(1); \
	  test -f $$r || { echo "FAIL $(2): $$r tidak ada"; exit 1; }; \
	  grep -q '<testcase' $$r || { echo "FAIL $(2): tidak ada testcase di $$r"; exit 1; }; \
	  ! grep -qE '<(failure|error)' $$r || { echo "FAIL $(2): ada test gagal, lihat $$r"; exit 1; }; \
	  echo "PASS $(2)"
endef

.PHONY: help test test-model test-crc8 test-crc8-gl test-cdc_fifo test-cdc_fifo-struct test-baseline \
        test-audit test-audit-struct-cdc_fifo sky130-cells clean \
        $(addprefix test-baseline-,$(BASELINES) crc8_0901) \
        $(addprefix test-audit-,$(AUDITS)) $(addprefix test-audit-gl-,$(AUDITS_GL)) test-audit-gl-gray

help:
	@sed -n '3,7p' $(firstword $(MAKEFILE_LIST)) | sed 's/^# \{0,1\}//'

test: test-model test-crc8 test-crc8-gl test-cdc_fifo test-cdc_fifo-struct test-baseline test-audit

test-model:
	@$(PYTHON) model/crc8.py
	@$(PYTHON) model/enc8b10b.py

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

# CDC FIFO SEGEL (rtl/cdc_fifo/): turunan #0036 dengan perbaikan F1 dan F3.
test-cdc_fifo:
	@echo "==> cdc_fifo (RTL SEGEL)"
	@cd tb/cdc_fifo && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/cdc_fifo/results.xml,cdc_fifo)

# F5 + reset: pointer Gray lintas domain langsung dari flop, dan setiap flop
# ber-reset memakai reset tersinkron domainnya (sintesis Yosys).
test-cdc_fifo-struct:
	@echo "==> cdc_fifo (struktur synchronizer, Yosys)"
	@$(PYTHON) tb/struct/check_cdc_regs.py --src rtl/cdc_fifo --gray registered --reset synced

test-baseline: $(addprefix test-baseline-,$(BASELINES) crc8_0901)

$(addprefix test-baseline-,$(BASELINES)): test-baseline-%:
	@echo "==> baseline $*"
	@cd $(BASELINE_DIR)/$*/test && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,$(BASELINE_DIR)/$*/test/results.xml,$*)

# Baseline #0901 tidak punya RTL/testbench upstream; satu-satunya yang bisa
# diuji adalah netlist-nya, dengan testbench SEGEL.
test-baseline-crc8_0901: test-crc8-gl

# Audit baseline apa adanya. Cacat terkonfirmasi ditandai expect_fail di test,
# jadi target ini lulus selama perilaku baseline sama dengan yang dilaporkan.
# Audit CRC-8 (#0901) adalah test-crc8-gl.
test-audit: $(addprefix test-audit-,$(AUDITS)) $(addprefix test-audit-gl-,$(AUDITS_GL)) \
            test-audit-gl-gray test-audit-struct-cdc_fifo test-crc8-gl

# Baseline: synchronizer diumpan logika kombinasional dan reset tidak
# disinkronkan (keduanya diharapkan).
test-audit-struct-cdc_fifo:
	@echo "==> audit cdc_fifo (struktur synchronizer, Yosys)"
	@$(PYTHON) tb/struct/check_cdc_regs.py --src $(BASELINE_DIR)/cdc_fifo_0036/src --gray combinational --reset unsynced

$(addprefix test-audit-,$(AUDITS)): test-audit-%:
	@echo "==> audit $* (RTL)"
	@cd tb/audit/$* && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/audit/$*/results.xml,audit-$*)

$(addprefix test-audit-gl-,$(AUDITS_GL)): test-audit-gl-%: $(SKY130_STAMP)
	@echo "==> audit $* (netlist gate-level)"
	@cd tb/audit/gl && rm -f results_$*.xml && \
	  $(MAKE) --no-print-directory SIM=$(SIM) DESIGN=$* SKY130_SC_HD=$(SKY130_SC_HD)
	$(call check_results,tb/audit/gl/results_$*.xml,audit-gl-$*)

# F5: glitch pointer Gray di netlist #0036 (Verilog murni, bukan cocotb).
CDC_GL_NETLIST := $(BASELINE_DIR)/cdc_fifo_0036/gl/tt_um_pa1mantri_cdc_fifo.v
test-audit-gl-gray: $(SKY130_STAMP)
	@echo "==> audit cdc_fifo (glitch Gray, netlist gate-level)"
	@mkdir -p tb/audit/gl/sim_build && rm -f tb/audit/gl/sim_build/gray_glitch.vvp
	@set -o pipefail; iverilog -g2012 -grelative-include -DFUNCTIONAL -DUSE_POWER_PINS -DSIM -DUNIT_DELAY=\#1 \
	  -o tb/audit/gl/sim_build/gray_glitch.vvp tb/common/gl_stubs.v \
	  $$(grep -oE '^ *sky130_fd_sc_hd__[a-z0-9]+_[0-9]+' $(CDC_GL_NETLIST) | tr -d ' ' | sort -u | \
	     sed -E 's|^sky130_fd_sc_hd__(.*)_([0-9]+)$$|$(SKY130_SC_HD)/cells/\1/sky130_fd_sc_hd__\1_\2.v|') \
	  $(CDC_GL_NETLIST) tb/audit/gl/gray_glitch.v 2>&1 | { grep -vi warning || true; }
	@vvp -n tb/audit/gl/sim_build/gray_glitch.vvp | tail -3 | tee /dev/stderr | grep -q '^PASS'

sky130-cells: $(SKY130_STAMP)

$(SKY130_STAMP):
	@echo "==> unduh model sel sky130_fd_sc_hd @ $(SKY130_SC_HD_REV)"
	rm -rf $(SKY130_SC_HD)
	git init -q $(SKY130_SC_HD)
	git -C $(SKY130_SC_HD) remote add origin $(SKY130_SC_HD_URL)
	git -C $(SKY130_SC_HD) sparse-checkout set --no-cone '/models/**' \
	  $(foreach c,$(GL_CELLS),'/cells/$(c)/*.v')
	git -C $(SKY130_SC_HD) fetch -q --depth 1 --filter=blob:none origin $(SKY130_SC_HD_REV)
	git -C $(SKY130_SC_HD) checkout -q FETCH_HEAD
	touch $@

clean:
	@for b in $(BASELINES); do \
	  rm -rf $(BASELINE_DIR)/$$b/test/{sim_build,results.xml,tb.vcd,__pycache__}; \
	done
	@rm -rf tb/crc8/{sim_build,results_rtl.xml,results_gl.xml,tb.vcd,__pycache__} model/__pycache__
	@for a in $(AUDITS); do \
	  rm -rf tb/audit/$$a/{sim_build,results.xml,tb.vcd,__pycache__,audit_$$a.json}; \
	done
	@rm -rf tb/audit/gl/{sim_build,results_*.xml,__pycache__}
	@rm -rf tb/cdc_fifo/{sim_build,results.xml,tb.vcd,__pycache__} tb/common/__pycache__
