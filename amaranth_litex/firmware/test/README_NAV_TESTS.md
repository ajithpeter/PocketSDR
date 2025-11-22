# GNSS Navigation Decoder Unit Tests

## Overview

This test suite provides comprehensive unit tests for the GPS and NavIC navigation message decoders used in the PocketSDR GNSS receiver firmware.

## Test Coverage

The test suite validates the following functionality:

### 1. **GPS Preamble Detection** (`test_gps_preamble_detection`)
Tests the ability to detect the GPS navigation message preamble pattern (0x8B = 10001011):
- Normal preamble detection (0x8B)
- Inverted preamble detection (0x74)
- False pattern rejection
- Preamble detection at various bit offsets

**GPS Preamble Format:**
```
Binary:  1 0 0 0 1 0 1 1
Hex:     0x8B
Purpose: Identifies start of TLM word (Word 1) in each subframe
```

### 2. **GPS Word Parity Checking** (`test_gps_word_parity`)
Validates GPS word parity checking and data extraction:
- 30-bit word structure (24 data + 6 parity)
- Parity bit removal
- Sequential word validation
- Data integrity checks

**GPS Word Structure:**
```
|<---- 24 data bits ---->|<- 6 parity bits ->|
 Bits 1-24                Bits 25-30
```

### 3. **GPS Subframe Decoding** (`test_gps_subframe_decoding`)
Tests decoding of GPS navigation subframes:
- Subframe 1: Clock correction and health data
- Subframe 2: Ephemeris parameters (part 1)
- Subframe 3: Ephemeris parameters (part 2)
- Subframe ID extraction from HOW word
- Complete ephemeris validation

**Subframe Structure:**
```
Subframe (300 bits, 6 seconds):
  Word 1:  TLM (Telemetry Word with preamble)
  Word 2:  HOW (Handover Word with subframe ID)
  Words 3-10: Subframe-specific data
```

### 4. **NavIC Sync Pattern Detection** (`test_navic_sync_detection`)
Tests NavIC-specific synchronization:
- Sync pattern 0xEB90 detection
- False pattern rejection
- Partial pattern handling

**NavIC Sync Pattern:**
```
Hex:    0xEB90
Binary: 1110 1011 1001 0000
Length: 16 bits
```

### 5. **Ephemeris Parameter Extraction** (`test_ephemeris_extraction`)
Validates extraction of satellite orbital parameters:
- Clock parameters: toc, af0, af1, af2
- Orbital elements: sqrt(A), e, i0, OMEGA0, omega, M0
- Correction terms: cuc, cus, crc, crs, cic, cis
- Health and accuracy indicators
- API retrieval functions

**Key Parameters:**
- **sqrt(A)**: Square root of semi-major axis (~5153 m^0.5 for GPS)
- **e**: Eccentricity (~0.01 for GPS orbits)
- **af0, af1, af2**: Clock bias, drift, and drift rate

### 6. **Bit Synchronization** (`test_bit_synchronization`)
Tests bit-level synchronization and buffering:
- Frame synchronization acquisition
- Bit buffer management
- Word boundary detection
- 30-bit word collection
- Subframe assembly (10 words)

**Bit Processing Flow:**
```
Raw bits → Bit buffer → Preamble search → Frame sync
  ↓
30-bit words → Parity check → Subframe assembly
  ↓
Subframe decode → Ephemeris extraction
```

### 7. **End-to-End Navigation Processing** (`test_e2e_navigation_processing`)
Complete navigation message processing:
- Full subframe bit-by-bit transmission
- Complete ephemeris assembly (Subframes 1-3)
- Multi-subframe state management
- Final ephemeris validation

**Test Sequence:**
1. Send 300 bits for Subframe 1 → Extract clock data
2. Send 300 bits for Subframe 2 → Extract ephemeris part 1
3. Send 300 bits for Subframe 3 → Extract ephemeris part 2
4. Validate complete ephemeris

### 8. **Error Handling and Edge Cases** (`test_error_handling`)
Tests robustness and error conditions:
- Invalid bit handling (bit = 0 means no data)
- Ephemeris retrieval before data ready
- Multiple decoder initializations
- State reset verification
- NavIC decoder edge cases

## Building and Running

### Prerequisites
- GCC compiler (native, not RISC-V cross-compiler)
- Make
- Math library support (-lm)

### Build Commands

