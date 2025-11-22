# Vahya GNSS SoC with GPSDO - Complete Build Guide

## Overview

This guide covers building the complete Vahya GNSS receiver SoC with integrated GPS Disciplined Oscillator (GPSDO) for the Lattice ECP5-25F FPGA.

**System Specifications:**
- **FPGA:** Lattice ECP5 LFE5U-25F-7BG256C
- **CPU:** VexRiscv RISC-V @ 48 MHz (minimal variant)
- **Memory:** 64 KB SRAM
- **GNSS Channels:** 8 (GPS L1 C/A + NavIC L5)
- **USB:** 2.0 High-Speed (480 Mbps via USB3343 ULPI)
- **GPSDO:** Integrated with ±21ns 1PPS accuracy

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Vahya GNSS SoC (ECP5-25F)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  VexRiscv    │    │    GNSS      │    │    GPSDO     │    │
│  │   RISC-V     │◄──►│   Baseband   │───►│  Disciplined │    │
│  │   @ 48 MHz   │    │  (8 channels)│    │  Oscillator  │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│         │                    │                    │            │
│         │                    │                    │            │
│  ┌──────┴────────────────────┴────────────────────┴──────┐    │
│  │              Wishbone Interconnect                     │    │
│  └──────┬────────────┬──────────┬──────────┬─────────────┘    │
│         │            │          │          │                   │
│  ┌──────┴───┐ ┌─────┴────┐ ┌──┴────┐ ┌──┴────┐              │
│  │   UART   │ │   SPI    │ │  GPIO │ │  USB  │              │
│  │ Console  │ │ MAX2771  │ │  LEDs │ │ ULPI  │              │
│  └──────────┘ └──────────┘ └───────┘ └───────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │              │            │           │
         ▼              ▼            ▼           ▼
      UART         MAX2771       Status      USB Host
     Console        GNSS RF        LEDs      Computer
                   Frontend
```

### Memory Map

| Address Range         | Module              | Size   | Description                    |
|-----------------------|---------------------|--------|--------------------------------|
| `0x00000000-0x0000FFFF` | SRAM              | 64 KB  | Main system memory            |
| `0x10000000-0x1000FFFF` | UART              | 64 KB  | Console UART                  |
| `0x20000000-0x2000FFFF` | SPI MAX2771       | 64 KB  | RF frontend configuration     |
| `0x30000000-0x3000FFFF` | GPIO              | 64 KB  | Status LEDs                   |
| `0x40000000-0x4000FFFF` | GNSS Baseband     | 64 KB  | Tracking and acquisition      |
| `0x50000000-0x5000FFFF` | USB Control       | 64 KB  | USB streaming control         |
| `0x60000000-0x6000FFFF` | **GPSDO**         | 64 KB  | **GPS disciplined oscillator**|
| `0xF0000000-0xFFFFFFFF` | SPI Flash         | 256 MB | Boot firmware and storage     |

### GPSDO CSR Map (Base: 0x60000000)

| Offset | Register           | Access | Description                        |
|--------|--------------------|--------|------------------------------------|
| 0x00   | Control            | RW     | Enable, reset, manual mode         |
| 0x04   | Status             | RO     | Locked, TOW valid, PPS active      |
| 0x08   | GPS TOW            | RW     | Time of Week (milliseconds)        |
| 0x0C   | TOW Update         | RW     | TOW update strobe                  |
| 0x10   | Kp Shift           | RW     | Proportional gain (default: 8)     |
| 0x14   | Ki Shift           | RW     | Integral gain (default: 16)        |
| 0x18   | Phase Error        | RO     | Phase error (ns, signed)           |
| 0x1C   | DAC Value          | RO     | Current DAC value                  |
| 0x20   | PPS Count          | RO     | 1PPS pulse counter                 |
| 0x24   | Manual DAC         | RW     | Manual DAC setting                 |

## Prerequisites

### Software Dependencies

```bash
# Operating System
Ubuntu 20.04 LTS or later (recommended)
Debian 11 or later

