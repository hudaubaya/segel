# Makefile utama SEGEL — menjalankan seluruh test dari root repo.
#
#   make test                      semua test (model, RTL, gate-level, baseline, audit)
#   make test-<nama>               satu target: model crc8 crc8-gl cdc_fifo ascon ascon-mutants
#                                  phy phy-units fpga-loopback fpga-scripts baseline-<b> audit
#                                  audit-<a> (struktur butuh yosys, fpga-scripts butuh tclsh)
#   make sky130-cells              unduh model sel sky130_fd_sc_hd untuk simulasi GL
#   make ascon-vectors             unduh vektor uji resmi Ascon (ACVP NIST + KAT ascon-c)
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

# Vektor uji resmi Ascon (docs/ascon.md), dikunci ke commit + SHA-256.
ACVP_SERVER_REV  := 975de31eb83d87039ec88934fdc47d8c312b892d
ASCON_C_REV      := 446347f21b209f3921c65ece70027c366cbe1693
ASCON_VEC_SUMS   := tb/ascon/vectors.sha256
export ASCON_VECTORS ?= $(CURDIR)/.cache/ascon-vectors
ASCON_VEC_STAMP  := $(ASCON_VECTORS)/.segel-$(shell md5sum < $(ASCON_VEC_SUMS) | cut -c1-8)
ACVP_RAW         := https://raw.githubusercontent.com/usnistgov/ACVP-Server/$(ACVP_SERVER_REV)/gen-val/json-files
ASCON_C_RAW      := https://raw.githubusercontent.com/ascon/ascon-c/$(ASCON_C_REV)
# <path lokal>=<URL>
ASCON_VEC_FILES  := \
  acvp/Ascon-AEAD128-SP800-232/internalProjection.json=$(ACVP_RAW)/Ascon-AEAD128-SP800-232/internalProjection.json \
  acvp/Ascon-XOF128-SP800-232/internalProjection.json=$(ACVP_RAW)/Ascon-XOF128-SP800-232/internalProjection.json \
  ascon-c/LWC_AEAD_KAT_128_128.txt=$(ASCON_C_RAW)/crypto_aead/asconaead128/LWC_AEAD_KAT_128_128.txt \
  ascon-c/LWC_XOF_KAT_128_512.txt=$(ASCON_C_RAW)/crypto_hash/asconxof128/LWC_XOF_KAT_128_512.txt

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

.PHONY: help test test-model test-crc8 test-ascon test-ascon-model test-ascon-mutants test-ascon-synth \
        ascon-vectors test-phy test-phy-units test-phy-synth test-phy-fifo-struct \
        test-fpga-loopback test-fpga-scripts test-crc8-gl test-cdc_fifo test-cdc_fifo-struct test-baseline \
        test-cdc_fifo-meta test-sync_meta test-cdc_fifo-cyclonev test-cdc_fifo-cyclonev-struct \
        cdc_fifo-cyclonev \
        test-audit test-audit-struct-cdc_fifo sky130-cells clean \
        $(addprefix test-baseline-,$(BASELINES) crc8_0901) \
        $(addprefix test-audit-,$(AUDITS)) $(addprefix test-audit-gl-,$(AUDITS_GL)) test-audit-gl-gray

help:
	@sed -n '3,7p' $(firstword $(MAKEFILE_LIST)) | sed 's/^# \{0,1\}//'

test: test-model test-crc8 test-crc8-gl test-cdc_fifo test-cdc_fifo-struct test-cdc_fifo-meta \
      test-sync_meta test-cdc_fifo-cyclonev test-cdc_fifo-cyclonev-struct \
      test-ascon-model test-ascon test-ascon-mutants test-ascon-synth \
      test-phy-units test-phy test-phy-synth test-phy-fifo-struct \
      test-fpga-loopback test-fpga-scripts test-baseline test-audit

test-model:
	@$(PYTHON) model/crc8.py
	@$(PYTHON) model/enc8b10b.py
	@$(PYTHON) model/ascon.py
	@$(PYTHON) sw/ber.py --self-test

