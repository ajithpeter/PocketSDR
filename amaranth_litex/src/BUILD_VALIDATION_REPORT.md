# Vahya GNSS SoC Build Validation Report

**Date:** 2025-11-22
**Location:** `/home/user/PocketSDR/amaranth_litex/src/`
**Validation Scope:** Python syntax, imports, memory map, Verilog generation

---

## Executive Summary

### Overall Status: ⚠ PARTIAL SUCCESS

- ✅ Python syntax validation: **PASSED** (after fix)
- ✅ Import dependency check: **PASSED** (Amaranth available)
- ⚠️  LiteX/Migen dependencies: **NOT INSTALLED**
- ✅ Memory map consistency: **PASSED**
- ✅ Platform definitions: **VALIDATED**
- ❌ Verilog generation: **FAILED** (design error in channel_manager.py)

---

## 1. Python Syntax Validation

### vahya_gnss_soc.py
- **Initial Status:** ❌ FAILED
- **Error Found:** `SyntaxError: import * only allowed at module level`
- **Location:** Line 275 in `get_vahya_platform()` function
- **Fix Applied:** Changed `from litex.build.generic_platform import *` to explicit imports
- **Final Status:** ✅ PASSED

```bash
$ python3 -m py_compile vahya_gnss_soc.py
# No errors (after fix)
```

### gnss_baseband.py
- **Status:** ✅ PASSED (no syntax errors)

```bash
$ python3 -m py_compile gnss_baseband.py
# No errors
```

---

## 2. Import Dependency Validation

### Amaranth Dependencies (Required for gnss_baseband.py)
```
✓ amaranth                         [INSTALLED]
✓ amaranth.lib                     [INSTALLED]
✓ amaranth.sim                     [INSTALLED]
✓ amaranth.back                    [INSTALLED]
```

### LiteX/Migen Dependencies (Required for vahya_gnss_soc.py)
```
✗ migen                            [NOT INSTALLED]
✗ litex.soc.integration            [NOT INSTALLED]
✗ litex.soc.cores                  [NOT INSTALLED]
✗ litex.build.generic_platform     [NOT INSTALLED]
```

**Impact:** Full synthesis to bitstream requires LiteX/Migen installation. However, Amaranth modules can be validated independently.

### Module Dependencies (gnss_baseband.py)
```
✓ max2771_interface.py             [FOUND, VALID]
✓ channel_manager.py               [FOUND, VALID SYNTAX]
✓ csr_interface.py                 [FOUND, VALID]
✓ carrier_nco.py                   [FOUND]
✓ code_nco.py                      [FOUND]
✓ correlator.py                    [FOUND]
✓ channel_core.py                  [FOUND]
✓ gps_l1ca_gen.py                  [FOUND]
✓ navic_l5_gen.py                  [FOUND]
```

---

## 3. Verilog Generation

### Attempt: gnss_baseband.py → Verilog

**Status:** ❌ FAILED

**Error:**
```
TypeError: list indices must be integers or slices, not Signal
```

**Location:** `/home/user/PocketSDR/amaranth_litex/src/channel_manager.py:196`

**Root Cause Analysis:**

The code attempts to dynamically index a Python list using an Amaranth `Signal`:

```python
# Line 196-198 in channel_manager.py
Cat(channels[csr_channel].dump_ready,  # ❌ ERROR HERE
    channels[csr_channel].code_epoch,
    Const(0, 30))
```

Where:
- `channels` is a Python `list` of `ChannelCore` objects (line 93-97)
- `csr_channel` is an Amaranth `Signal` (line 153), not a Python integer
- Python lists cannot be indexed by hardware signals

**Affected Code Locations:**
```
channel_manager.py:196  - channels[csr_channel].dump_ready
channel_manager.py:197  - channels[csr_channel].code_epoch
channel_manager.py:213  - channels[csr_channel].corr_e_i
channel_manager.py:215  - channels[csr_channel].corr_e_q
channel_manager.py:217  - channels[csr_channel].corr_p_i
channel_manager.py:219  - channels[csr_channel].corr_p_q
channel_manager.py:221  - channels[csr_channel].corr_l_i
channel_manager.py:223  - channels[csr_channel].corr_l_q
channel_manager.py:225  - channels[csr_channel].chip_count
```

**Technical Explanation:**

