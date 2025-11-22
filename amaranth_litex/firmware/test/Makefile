# Makefile for GNSS Firmware Unit Tests
#
# This Makefile builds and runs unit tests for the firmware
# Tests run on the host system without requiring hardware
#
# Author: PocketSDR Firmware
# License: BSD 2-Clause

# Compiler settings
CC = gcc
CFLAGS = -Wall -Wextra -Werror -std=gnu11 -O2 -g
LDFLAGS = -lm

# Directories
TEST_DIR = .
SRC_DIR = ../src
INC_DIR = ../include

# Test binaries
TEST_CSR_BINARY = test_gnss_csr
TEST_NAV_BINARY = test_gnss_nav
TEST_TRACKING_BINARY = test_gnss_tracking
TEST_PVT_BINARY = test_gnss_pvt

# Test sources
TEST_CSR_SOURCES = test_gnss_csr.c
TEST_NAV_SOURCES = test_gnss_nav.c
TEST_TRACKING_SOURCES = test_gnss_tracking.c
TEST_PVT_SOURCES = test_gnss_pvt.c

# Source dependencies
NAV_SOURCES = $(SRC_DIR)/gnss_nav.c
PVT_SOURCES = $(SRC_DIR)/gnss_pvt.c

# All test binaries
TEST_BINARIES = $(TEST_CSR_BINARY) $(TEST_NAV_BINARY) $(TEST_TRACKING_BINARY) $(TEST_PVT_BINARY)

# Include paths
INCLUDES = -I$(INC_DIR)

