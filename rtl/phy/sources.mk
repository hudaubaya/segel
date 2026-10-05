# Daftar sumber PHY (dipakai tb/phy*, Makefile root). REPO_ROOT harus sudah diset.
PHY_DIR     := $(REPO_ROOT)/rtl/phy
CDC_DIR     := $(REPO_ROOT)/rtl/cdc_fifo
PHY_SOURCES := $(PHY_DIR)/enc8b10b.v $(PHY_DIR)/dec8b10b.v $(PHY_DIR)/phy_serializer.v \
               $(PHY_DIR)/phy_deserializer.v $(PHY_DIR)/phy_comma_align.v \
               $(PHY_DIR)/phy_framer.v $(PHY_DIR)/phy_deframer.v $(PHY_DIR)/phy.v \
               $(REPO_ROOT)/rtl/crc8/crc8.v \
               $(CDC_DIR)/cdc_fifo.sv $(CDC_DIR)/dpram.sv $(CDC_DIR)/cdc_fifo_read_state.sv \
               $(CDC_DIR)/cdc_fifo_write_state.sv $(CDC_DIR)/binary_to_gray.sv \
               $(CDC_DIR)/gray_to_binary.sv $(CDC_DIR)/synchronizer.sv \
               $(CDC_DIR)/reset_synchronizer.sv