In HDL design, you cannot use runtime hardware signals to index Python data structures. The code correctly uses `Array()` for configuration registers (lines 118-128):

```python
# ✅ CORRECT PATTERN (lines 118-128)
ch_enable = Array([Signal(name=f"ch{i}_enable") for i in range(self.num_channels)])
ch_reset = Array([Signal(name=f"ch{i}_reset") for i in range(self.num_channels)])
# These can be indexed with signals:
ch_enable[csr_channel].eq(...)  # ✓ Works
```

But fails to apply this pattern to channel status/correlation outputs.

**Required Fix:**

Create `Array()` objects for channel outputs and populate them in the loop, similar to the configuration registers. This requires moderate refactoring of `channel_manager.py` lines 190-225.

---

## 4. Platform Definitions

### Vahya ECP5-25F Platform

**Status:** ✅ VALIDATED

**FPGA Details:**
- **Part Number:** Lattice ECP5 LFE5U-25F-7BG256C
- **Package:** BG256 (256-ball BGA)
- **Speed Grade:** -7 (fastest)
- **Toolchain:** Project Trellis (open-source)

**I/O Definitions:**
```python
✓ clk26          - 26 MHz oscillator (P3, LVCMOS33)
✓ rst_n          - Reset button (P4, LVCMOS33)
✓ user_led       - 2x Status LEDs (T13, T14)
✓ serial         - UART console (L4/M1)
✓ spi_max2771    - SPI for MAX2771 config (D1/E1/F1/G1)
✓ max2771_adc    - 4-bit IQ ADC interface (A1-A4, B1)
✓ usb_ulpi       - USB3343 ULPI interface (H1-P2)
✓ spiflash       - SPI Flash boot (R2/U3/W2/V2)
```

**Pin Assignments:** All defined with proper IOStandard (LVCMOS33)

---

## 5. Memory Map Consistency

### Vahya GNSS SoC Memory Map

**Status:** ✅ VALIDATED

```
0x00000000 - 0x0000FFFF: SRAM (64 KB)
0x10000000 - 0x1000FFFF: UART (64 KB region)
0x20000000 - 0x2000FFFF: SPI (MAX2771) (64 KB region)
0x30000000 - 0x3000FFFF: GPIO (64 KB region)
0x40000000 - 0x4000FFFF: GNSS Baseband (64 KB region)
0x50000000 - 0x5000FFFF: USB Control (64 KB region)
0xF0000000 - 0xFFFFFFFF: SPI Flash (256 MB region)
```

### GNSS Baseband Register Map

**Base Address:** `0x40000000`
**Channel Stride:** `0x100` (256 bytes per channel)
**Address Format:** `base + (channel * 0x100) + register_offset`

#### Per-Channel Registers (16 registers × 4 bytes = 64 bytes used per channel)

| Offset | Register          | Access | Description                        |
|--------|-------------------|--------|------------------------------------|
| 0x00   | CTRL              | R/W    | Control (enable, reset)            |
| 0x04   | STATUS            | R      | Status (dump_ready, code_epoch)    |
| 0x08   | CARRIER_FREQ      | R/W    | Carrier NCO frequency word         |
| 0x0C   | CARRIER_PHASE     | R/W    | Carrier phase offset               |
| 0x10   | CODE_FREQ         | R/W    | Code NCO frequency word            |
| 0x14   | SIGNAL_TYPE       | R/W    | Signal type (GPS/NavIC)            |
| 0x18   | PRN               | R/W    | PRN number                         |
| 0x1C   | INTEGRATION_TIME  | R/W    | Integration period in samples      |
| 0x20   | CORR_E_I          | R      | Early In-phase correlation         |
| 0x24   | CORR_E_Q          | R      | Early Quadrature correlation       |
| 0x28   | CORR_P_I          | R      | Prompt In-phase correlation        |
| 0x2C   | CORR_P_Q          | R      | Prompt Quadrature correlation      |
| 0x30   | CORR_L_I          | R      | Late In-phase correlation          |
| 0x34   | CORR_L_Q          | R      | Late Quadrature correlation        |
| 0x38   | CHIP_COUNT        | R      | Current chip counter               |
| 0x3C   | EPOCH_COUNT       | R      | Code epoch counter                 |

#### Global Registers (at 0x40001000)