```bash
# Navigate to test directory
cd /home/user/PocketSDR/amaranth_litex/firmware/test

# Clean previous build
make clean

# Build navigation tests only
make test_gnss_nav

# Build and run navigation tests
make test-nav

# Build and run all tests (CSR + Navigation)
make test

# Verbose test output
make test-verbose

# Show available targets
make help
```

### Expected Output

```
╔════════════════════════════════════════════════════════════════╗
║      GNSS Navigation Decoder Unit Test Suite                  ║
║      PocketSDR Firmware - Test Version 1.0                    ║
╚════════════════════════════════════════════════════════════════╝

[TEST 1] GPS Preamble Detection (0x8B pattern)
  ✓ PASS: Normal preamble 0x8B detected
  ✓ PASS: Inverted preamble 0x74 detected
  ...

╔════════════════════════════════════════════════════════════════╗
║                     TEST SUMMARY                               ║
╠════════════════════════════════════════════════════════════════╣
║  Total Tests Run:    8                                         ║
║  Assertions Passed:  XX                                        ║
║  Assertions Failed:  XX                                        ║
║  Success Rate:       XX.X%                                     ║
╚════════════════════════════════════════════════════════════════╝
```

## Test Vectors

### GPS Navigation Message Test Data

The test suite includes sample GPS navigation message data:

#### **Subframe 1 Sample** (Clock and Health)
```c
gps_subframe1_sample[10] = {
    0x22C00000,  // Word 1: TLM with preamble 0x8B
    0x00001684,  // Word 2: HOW with subframe ID = 1
    0x3FFC1234,  // Word 3: Week, health, URA
    ...
    0x00100000   // Word 9: af0 (clock bias)
};
```

#### **Subframe 2 Sample** (Ephemeris Part 1)
```c
gps_subframe2_sample[10] = {
    0x22C00000,  // Word 1: TLM
    0x00002684,  // Word 2: HOW with subframe ID = 2
    0x01001000,  // Word 3: IODE, crs
    ...
    0x5153A000   // Word 9: sqrt(A) LSBs (~26560 km)
};
```

#### **Subframe 3 Sample** (Ephemeris Part 2)
```c
gps_subframe3_sample[10] = {
    0x22C00000,  // Word 1: TLM
    0x00003684,  // Word 2: HOW with subframe ID = 3
    0x00100000,  // Word 3: cic, OMEGA0 MSBs
    ...
    0x01000100   // Word 10: IODE, IDOT
};
```

### Test Patterns

**Preamble Patterns:**
- Normal: `{1,0,0,0,1,0,1,1}` = 0x8B
- Inverted: `{0,1,1,1,0,1,0,0}` = 0x74
- Invalid: `{1,1,1,1,0,0,0,0}` = 0xF0

**NavIC Sync:**
- Valid: `{1,1,1,0,1,0,1,1,1,0,0,1,0,0,0,0}` = 0xEB90

## GPS Navigation Message Reference

### Frame Structure
- **Frame**: 5 subframes × 300 bits = 1500 bits (30 seconds)
- **Subframe**: 10 words × 30 bits = 300 bits (6 seconds)
- **Word**: 24 data bits + 6 parity bits = 30 bits (0.6 seconds)
- **Bit**: 20 milliseconds (50 bps data rate)

### Timing
```
|<-------------- Frame (30 sec) -------------->|
|<--- SF1 --->|<--- SF2 --->|<--- SF3 --->|...
|  6 sec      |  6 sec      |  6 sec      |...
```

### Subframe Content

**Subframe 1 (Clock & Health):**
- GPS week number
- SV health and accuracy
- Clock corrections: toc, af0, af1, af2
- IODC (Issue of Data, Clock)

**Subframe 2 (Ephemeris Part 1):**
- IODE (Issue of Data, Ephemeris)
- crs, delta_n (orbit corrections)
- M0 (mean anomaly)
- cuc, cus (argument of latitude corrections)
- e (eccentricity)
- sqrt(A) (semi-major axis)
- toe (ephemeris reference time)

**Subframe 3 (Ephemeris Part 2):**
- cic, cis (inclination corrections)
- OMEGA0 (longitude of ascending node)
- i0 (inclination angle)
- crc (orbit radius corrections)
- omega (argument of perigee)
- OMEGA_DOT (rate of right ascension)
- IDOT (rate of inclination)

**Subframes 4-5:**
- Almanac data
- Ionospheric model
- UTC parameters
- Satellite health (all SVs)

## Understanding Test Results

### Success Indicators
- ✓ **Green checkmark**: Test assertion passed
- ✗ **Red X**: Test assertion failed
- 🎉 **All tests PASSED**: 100% success rate