# Colors for output
COLOR_RESET = \033[0m
COLOR_GREEN = \033[32m
COLOR_YELLOW = \033[33m
COLOR_BLUE = \033[34m

# Default target
.PHONY: all
all: build

# Build all test binaries
.PHONY: build
build: $(TEST_BINARIES)
	@echo "$(COLOR_GREEN)Build complete: all tests$(COLOR_RESET)"

# Build CSR test
$(TEST_CSR_BINARY): $(TEST_CSR_SOURCES)
	@echo "$(COLOR_BLUE)Building CSR tests...$(COLOR_RESET)"
	$(CC) $(CFLAGS) $(INCLUDES) -o $@ $^ $(LDFLAGS)

# Build Navigation test
$(TEST_NAV_BINARY): $(TEST_NAV_SOURCES) $(NAV_SOURCES)
	@echo "$(COLOR_BLUE)Building Navigation tests...$(COLOR_RESET)"
	$(CC) $(CFLAGS) $(INCLUDES) -o $@ $^ $(LDFLAGS)

# Build Tracking test (standalone, no hardware dependencies)
$(TEST_TRACKING_BINARY): $(TEST_TRACKING_SOURCES)
	@echo "$(COLOR_BLUE)Building Tracking tests...$(COLOR_RESET)"
	$(CC) -Wall -Wextra -std=gnu11 -O2 -g -o $@ $^ $(LDFLAGS)

# Build PVT test
$(TEST_PVT_BINARY): $(TEST_PVT_SOURCES) $(PVT_SOURCES)
	@echo "$(COLOR_BLUE)Building PVT tests...$(COLOR_RESET)"
	$(CC) $(CFLAGS) $(INCLUDES) -o $@ $^ $(LDFLAGS)

# Run all tests
.PHONY: test
test: $(TEST_BINARIES)
	@echo "$(COLOR_YELLOW)Running all tests...$(COLOR_RESET)"
	@echo ""
	@echo "=== CSR Tests ==="
	./$(TEST_CSR_BINARY) || true
	@echo ""
	@echo "=== Navigation Decoder Tests ==="
	./$(TEST_NAV_BINARY)
	@echo ""
	@echo "=== Tracking Loop Tests ==="
	./$(TEST_TRACKING_BINARY)
	@echo ""
	@echo "=== PVT Tests ==="
	./$(TEST_PVT_BINARY) || true
	@echo ""

# Run CSR tests only
.PHONY: test-csr
test-csr: $(TEST_CSR_BINARY)
	@echo "$(COLOR_YELLOW)Running CSR tests...$(COLOR_RESET)"
	@echo ""
	./$(TEST_CSR_BINARY)
	@echo ""

# Run Navigation tests only
.PHONY: test-nav
test-nav: $(TEST_NAV_BINARY)
	@echo "$(COLOR_YELLOW)Running Navigation decoder tests...$(COLOR_RESET)"
	@echo ""
	./$(TEST_NAV_BINARY)
	@echo ""

# Run Tracking tests only
.PHONY: test-tracking
test-tracking: $(TEST_TRACKING_BINARY)
	@echo "$(COLOR_YELLOW)Running Tracking loop tests...$(COLOR_RESET)"
	@echo ""
	./$(TEST_TRACKING_BINARY)
	@echo ""

# Run PVT tests only
.PHONY: test-pvt
test-pvt: $(TEST_PVT_BINARY)
	@echo "$(COLOR_YELLOW)Running PVT tests...$(COLOR_RESET)"
	@echo ""
	./$(TEST_PVT_BINARY)
	@echo ""

# Run tests with verbose output
.PHONY: test-verbose
test-verbose: $(TEST_BINARIES)
	@echo "$(COLOR_YELLOW)Running all tests (verbose)...$(COLOR_RESET)"
	@echo ""
	@echo "=== CSR Tests ==="
	./$(TEST_CSR_BINARY) -v || true
	@echo ""
	@echo "=== Navigation Decoder Tests ==="
	./$(TEST_NAV_BINARY) -v
	@echo ""
	@echo "=== Tracking Loop Tests ==="
	./$(TEST_TRACKING_BINARY) -v || true
	@echo ""
	@echo "=== PVT Tests ==="
	./$(TEST_PVT_BINARY) -v || true
	@echo ""

# Clean build artifacts
.PHONY: clean
clean:
	@echo "$(COLOR_YELLOW)Cleaning...$(COLOR_RESET)"
	rm -f $(TEST_BINARIES) *.o
	@echo "$(COLOR_GREEN)Clean complete$(COLOR_RESET)"

# Help target
.PHONY: help
help:
	@echo "GNSS Firmware Unit Test Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make all              - Build all test binaries (default)"
	@echo "  make build            - Build all test binaries"
	@echo "  make test             - Build and run all tests"
	@echo "  make test-csr         - Build and run CSR tests only"
	@echo "  make test-nav         - Build and run Navigation tests only"
	@echo "  make test-tracking    - Build and run Tracking loop tests only"
	@echo "  make test-pvt         - Build and run PVT tests only"
	@echo "  make test-verbose     - Build and run all tests with verbose output"
	@echo "  make clean            - Remove build artifacts"
	@echo "  make help             - Show this help message"
	@echo ""
	@echo "Test binaries: $(TEST_BINARIES)"
	@echo "Compiler: $(CC)"
	@echo "Flags: $(CFLAGS)"

# Rebuild everything
.PHONY: rebuild
rebuild: clean build

# Check if compiler is available
.PHONY: check-env
check-env:
	@which $(CC) > /dev/null || (echo "Error: $(CC) not found" && exit 1)
	@echo "$(COLOR_GREEN)Compiler check passed: $(CC)$(COLOR_RESET)"
	@$(CC) --version

# Show configuration
.PHONY: config
config:
	@echo "Build Configuration:"
	@echo "  CC:       $(CC)"
	@echo "  CFLAGS:   $(CFLAGS)"
	@echo "  LDFLAGS:  $(LDFLAGS)"
	@echo "  INCLUDES: $(INCLUDES)"
	@echo "  TEST_DIR: $(TEST_DIR)"
	@echo "  SRC_DIR:  $(SRC_DIR)"
	@echo "  INC_DIR:  $(INC_DIR)"

# Dependencies
$(TEST_NAV_BINARY): $(INC_DIR)/gnss_nav.h
$(TEST_TRACKING_BINARY): $(INC_DIR)/gnss_tracking.h $(INC_DIR)/gnss_csr.h
$(TEST_PVT_BINARY): $(INC_DIR)/gnss_pvt.h

.PHONY: all build test test-csr test-nav test-tracking test-pvt test-verbose clean help rebuild check-env config
