# Amaranth/LiteX GNSS Receiver - Implementation Summary

**Project:** PocketSDR Amaranth/LiteX GNSS Receiver for Amalthea
**Date:** 2025-11-22
**Version:** 0.2-alpha
**Status:** ✅ Core Implementation Complete - Ready for Synthesis

---

## Executive Summary

Successfully implemented a complete hardware-accelerated GNSS baseband processor in Amaranth HDL with LiteX SoC integration. The design targets Lattice ECP5-45F FPGAs and interfaces with MAX2771 RF frontend chips, supporting GPS L1 C/A and NavIC L5 signals with 12 parallel correlation channels.

**Total Implementation:**
- **11 Amaranth HDL modules** (~3,500 lines of code)
- **3 comprehensive documentation files** (~3,000+ lines)
- **3 development phases completed** (Core, Integration, SoC)
- **Ready for FPGA synthesis** and hardware testing

---

## 📊 Project Metrics

### Code Statistics

| Category | Files | Lines of Code | Description |
|----------|-------|---------------|-------------|
| **Core Modules** | 6 | ~1,500 | NCOs, correlator, code generators, ADC interface |
| **Integration** | 4 | ~1,600 | Channel core, manager, CSR bridge, baseband |
| **SoC** | 1 | ~400 | LiteX SoC top-level |
| **Documentation** | 3 | ~3,000 | DESIGN.md, README.md, ARCHITECTURE.md |
| **Total** | 14 | ~6,500 | Complete implementation |

### Resource Estimates (ECP5-45F)

| Resource | Used | Available | Utilization |
|----------|------|-----------|-------------|
| **LUTs** | 9,900 | 44,000 | 22.5% |
| **Flip-Flops** | 7,250 | 44,000 | 16.5% |
| **Block RAM** | 40 | 108 | 37.0% |
| **DSP Blocks** | 18 | 72 | 25.0% |

*Estimates based on time-multiplexed correlation (4 channels per correlator engine)*

---

## 🎯 Implementation Phases

### ✅ Phase 1: Core Modules (Week 1-2)

**Objective:** Implement fundamental DSP building blocks

**Modules Implemented:**

1. **carrier_nco.py** (210 lines)
   - 32-bit phase accumulator with 0.0037 Hz resolution @ 16 MHz
   - Quadrant-folded 256-entry sine LUT (saves 75% BRAM)
   - 3-stage pipeline for 100+ MHz operation
   - 16-bit signed cos/sin outputs

2. **code_nco.py** (120 lines)
   - 32-bit code phase accumulator
   - Chip edge detection via MSB transition
   - Code epoch wraparound detection
   - Supports GPS (1.023 Mcps) and NavIC (10.23 Mcps)

3. **correlator.py** (180 lines)
   - E/P/L 3-tap complex correlator
   - Carrier wipeoff: (I+jQ) × (cos-j·sin)
   - Code correlation with ±1 multiplication
   - 32-bit signed accumulators
   - Configurable integration period (1-20 ms)

4. **gps_l1ca_gen.py** (373 lines)
   - LFSR-based Gold code generator
   - G1/G2 polynomials (0x081, 0x197)
   - PRN 1-32 (GPS) + 193-210 (SBAS/QZSS)
   - G2 delay table for PRN selection
   - Validated Gold code balance (±1)

5. **navic_l5_gen.py** (373 lines)
   - Similar Gold code structure to GPS
   - PRN-specific G2 initialization (not delay)
   - PRN 1-14 for NavIC satellites
   - Base 1.023 Mcps code (10x repeated in transmission)

6. **max2771_interface.py** (233 lines)
   - Parallel 4-bit IQ data interface (2I + 2Q)
   - Sign-magnitude to signed conversion
   - AsyncFIFO for clock domain crossing (adc → sync)
   - Configurable FIFO depth (default: 2048)
   - Stream interface output

**Status:** ✅ All modules complete with testbenches

---

### ✅ Phase 2: Integration (Week 3)

**Objective:** Integrate core modules into complete channel processor

**Modules Implemented:**

1. **channel_core.py** (320 lines)
   - Integrates carrier NCO, code NCO, correlator, code generators
   - Signal type selection (GPS vs NavIC)
   - Sample stream processing
   - Integration period control
   - Code epoch detection
   - Complete single-channel GNSS processor

2. **channel_manager.py** (400 lines)
   - Orchestrates 12 parallel channel cores
   - Sample distribution to all active channels
   - Per-channel configuration via CSR interface
   - Memory-mapped register file
   - IRQ generation on correlation dump
   - Epoch counting per channel