### Common Failure Modes

1. **Preamble Detection Failures**
   - Cause: Bit ordering mismatch
   - Fix: Ensure MSB-first bit processing

2. **Subframe ID Extraction Failures**
   - Cause: Incorrect HOW word format
   - Fix: Verify bits 20-22 contain subframe ID

3. **Ephemeris Not Valid**
   - Cause: Incomplete subframe collection
   - Fix: Ensure all 3 subframes (1-3) received

4. **Synchronization Failures**
   - Cause: Bit buffer management issues
   - Fix: Verify 30-bit word boundaries

## Test Framework Details

### Assertion Macros

```c
TEST_START(name)
  - Starts a new test case
  - Increments test counter
  - Prints test name

TEST_ASSERT(condition, message)
  - Checks boolean condition
  - Prints PASS/FAIL with message
  - Updates pass/fail counters

TEST_ASSERT_EQ(expected, actual, message)
  - Checks equality
  - Shows expected vs actual values
  - Useful for integer comparisons

TEST_ASSERT_NEAR(expected, actual, tolerance, message)
  - Checks floating-point equality within tolerance
  - Shows difference and tolerance
  - Essential for ephemeris parameter validation
```

### Test Statistics

The test framework automatically tracks:
- Total number of test cases
- Total assertions executed
- Passed assertion count
- Failed assertion count
- Success rate percentage

## Extending the Tests

### Adding New Test Cases

1. **Create test function:**
```c
void test_new_feature(void) {
    TEST_START("New Feature Description");

    // Setup
    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Execute
    bool result = new_function(&nav);

    // Verify
    TEST_ASSERT(result, "Feature works correctly");
}
```

2. **Add to main():**
```c
int main(int argc, char *argv[]) {
    ...
    test_gps_preamble_detection();
    test_new_feature();  // Add here
    ...
}
```

### Adding New Test Vectors

Create new test data arrays:
```c
static const uint32_t custom_subframe[] = {
    0x22C00000,  // TLM
    0x00001684,  // HOW
    // ... your data
};
```

## Troubleshooting

### Build Errors

**Error:** `gcc: command not found`
- **Solution:** Install GCC: `sudo apt-get install build-essential`

**Error:** `gnss_nav.h: No such file or directory`
- **Solution:** Check include path: `-I../include`

### Runtime Errors

**Issue:** All preamble tests fail
- **Check:** Bit buffer ordering (MSB vs LSB first)
- **Verify:** Preamble constant matches GPS spec (0x8B)

**Issue:** Subframe ID always 0
- **Check:** HOW word format
- **Verify:** Bits 20-22 contain subframe ID (1-5)

**Issue:** Ephemeris never valid
- **Check:** All 3 subframes (1-3) received
- **Verify:** `eph_received[]` array flags

## Integration with Hardware

While these tests run on the host system, the same decoder functions are used in the RISC-V firmware on the Vahya board. The tests validate:

1. **Algorithm correctness** - independent of hardware
2. **Data format compliance** - GPS IS-GPS-200 standard
3. **API contract** - function interfaces and return values
4. **Error handling** - robustness to invalid inputs

## References

### GPS Specifications
- **IS-GPS-200**: Interface Specification for GPS L1 C/A
- **ICD-GPS-200**: Interface Control Document (older version)

### NavIC Specifications
- **IRNSS-ICD-SPS**: NavIC Signal-in-Space ICD

### Key Formulas

**Semi-major axis from sqrt(A):**
```
A = sqrt(A)² meters
```

**GPS Time:**
```
GPS Time = Week × 604800 + TOW seconds
```

**Parity Checking:**
```
Hamming code (30,24) with D1-D24 data bits and D25-D30 parity bits
```

## File Locations

- **Test Source:** `/home/user/PocketSDR/amaranth_litex/firmware/test/test_gnss_nav.c`
- **Decoder Header:** `/home/user/PocketSDR/amaranth_litex/firmware/include/gnss_nav.h`
- **Decoder Source:** `/home/user/PocketSDR/amaranth_litex/firmware/src/gnss_nav.c`
- **Test Makefile:** `/home/user/PocketSDR/amaranth_litex/firmware/test/Makefile`
- **Test Results:** `/home/user/PocketSDR/amaranth_litex/firmware/test/TEST_RESULTS.md`

## License

BSD 2-Clause License (same as PocketSDR firmware)

---

**Last Updated:** 2025-11-22
**Test Version:** 1.0
**Firmware Version:** Compatible with Vahya GNSS Receiver Firmware