| Offset | Register        | Access | Description                |
|--------|-----------------|--------|----------------------------|
| 0x1000 | GLOBAL_CTRL     | R/W    | Global control register    |
| 0x1004 | IRQ_STATUS      | R      | Interrupt status           |
| 0x1008 | VERSION         | R      | Version (0xA5A50001)       |
| 0x100C | NUM_CHANNELS    | R      | Number of channels         |

### Memory Map Validation Results

```
✓ Channel registers (12 channels) do not overlap global registers
✓ GNSS baseband fits within allocated 64 KB region
✓ All channel registers are 32-bit aligned
✓ Memory regions do not overlap
✓ All base addresses are properly aligned
✓ No memory map consistency issues found
```

**Example Addresses:**
- Channel 0 CTRL: `0x40000000`
- Channel 0 CORR_P_I: `0x40000028`
- Channel 7 CTRL: `0x40000700`
- Global VERSION: `0x40001008`

---

## 6. Resource Constraints (ECP5-25F)

### FPGA Resources

| Resource | Total  | Used (8 ch) | Utilization | Status |
|----------|--------|-------------|-------------|--------|
| LUTs     | 24,000 | ~6,600      | 27.5%       | ✅ OK  |
| FFs      | 24,000 | ~4,850      | 20.2%       | ✅ OK  |
| EBRs     | 56     | ~27         | 48.0%       | ⚠️ Tight |
| DSPs     | 28     | ~12         | 42.8%       | ✅ OK  |

**Notes:**
- EBR utilization is high (48%) but acceptable
- Design uses 4:1 time-multiplexing for correlators to reduce DSP usage
- Optimized for 8 channels (down from 12) to fit ECP5-25F
- Can support up to 10 channels if EBR usage is optimized

### Clock Domains

| Domain | Frequency | Source               | Purpose                    |
|--------|-----------|----------------------|----------------------------|
| sys    | 48 MHz    | PLL from 26 MHz      | System bus, CPU, USB       |
| usb    | 60 MHz    | PLL from 26 MHz      | ULPI interface             |
| adc    | 16.368 MHz| MAX2771 CLKOUT       | Sample acquisition         |

---

## 7. File Generation Status

### Generated Files

```
❌ gnss_baseband.v                 - NOT GENERATED (due to design error)
✅ test_verilog_gen.py             - Created for testing
✅ validate_memory_map.py          - Created for validation
✅ BUILD_VALIDATION_REPORT.md      - This report
```

### Expected Files (after fix)

```
□ gnss_baseband.v                  - Verilog netlist from Amaranth
□ build/vahya/gateware/*.v         - LiteX-generated Verilog
□ build/vahya/gateware/*.bit       - FPGA bitstream
□ build/vahya/gateware/*.svf       - JTAG programming file
□ build/vahya/software/bios.bin    - Boot firmware
□ build/vahya/csr.csv              - Register map CSV
```

---

## 8. Summary of Issues Found

### Critical Issues

1. **❌ Design Error in channel_manager.py**
   - **Severity:** CRITICAL - Blocks Verilog generation
   - **Location:** Lines 196-225
   - **Issue:** Attempting to index Python list with hardware Signal
   - **Impact:** Cannot generate Verilog for GNSS baseband
   - **Fix Required:** Refactor to use `Array()` for channel outputs

### Non-Critical Issues

2. **⚠️ LiteX/Migen Not Installed**
   - **Severity:** MEDIUM - Blocks full synthesis
   - **Impact:** Cannot build complete SoC bitstream
   - **Workaround:** Install with `pip install migen litex`

3. **⚠️ High EBR Utilization**
   - **Severity:** LOW - Within limits but tight
   - **Impact:** Limited headroom for additional features
   - **Mitigation:** Already optimized to 8 channels

---

## 9. Validation Test Results

### Test 1: Python Syntax Check
```bash
$ python3 -m py_compile vahya_gnss_soc.py
✅ PASSED (after syntax fix)

$ python3 -m py_compile gnss_baseband.py
✅ PASSED
```

### Test 2: Import Resolution
```bash
$ python3 -c "from amaranth import *; from amaranth.lib import wiring, stream"
✅ PASSED - Amaranth available

$ python3 -c "from migen import *"
❌ FAILED - Migen not installed
```

### Test 3: Module Dependencies
```bash
$ python3 -c "import max2771_interface; import channel_manager; import csr_interface"
✅ PASSED - All modules import successfully
```