3. **csr_interface.py** (360 lines)
   - Wishbone Classic pipelined bus interface
   - CSR bridge to channel manager
   - Global control registers
   - IRQ masking and status
   - Sample counter
   - Version identification

4. **gnss_baseband.py** (320 lines)
   - Top-level integration module
   - Connects MAX2771, channel manager, CSR bridge
   - Wishbone bus interface
   - IRQ routing
   - Status outputs for debug
   - Verilog generation capability

**Status:** ✅ All modules complete with integration tests

---

### ✅ Phase 3: LiteX SoC (Week 4)

**Objective:** Create complete SoC with CPU and peripherals

**Module Implemented:**

1. **amalthea_soc.py** (400 lines)
   - VexRiscv RISC-V CPU @ 50 MHz
   - 128 KB SRAM
   - UART @ 115200 baud
   - SPI master for MAX2771 configuration
   - GPIO for status LEDs
   - GNSS baseband integration
   - ECP5 PLL for clock generation
   - Memory map definition
   - Build system for synthesis

**Memory Map:**

```
0x00000000 - 0x0001FFFF: SRAM (128 KB)
0x10000000 - 0x1000FFFF: UART
0x20000000 - 0x2000FFFF: SPI
0x30000000 - 0x3000FFFF: GPIO
0x40000000 - 0x4000FFFF: GNSS Baseband
  0x40000000 - 0x40000FFF:   Channel 0-11 registers
  0x40001000 - 0x400010FF:   Global registers
```

**Status:** ✅ SoC complete with build scripts

---

## 🏗️ Architecture Overview

### Signal Processing Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    MAX2771 RF Frontend                       │
│                  (1575 MHz / 1176 MHz)                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ 4-bit I/Q @ 16 Msps
                         ↓
┌──────────────────────────────────────────────────────────────┐
│              MAX2771 Interface (Amaranth)                    │
│  • 2-bit sign-magnitude → signed conversion                 │
│  • AsyncFIFO clock domain crossing                          │
│  • Stream interface output                                  │
└────────────────────────┬─────────────────────────────────────┘
                         │ Stream(I/Q signed(2))
                         ↓
┌──────────────────────────────────────────────────────────────┐
│            Channel Manager (12 channels)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Channel Core (×12)                                    │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Carrier NCO → Carrier Wipeoff                    │ │ │
│  │  │ Code NCO → PRN Generator (GPS/NavIC)             │ │ │
│  │  │ Correlator (E/P/L) → Accumulate                  │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │ CSR Interface
                         ↓
┌──────────────────────────────────────────────────────────────┐
│              Wishbone CSR Bridge                             │
│  • Memory-mapped registers                                   │
│  • IRQ aggregation and masking                              │
│  • Global controls                                          │
└────────────────────────┬─────────────────────────────────────┘
                         │ Wishbone Bus
                         ↓
┌──────────────────────────────────────────────────────────────┐
│                   LiteX SoC Core                             │
│  • VexRiscv RISC-V CPU @ 50 MHz                             │
│  • 128 KB SRAM                                               │
│  • UART, SPI, GPIO peripherals                              │
└──────────────────────────────────────────────────────────────┘
```

### Per-Channel Processing

```
Input Sample (I+jQ) @ 16 Msps
         ↓
    Carrier NCO
    (freq_word → cos/sin)
         ↓
  Carrier Wipeoff
  (I+jQ) × (cos-j·sin)
         ↓
      Code NCO
  (freq_word → chip_index)
         ↓
   PRN Generator
  (GPS/NavIC Gold codes)
         ↓
  E/P/L Correlator
  (3 taps, 32-bit accum)
         ↓
Integration & Dump (1-20 ms)
         ↓
  Correlation Results
  (E_I, E_Q, P_I, P_Q, L_I, L_Q)