# Python
Python 3.8 or later

# Build Tools
sudo apt-get update
sudo apt-get install -y \
    git \
    build-essential \
    python3 \
    python3-pip \
    python3-dev \
    libffi-dev \
    libssl-dev

# LiteX and dependencies
pip3 install --user migen litex litex-boards

# Amaranth HDL
pip3 install --user amaranth amaranth-boards

# RISC-V Toolchain
# Download from: https://github.com/stnolting/riscv-gcc-prebuilt
# Or use pre-downloaded at: /home/user/tools/riscv-gcc/

# OSS CAD Suite (Yosys, nextpnr, etc.)
# Download from: https://github.com/YosysHQ/oss-cad-suite-build
# Or use pre-downloaded at: /home/user/tools/oss-cad-suite/
```

### Hardware Requirements

**Vahya Board:**
- Lattice ECP5 LFE5U-25F-7BG256C FPGA
- MAX2771 GNSS RF frontend
- USB3343 ULPI PHY
- 26 MHz crystal oscillator
- W25Q128 SPI Flash (16 MB)

**GPSDO External Components:**
- DAC: MCP4821, AD5061, or DAC8551 (12-16 bit)
- VCXO/OCXO: 10 MHz or 48 MHz
- Local oscillator with 1PPS output

**Programming:**
- JTAG programmer (FT2232H recommended)
- USB cable for UART console

## Build Process

### Step 1: Environment Setup

```bash
# Set up paths
export PATH="/home/user/tools/oss-cad-suite/bin:$PATH"
export PATH="/home/user/tools/riscv-gcc/bin:$PATH"

# Verify tools
yosys --version        # Should show 0.47 or later
riscv64-unknown-elf-gcc --version  # Should show 13.2.0

cd /home/user/PocketSDR/amaranth_litex
```

### Step 2: Generate GPSDO Verilog

```bash
cd src
python3 generate_gpsdo_verilog.py -o ../build/gpsdo.v -f 48

# Expected output:
# ✅ Generated: ../build/gpsdo.v
#    Size: 33,785 bytes
#    Lines: 963
```

### Step 3: Run Hardware Tests

```bash
# Test GNSS modules
python3 run_all_hardware_tests.py

# Test GPSDO specifically
cd src
python3 test_gpsdo.py

# Expected results:
# 6/6 tests passed
# ✅ ALL TESTS PASSED
```

### Step 4: Build Firmware

```bash
cd ../firmware

# Method 1: Using make (if available)
make clean
make all

# Method 2: Using build script
bash ../build_firmware_test.sh

# Expected output:
# gnss_csr.o (45 KB)
# gnss_tracking.o (101 KB)
# gnss_nav.o (57 KB)
# gnss_pvt.o (117 KB)
# main.o (57 KB)
```

### Step 5: Build Complete SoC (LiteX)

**Note:** This requires a full LiteX installation with all dependencies.

```bash
cd /home/user/PocketSDR/amaranth_litex/src

# Build with default configuration (8 channels, 48 MHz)
python3 vahya_gnss_soc.py --build

# Build with custom options
python3 vahya_gnss_soc.py --build --channels 8 --sys-clk 48

# Output files will be in: build/vahya/
```

### Step 6: Generate FPGA Bitstream

```bash
# Using LiteX builder (automatically done in step 5)
# Or manually with Yosys + nextpnr:

cd build/vahya/gateware

# Synthesize with Yosys
yosys -p "synth_ecp5 -top vahya_gnss -json vahya_gnss.json" vahya_gnss.v

# Place and route with nextpnr
nextpnr-ecp5 \
    --25k \
    --package CABGA256 \
    --speed 7 \
    --json vahya_gnss.json \
    --textcfg vahya_gnss.config \
    --lpf ../../../vahya.lpf

# Generate bitstream
ecppack --compress --svf vahya_gnss.svf vahya_gnss.config vahya_gnss.bit