# Ascon-AEAD128 / Ascon-XOF128 (rtl/ascon_core.v, docs/ascon.md)
test-ascon-model: $(ASCON_VEC_STAMP)
	@echo "==> ascon (golden model vs vektor resmi)"
	@$(PYTHON) model/ascon.py
	@$(PYTHON) tb/ascon/check_model.py

test-ascon: $(ASCON_VEC_STAMP)
	@echo "==> ascon (RTL, vektor resmi + acak + tag salah + siklus)"
	@cd tb/ascon && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/ascon/results.xml,ascon)

# Tiga mutan (konstanta ronde, rotasi linear, perbandingan tag) harus membuat test gagal.
test-ascon-mutants: $(ASCON_VEC_STAMP)
	@echo "==> ascon (uji mutasi)"
	@$(PYTHON) tb/ascon/mutants.py

# RTL harus bisa disintesis (Yosys, gerbang generik) tanpa masalah struktural.
test-ascon-synth:
	@echo "==> ascon (sintesis Yosys)"
	@mkdir -p build/ascon
	@yosys -q -l build/ascon/synth.log -p "read_verilog rtl/ascon_core.v; synth -top ascon_core; \
	  check -assert; tee -q -o build/ascon/stat.txt stat"
	@sed -n '/Number of cells/p' build/ascon/stat.txt
	@echo "PASS ascon-synth"

ascon-vectors: $(ASCON_VEC_STAMP)

# PHY serial (rtl/phy/, docs/phy.md)
REPO_ROOT := $(CURDIR)
include rtl/phy/sources.mk

test-phy-units:
	@echo "==> phy (unit: 8b/10b exhaustive, comma aligner)"
	@cd tb/phy_units && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/phy_units/results.xml,phy-units)

test-phy:
	@echo "==> phy (loopback dua PHY: geseran bit, rasio clock, galat bit, batas laju)"
	@cd tb/phy && rm -f results.xml && $(MAKE) --no-print-directory SIM=$(SIM)
	$(call check_results,tb/phy/results.xml,phy)

test-phy-synth:
	@echo "==> phy (sintesis Yosys)"
	@mkdir -p build/phy
	@yosys -q -l build/phy/synth.log -p "read_verilog -sv -I rtl/phy $(PHY_SOURCES); \
	  synth -flatten -top phy; check -assert; tee -q -o build/phy/stat.txt stat"
	@sed -n '/Number of cells/p' build/phy/stat.txt
	@echo "PASS phy-synth"

# Uji loopback DE10-Nano (fpga/phy_loopback, docs/phy_howto.md). Tanpa Quartus/papan:
# simulasi top FPGA dengan model PLL/DDIO/JTAG pada ~25 dan ~5 Mbit/s, dan skrip
# Tcl (SDC, proyek, System Console) di tclsh dengan mock.
test-fpga-loopback:
	@echo "==> fpga/phy_loopback (simulasi top, TX_SEL 3 dan 0)"
	@cd tb/fpga_loopback && rm -f results_sel3.xml results_sel0.xml && \
	  $(MAKE) --no-print-directory SIM=$(SIM) TX_SEL=3 && $(MAKE) --no-print-directory SIM=$(SIM) TX_SEL=0
	$(call check_results,tb/fpga_loopback/results_sel3.xml,fpga-loopback-25M)
	$(call check_results,tb/fpga_loopback/results_sel0.xml,fpga-loopback-5M)

test-fpga-scripts:
	@echo "==> fpga/phy_loopback (SDC, proyek Quartus, System Console: tclsh + mock)"
	@$(PYTHON) tb/fpga_scripts/run_tests.py

# CDC FIFO yang dipakai PHY: DATA_WIDTH = 9 (8 data + flag K)
test-phy-fifo-struct:
	@echo "==> cdc_fifo 9 bit (struktur synchronizer, Yosys)"
	@$(PYTHON) tb/struct/check_cdc_regs.py --src rtl/cdc_fifo --data-width 9 --gray registered --reset synced