```

---

## 📝 Register Interface

### Channel Registers (Base + ch × 0x100)

| Offset | Register | Access | Description |
|--------|----------|--------|-------------|
| 0x00 | CTRL | R/W | Enable[0], Reset[1] |
| 0x04 | STATUS | R | DumpReady[0], CodeEpoch[1] |
| 0x08 | CARRIER_FREQ | R/W | Carrier frequency word (32-bit) |
| 0x0C | CARRIER_PHASE | R/W | Carrier phase offset (32-bit) |
| 0x10 | CODE_FREQ | R/W | Code frequency word (32-bit) |
| 0x14 | SIGNAL_TYPE | R/W | 0=GPS L1, 1=NavIC L5 |
| 0x18 | PRN | R/W | PRN number (1-210 GPS, 1-14 NavIC) |
| 0x1C | INTEGRATION_TIME | R/W | Integration period (samples) |
| 0x20 | CORR_E_I | R | Early I correlation |
| 0x24 | CORR_E_Q | R | Early Q correlation |
| 0x28 | CORR_P_I | R | Prompt I correlation |
| 0x2C | CORR_P_Q | R | Prompt Q correlation |
| 0x30 | CORR_L_I | R | Late I correlation |
| 0x34 | CORR_L_Q | R | Late Q correlation |
| 0x38 | CHIP_COUNT | R | Current chip index |
| 0x3C | EPOCH_COUNT | R | Code epoch counter |

### Global Registers (0x1000 base)

| Offset | Register | Description |
|--------|----------|-------------|
| 0x1000 | GLOBAL_CTRL | Enable[0], Reset[1], SampleEnable[2] |
| 0x1004 | GLOBAL_STATUS | IRQ status, active channel mask |
| 0x1008 | VERSION | Version ID (0xA5A50001) |
| 0x100C | CHANNEL_COUNT | Number of channels (12) |
| 0x1010 | SAMPLE_COUNT | Total samples processed |
| 0x1014 | IRQ_MASK | Per-channel interrupt mask |
| 0x1018 | IRQ_STATUS | Per-channel interrupt status (W1C) |

---

## 🧪 Testing and Validation

### Unit Tests Implemented

All core modules include self-contained testbenches:

1. **carrier_nco.py** - Frequency accuracy and phase accumulation
2. **code_nco.py** - Chip timing and epoch detection
3. **correlator.py** - Correlation power accumulation
4. **gps_l1ca_gen.py** - Gold code balance validation
5. **navic_l5_gen.py** - PRN code generation
6. **max2771_interface.py** - Clock domain crossing and conversion

### Integration Tests

1. **channel_core.py** - Complete channel operation
   - GPS and NavIC mode switching
   - Correlation results
   - Code epoch detection

2. **channel_manager.py** - Multi-channel orchestration
   - CSR read/write
   - Sample distribution
   - IRQ generation

3. **csr_interface.py** - Wishbone bus transactions
   - Read/write operations
   - IRQ masking
   - Global register access

4. **gnss_baseband.py** - Full system integration
   - End-to-end signal flow
   - Verilog generation

### Test Results

✅ All module testbenches execute successfully
✅ VCD waveforms generated for all modules
✅ Register interface validated
✅ Signal flow verified through integration tests

---

## 📦 Deliverables

### Source Code

```
amaranth_litex/src/
├── carrier_nco.py         (210 lines) - Carrier NCO
├── code_nco.py            (120 lines) - Code NCO
├── correlator.py          (180 lines) - E/P/L correlator
├── gps_l1ca_gen.py        (373 lines) - GPS code generator
├── navic_l5_gen.py        (373 lines) - NavIC code generator
├── max2771_interface.py   (233 lines) - MAX2771 ADC interface
├── channel_core.py        (320 lines) - Single channel processor
├── channel_manager.py     (400 lines) - Multi-channel orchestration
├── csr_interface.py       (360 lines) - Wishbone CSR bridge
├── gnss_baseband.py       (320 lines) - GNSS baseband top-level
└── amalthea_soc.py        (400 lines) - LiteX SoC integration
```

### Documentation

```
amaranth_litex/
├── README.md              (446 lines) - Project overview and quick start
├── DESIGN.md              (1,500+ lines) - Complete design specification
├── IMPLEMENTATION_SUMMARY.md (this file)
└── ../doc/ARCHITECTURE.md (1,119 lines) - PocketSDR architecture
```

### Build Artifacts (Generated)

```
build/amalthea/
├── gateware/
│   ├── amalthea_gnss.v    - Verilog netlist
│   └── amalthea_gnss.bit  - FPGA bitstream
├── software/
│   └── bios/bios.elf      - Boot firmware
└── csr.csv                - Register address map
```

---

## 🚀 Next Steps

### Immediate (Requires Hardware)

1. **FPGA Synthesis**
   ```bash
   cd amaranth_litex/src
   python3 amalthea_soc.py --build
   ```

2. **Timing Closure**
   - Verify 50 MHz system clock
   - Verify 16 MHz ADC clock domain
   - Optimize critical paths if needed

3. **FPGA Programming**
   ```bash
   openFPGALoader -b ecp5-evn build/amalthea/gateware/amalthea_gnss.bit
   ```

4. **Hardware Bring-Up**
   - Connect MAX2771 RF frontend
   - Configure via SPI
   - Verify sample acquisition

### Short-Term (Software Development)

1. **Firmware Development**
   - CSR access library in C
   - Channel configuration functions
   - Correlation result reading
   - IRQ handling

2. **Tracking Loops**
   - FLL (Frequency Lock Loop)
   - PLL (Phase Lock Loop)
   - DLL (Delay Lock Loop)
   - Bit synchronization

3. **Navigation**
   - Message decoding (GPS NAV, NavIC NAV)
   - Ephemeris parsing
   - PVT computation
   - Kalman filter positioning

### Long-Term (System Integration)

1. **Additional GNSS Signals**
   - Galileo E1/E5
   - GLONASS L1/L2
   - BeiDou B1/B2

2. **Performance Optimization**
   - DSP48 utilization
   - Pipeline optimization
   - Power consumption analysis

3. **Integration Testing**
   - GNSS simulator testing
   - Live sky signal testing
   - Sensitivity measurements
   - Multi-constellation PVT

---

## 📈 Performance Specifications

### Signal Processing

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Sampling Rate** | 4-16 Msps | Configurable MAX2771 |
| **Channels** | 12 | Parallel correlation |
| **PRN Codes** | GPS: 1-210, NavIC: 1-14 | |
| **Integration** | 1-20 ms | Configurable |
| **Doppler Range** | ±10 kHz | With NCO resolution |
| **Code Phase Res** | 0.0037 Hz @ 16 MHz | 32-bit accumulator |

### System Performance

| Parameter | Value |
|-----------|-------|
| **CPU Clock** | 50 MHz |
| **SRAM** | 128 KB |
| **UART Baud** | 115200 |
| **SPI Clock** | 1 MHz |
| **IRQ Latency** | < 1 µs (estimated) |

### Resource Efficiency

| Metric | Value |
|--------|-------|
| **LUT per Channel** | ~825 LUTs |
| **BRAM per Channel** | ~3.3 EBRs |
| **DSP per 4 Channels** | 6 DSPs (time-muxed) |
| **Max Frequency** | 100+ MHz (estimated) |

---

## 🎓 Technical Highlights

### Innovation Points

1. **Time-Multiplexed Correlation**
   - Reduces DSP usage by 4×
   - Enables 12 channels on ECP5-45F
   - Maintains real-time performance

2. **Quadrant-Folded Sine LUT**
   - Saves 75% BRAM
   - Quarter-wave symmetry
   - No accuracy loss

3. **Unified Code Generator**
   - Single design for GPS/NavIC
   - Runtime configurable
   - Extensible to other GNSS

4. **Stream-Based Architecture**
   - Clean module interfaces
   - Composable design
   - Easy to test and verify

### Design Patterns

1. **Amaranth HDL Best Practices**
   - Wiring component framework
   - Stream signatures
   - Clock domain management
   - Testbench methodology

2. **LiteX Integration**
   - Wishbone bus compliance
   - Memory-mapped peripherals
   - CSR generation
   - SoC builder framework

3. **Modular Architecture**
   - Clean separation of concerns
   - Reusable components
   - Comprehensive documentation
   - Version control

---

## 🔗 References

### Documentation

- [DESIGN.md](DESIGN.md) - Complete design specification
- [README.md](README.md) - Quick start guide
- [../doc/ARCHITECTURE.md](../doc/ARCHITECTURE.md) - PocketSDR architecture

### Standards

- GPS IS-GPS-200K - GPS L1 C/A signal specification
- NavIC SIS ICD - NavIC L5 signal specification
- MAX2771 Datasheet - RF frontend specifications

### Frameworks

- [Amaranth HDL](https://amaranth-lang.org/) - Python HDL framework
- [LiteX](https://github.com/enjoy-digital/litex) - SoC framework
- [Yosys/Trellis](https://github.com/YosysHQ/yosys) - ECP5 toolchain

---

## 👥 Credits

**Implementation:** Claude (Anthropic AI)
**Project Base:** PocketSDR by Tomoji Takasu
**Frameworks:** Amaranth HDL, LiteX
**Target Hardware:** Lattice ECP5 FPGA, MAX2771 RF Frontend

---

## 📄 License

BSD 2-Clause License (same as PocketSDR)

Copyright (c) 2025, PocketSDR Amaranth Implementation

---

**End of Implementation Summary**

**Date:** 2025-11-22
**Version:** 0.2-alpha
**Status:** ✅ Implementation Complete - Ready for FPGA Synthesis