# Expected output:
# vahya_gnss.bit (~500 KB)
# vahya_gnss.svf (for JTAG programming)
```

## Programming the FPGA

### Using openFPGALoader

```bash
# Load bitstream to SRAM (volatile, for testing)
openFPGALoader -c ft2232 build/vahya/gateware/vahya_gnss.bit

# Program to SPI Flash (persistent)
openFPGALoader -c ft2232 --write-flash build/vahya/gateware/vahya_gnss.bit
```

### Using JTAG (with Lattice Diamond Programmer)

```bash
# Use the generated .svf file
# File: build/vahya/gateware/vahya_gnss.svf
```

## Resource Utilization (ECP5-25F)

### Estimated Resources

| Resource | Used    | Total   | Percentage |
|----------|---------|---------|------------|
| LUTs     | ~8,500  | 24,000  | 35.4%      |
| FFs      | ~6,200  | 24,000  | 25.8%      |
| EBRs     | ~32     | 56      | 57.1%      |
| DSPs     | ~12     | 28      | 42.8%      |

### GPSDO Resources

| Module          | LUTs  | FFs   | Notes                    |
|-----------------|-------|-------|--------------------------|
| PPS_Generator   | ~80   | ~120  | 1PPS from GPS TOW        |
| PhaseDetector   | ~150  | ~200  | TIC with edge detection  |
| PIController    | ~200  | ~280  | PI with anti-windup      |
| DACInterface    | ~120  | ~150  | SPI master               |
| **Total GPSDO** | ~550  | ~750  | **2.3% of FPGA**        |

## Testing and Verification

### 1. UART Console Test

```bash
# Connect to UART (115200 baud, 8N1)
screen /dev/ttyUSB0 115200

# Or picocom
picocom -b 115200 /dev/ttyUSB0

# Expected output:
#        __   _ __      _  __
#       / /  (_) /____ | |/_/
#      / /__/ / __/ -_)>  <
#     /____/_/\__/\__/_/|_|
#
#  Vahya GNSS Receiver v0.2 (ECP5-25F)
#  (c) 2024 PocketSDR
```

### 2. GPSDO Status Check

```c
// From firmware console
litex> mem_read 0x60000004  // Read GPSDO status
litex> mem_read 0x60000018  // Read phase error
litex> mem_read 0x60000020  // Read PPS count
```

### 3. MAX2771 Configuration

```bash
# Configure MAX2771 via SPI
# Base address: 0x20000000

# Example: Set to GPS L1 mode
litex> spi_write 0x20000000 0x01  // Config register
litex> spi_write 0x20000000 0xA2  // GPS L1 settings
```

### 4. Signal Acquisition

Connect GPS antenna and monitor:
- Status LEDs should blink on signal acquisition
- UART should show satellite tracking status
- GPSDO PPS LED should blink once per second when locked

## GPSDO Operation

### Initialization

```c
// From firmware (gnss_pvt.c or main.c):

#include "gpsdo.h"

// Initialize GPSDO with default configuration
gpsdo_init(NULL);  // Uses default gains

// Or with custom configuration
gpsdo_config_t config = {
    .kp_shift = 8,              // Kp = 1/256
    .ki_shift = 16,             // Ki = 1/65536
    .lock_threshold_ns = 100,   // ±100 ns lock
    .holdover_timeout = 300     // 5 minutes
};
gpsdo_init(&config);

// Enable GPSDO
gpsdo_enable(true);
```

### Runtime Operation

```c
// Update GPS time (called from PVT solver)
void pvt_update_callback(uint32_t tow_ms, bool valid) {
    gpsdo_update_time(tow_ms, valid);
}

