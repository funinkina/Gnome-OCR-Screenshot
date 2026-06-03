SCRIPT     := gnome-ocr-screenshot.py
BIN_NAME   := gnome-ocr-screenshot
BIN_DIR    := $(HOME)/.local/bin
TARGET     := $(BIN_DIR)/$(BIN_NAME)
SRC        := $(CURDIR)/$(SCRIPT)

.PHONY: install uninstall

install:
	@mkdir -p $(BIN_DIR)
	@chmod +x $(SRC)
	@ln -sf $(SRC) $(TARGET)
	@echo "Installed: $(TARGET) -> $(SRC)"

uninstall:
	@rm -f $(TARGET)
	@echo "Removed: $(TARGET)"