$(ASCON_VEC_STAMP): $(ASCON_VEC_SUMS)
	@echo "==> unduh vektor uji Ascon (ACVP-Server @ $(ACVP_SERVER_REV), ascon-c @ $(ASCON_C_REV))"
	rm -rf $(ASCON_VECTORS)
	@set -e; for e in $(ASCON_VEC_FILES); do \
	  f=$(ASCON_VECTORS)/$${e%%=*}; mkdir -p $$(dirname $$f); \
	  curl -fsSL --retry 3 -o $$f "$${e#*=}"; \
	done
	cd $(ASCON_VECTORS) && sha256sum --quiet -c $(CURDIR)/$(ASCON_VEC_SUMS)
	touch $@

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

# Test yang sama dengan model metastabilitas di synchronizer (`ifdef METASTABILITY_SIM).
test-cdc_fifo-meta:
	@echo "==> cdc_fifo (RTL SEGEL, model metastabilitas)"
	@cd tb/cdc_fifo && rm -f results_meta.xml && $(MAKE) --no-print-directory SIM=$(SIM) META=1
	$(call check_results,tb/cdc_fifo/results_meta.xml,cdc_fifo-meta)

# Uji unit model metastabilitas synchronizer, tanpa dan dengan model.
test-sync_meta:
	@echo "==> synchronizer (model metastabilitas, unit)"
	@cd tb/sync_meta && rm -f results.xml results_meta.xml && \
	  $(MAKE) --no-print-directory SIM=$(SIM) && $(MAKE) --no-print-directory SIM=$(SIM) META=1
	$(call check_results,tb/sync_meta/results.xml,sync_meta)
	$(call check_results,tb/sync_meta/results_meta.xml,sync_meta-meta)

# Netlist Cyclone V (Yosys synth_intel_alm, sel MISTRAL_*; bukan Quartus).
CV_NETLIST := build/cyclonev/cdc_fifo_cyclonev.v
CV_SOURCES := $(wildcard rtl/cdc_fifo/*.sv) fpga/cdc_fifo/synth_cyclonev.ys
cdc_fifo-cyclonev: $(CV_NETLIST)

$(CV_NETLIST): $(CV_SOURCES)
	@echo "==> sintesis cdc_fifo untuk Cyclone V (Yosys)"
	@mkdir -p build/cyclonev
	@yosys -q -l build/cyclonev/synth.log fpga/cdc_fifo/synth_cyclonev.ys
	@sed -n '/Number of cells/,/^$$/p' build/cyclonev/cdc_fifo_cyclonev_stat.txt

test-cdc_fifo-cyclonev: $(CV_NETLIST)
	@echo "==> cdc_fifo (netlist Cyclone V)"
	@cd tb/cdc_fifo_cv && rm -f results.xml && \
	  $(MAKE) --no-print-directory SIM=$(SIM) NETLIST=$(CURDIR)/$(CV_NETLIST)
	$(call check_results,tb/cdc_fifo_cv/results.xml,cdc_fifo-cyclonev)

test-cdc_fifo-cyclonev-struct:
	@echo "==> cdc_fifo (struktur synchronizer, netlist Cyclone V)"
	@$(PYTHON) tb/struct/check_cdc_regs.py --src rtl/cdc_fifo --target cyclonev --gray registered --reset synced


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
	@rm -rf tb/cdc_fifo/{sim_build,results.xml,results_meta.xml,tb.vcd,__pycache__} tb/common/__pycache__
	@rm -rf tb/sync_meta/{sim_build,results.xml,results_meta.xml,__pycache__}
	@rm -rf tb/cdc_fifo_cv/{sim_build,results.xml,tb.vcd,__pycache__} build
	@rm -rf tb/ascon/{sim_build,results.xml,ascon_cycles.json,__pycache__}
	@rm -rf tb/phy/{sim_build,results.xml,phy_bit_errors.json,__pycache__} tb/phy_units/{sim_build,results.xml,__pycache__}
	@rm -rf tb/fpga_loopback/{sim_build,results_sel*.xml,ber_sim_*,__pycache__} tb/fpga_scripts/__pycache__