// Periodic monitoring (1 Hz timer)
void timer_1hz_callback(void) {
    gpsdo_periodic_update();

    // Print status
    gpsdo_print_status();

    // Check if locked
    gpsdo_status_t status;
    gpsdo_get_status(&status);

    if (status.locked) {
        printf("GPSDO LOCKED: %d ns error\n", status.phase_error_ns);
    }
}
```

### Monitoring

```c
// Get detailed statistics
gpsdo_stats_t stats;
gpsdo_get_statistics(&stats);

printf("Phase Error: min=%d, max=%d, avg=%d ns\n",
       stats.min_phase_error,
       stats.max_phase_error,
       stats.avg_phase_error);

printf("Lock time: %u seconds\n", stats.lock_time);
printf("Holdover events: %u\n", stats.holdover_events);
```

## Hardware Connections

### GPSDO External Wiring

```
FPGA Pin B2 (DAC_CS)   ──► MCP4821 Pin 2 (CS)
FPGA Pin C2 (DAC_CLK)  ──► MCP4821 Pin 3 (SCK)
FPGA Pin D2 (DAC_MOSI) ──► MCP4821 Pin 4 (SDI)
                              MCP4821 Pin 1 (VDD) ──► 3.3V
                              MCP4821 Pin 7 (VSS) ──► GND
                              MCP4821 Pin 8 (VOUT) ──► VCXO Control

FPGA Pin E2 (GPS_PPS)  ──► External GPS 1PPS output
FPGA Pin F2 (PPS_LED)  ──► Status LED + resistor to GND
FPGA Pin G2 (1PPS_OUT) ──► Disciplined 1PPS output
FPGA Pin H3 (LOCAL_PPS)◄── VCXO/OCXO 1PPS input
```

### Recommended Oscillators

| Type   | Stability      | Lock Time | Cost | Use Case              |
|--------|----------------|-----------|------|-----------------------|
| TCXO   | ±0.5 ppm       | ~1 min    | $    | General purpose       |
| VCTCXO | ±0.1 ppm       | ~5 min    | $$   | Medium stability      |
| OCXO   | ±0.01 ppm      | ~30 min   | $$$  | High stability        |

## Troubleshooting

### Build Issues

**Problem:** Yosys not found
```bash
# Solution: Add OSS CAD Suite to PATH
export PATH="/home/user/tools/oss-cad-suite/bin:$PATH"
```

**Problem:** RISC-V GCC not found
```bash
# Solution: Add RISC-V toolchain to PATH
export PATH="/home/user/tools/riscv-gcc/bin:$PATH"
```

**Problem:** LiteX import errors
```bash
# Solution: Install LiteX
pip3 install --user litex migen
```

### Runtime Issues

**Problem:** GPSDO not locking
- Check GPS antenna connection
- Verify GPS has valid fix (4+ satellites)
- Check local oscillator 1PPS signal
- Monitor phase error (should decrease over time)

**Problem:** Large phase error
- Adjust PI gains (increase Ki for faster convergence)
- Check DAC voltage range (should be 0-3.3V)
- Verify VCXO control range

**Problem:** Excessive jitter
- Check local oscillator quality
- Reduce PI gains (decrease Kp and Ki)
- Verify clean power supply

## Performance Metrics

### GPSDO Specifications

| Parameter              | Value         | Notes                    |
|------------------------|---------------|--------------------------|
| 1PPS Accuracy          | ±21 ns        | @ 48 MHz system clock    |
| Phase Resolution       | ~21 ns        | TIC-based                |
| Lock Threshold         | ±100 ns       | Configurable             |
| Lock Time (TCXO)       | 1-5 minutes   | Depends on oscillator    |
| Lock Time (OCXO)       | 10-30 minutes | Includes warmup          |
| Holdover Stability     | Platform dep. | TCXO: seconds, OCXO: hours|
| Default Kp             | 1/256         | Proportional gain        |
| Default Ki             | 1/65536       | Integral gain            |

### Expected Phase Error

| Condition               | Phase Error   | Notes                   |
|-------------------------|---------------|-------------------------|
| Initial acquisition     | ±10 ms        | GPS time alignment      |
| Acquiring lock          | ±1 ms → ±1 μs | PI controller settling  |
| Locked (TCXO)           | ±100 ns       | GPS + TCXO noise        |
| Locked (OCXO)           | ±50 ns        | GPS limited             |
| Holdover (TCXO, 1 min)  | ±10 μs        | TCXO drift              |
| Holdover (OCXO, 1 hour) | ±1 μs         | OCXO stability          |

## File Structure

```
amaranth_litex/
├── src/
│   ├── gpsdo.py                    # GPSDO Amaranth implementation
│   ├── test_gpsdo.py               # GPSDO test suite (6/6 pass)
│   ├── generate_gpsdo_verilog.py   # Verilog generator
│   ├── litex_gpsdo.py              # LiteX GPSDO wrapper
│   ├── vahya_gnss_soc.py           # Complete SoC with GPSDO
│   ├── gnss_baseband.py            # GNSS baseband processor
│   ├── navic_l5_gen.py             # NavIC L5 code generator (fixed)
│   └── run_all_hardware_tests.py   # Hardware validation (32/32 pass)
│
├── firmware/
│   ├── include/
│   │   └── gpsdo.h                 # GPSDO firmware API
│   ├── src/
│   │   ├── gpsdo.c                 # GPSDO firmware implementation
│   │   ├── gnss_tracking.c         # Tracking loop firmware
│   │   ├── gnss_nav.c              # Navigation decoder
│   │   ├── gnss_pvt.c              # PVT solver
│   │   └── main.c                  # Main firmware
│   └── Makefile
│
├── build/
│   ├── gpsdo.v                     # Generated GPSDO Verilog (33.8 KB)
│   └── vahya/                      # SoC build output
│       ├── gateware/
│       │   ├── vahya_gnss.v        # Complete SoC Verilog
│       │   ├── vahya_gnss.bit      # FPGA bitstream
│       │   └── vahya_gnss.svf      # JTAG programming file
│       └── software/
│           └── bios/
│               └── bios.bin        # Boot firmware
│
└── docs/
    ├── GPSDO_IMPLEMENTATION.md     # GPSDO architecture details
    ├── BUILD_VALIDATION_FINAL.md   # Test results (100% pass)
    ├── BUILD_TOOLS_VERIFICATION.md # Tool verification
    └── SOC_BUILD_GUIDE.md          # This file