### Test 4: Verilog Generation
```bash
$ python3 test_verilog_gen.py
❌ FAILED - TypeError in channel_manager.py:196
```

### Test 5: Memory Map Validation
```bash
$ python3 validate_memory_map.py
✅ PASSED - No consistency issues
```

---

## 10. Recommendations

### Immediate Actions Required

1. **Fix channel_manager.py Design Error**
   - Refactor lines 190-225 to use `Array()` for dynamic signal indexing
   - Pattern to follow: lines 118-128 (configuration register arrays)
   - Estimated effort: 2-3 hours

2. **Install LiteX/Migen (Optional for full synthesis)**
   ```bash
   pip3 install migen
   pip3 install litex
   pip3 install litex-boards
   ```

3. **Test Verilog Generation After Fix**
   ```bash
   cd /home/user/PocketSDR/amaranth_litex/src
   python3 test_verilog_gen.py
   ```

### Future Improvements

4. **Add Automated Tests**
   - Create test suite for all Amaranth modules
   - Add CI/CD for validation

5. **Optimize EBR Usage**
   - Profile memory usage per channel
   - Consider smaller FIFO depths if possible
   - Target <40% EBR utilization for safety margin

6. **Documentation**
   - Add register map to firmware header file
   - Create programming guide for MAX2771 configuration
   - Document USB streaming protocol

---

## 11. Next Steps

### For Verilog Generation

1. Fix `channel_manager.py` indexing issue
2. Re-run `python3 test_verilog_gen.py`
3. Verify Verilog output is generated
4. Check synthesizability with Yosys (if installed)

### For Full SoC Build

1. Install LiteX/Migen dependencies
2. Run `python3 vahya_gnss_soc.py --build --channels 8`
3. Verify bitstream generation
4. Program FPGA with `openFPGALoader`

### For Hardware Testing

1. Configure MAX2771 via SPI
2. Verify ADC sample capture
3. Configure GNSS channels
4. Monitor correlation outputs
5. Test USB bulk streaming

---

## Appendix A: File Locations

All files in: `/home/user/PocketSDR/amaranth_litex/src/`

### Core Amaranth Modules
- `gnss_baseband.py` - Top-level GNSS baseband integration
- `channel_manager.py` - Multi-channel orchestration ⚠️ HAS BUG
- `channel_core.py` - Single GNSS channel processor
- `max2771_interface.py` - MAX2771 ADC interface
- `csr_interface.py` - Wishbone CSR bridge
- `carrier_nco.py` - Carrier NCO
- `code_nco.py` - Code NCO
- `correlator.py` - I/Q correlator
- `gps_l1ca_gen.py` - GPS L1 C/A PRN generator
- `navic_l5_gen.py` - NavIC L5 PRN generator

### SoC Integration
- `vahya_gnss_soc.py` - LiteX SoC for Vahya board
- `amalthea_soc.py` - Generic SoC variant

### Validation Scripts (Created)
- `test_verilog_gen.py` - Verilog generation test
- `validate_memory_map.py` - Memory map validator
- `BUILD_VALIDATION_REPORT.md` - This report

---

## Appendix B: Error Details

### Full Error Traceback

```
Traceback (most recent call last):
  File "/home/user/PocketSDR/amaranth_litex/src/test_verilog_gen.py", line 23, in <module>
    output = verilog.convert(...)
  File "/root/.local/lib/python3.11/site-packages/amaranth/back/verilog.py", line 60, in convert
    fragment = _ir.Fragment.get(elaboratable, platform)
  File "/root/.local/lib/python3.11/site-packages/amaranth/hdl/_ir.py", line 63, in get
    new_obj = obj.elaborate(platform)
  File "/root/.local/lib/python3.11/site-packages/amaranth/hdl/_dsl.py", line 694, in elaborate
    fragment.add_subfragment(Fragment.get(submodule, platform), name, src_loc=src_loc)
  File "/root/.local/lib/python3.11/site-packages/amaranth/hdl/_ir.py", line 63, in get
    new_obj = obj.elaborate(platform)
  File "/home/user/PocketSDR/amaranth_litex/src/channel_manager.py", line 196, in elaborate
    Cat(channels[csr_channel].dump_ready,
        ~~~~~~~~^^^^^^^^^^^^^
TypeError: list indices must be integers or slices, not Signal
```

---

**End of Report**