```

## References

### Documentation
- [GPSDO Implementation Details](GPSDO_IMPLEMENTATION.md)
- [Build Validation Report](BUILD_VALIDATION_FINAL.md)
- [Build Tools Verification](BUILD_TOOLS_VERIFICATION.md)

### External Resources
- [Vahya Board Repository](https://github.com/ajithpeter/orbtrace/tree/vahya)
- [LiteX Documentation](https://github.com/enjoy-digital/litex)
- [Amaranth HDL Guide](https://amaranth-lang.org/docs/amaranth/latest/)
- [ECP5 FPGA Family](https://www.latticesemi.com/Products/FPGAandCPLD/ECP5)

### GPS/GNSS Standards
- IS-GPS-200 (GPS L1 C/A interface specification)
- IRNSS-ICD-SPS (NavIC L5 SPS interface specification)
- RFC 2783 (Pulse-Per-Second API)

## Support and Contributing

For issues, questions, or contributions:
- GitHub: https://github.com/ajithpeter/PocketSDR
- Issues: https://github.com/ajithpeter/PocketSDR/issues

## License

BSD 2-Clause License

## Version History

- v0.3 (2024-11-22): Added GPSDO integration, 100% test pass rate
- v0.2 (2024-11): NavIC L5 support, 8-channel baseband
- v0.1 (2024-10): Initial Vahya SoC implementation

---

**Build Status:** ✅ All hardware modules validated (100%)
**Test Coverage:** ✅ 32/32 hardware tests pass, 6/6 GPSDO tests pass
**Ready for:** SoC build and bitstream generation
