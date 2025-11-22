# GNSS Firmware Unit Tests

This directory contains unit tests for the PocketSDR GNSS firmware library components.

## Overview

The test suite validates core firmware functionality without requiring hardware, enabling rapid development and verification on host systems.

## Test Files

### test_gnss_csr.c
Unit tests for the GNSS CSR (Control/Status Register) library.

**Test Coverage:**
1. **Register Address Calculations** - Validates channel base address calculations and register offset mappings
2. **Frequency Word Calculations** - Tests GNSS_FREQ_TO_WORD macro for NCO frequency synthesis
3. **Correlation Power/Magnitude** - Verifies correlation result computations (I²+Q² power and magnitude)
4. **Doppler to Frequency Word Conversion** - Tests carrier Doppler frequency mapping
5. **Chip Rate to Frequency Word Conversion** - Validates code NCO frequency calculations for GPS L1 C/A and NavIC L5
6. **Edge Cases and Boundary Conditions** - Tests extreme values and wraparound behavior
7. **Known Values Verification** - Confirms against GNSS system parameters

**Test Statistics:**
- Total Tests: 64
- Test Categories: 7
- All tests passing ✓

## Building and Running Tests

### Prerequisites
- GCC compiler
- GNU Make
- Math library (libm)

### Build Commands

```bash
# Build all tests
make build

# Build and run all tests
make test

# Build and run CSR tests only
make test-csr

# Clean build artifacts
make clean

# Rebuild from scratch
make rebuild

# Show help
make help
```

### Test Output

Tests provide detailed output showing:
- Configuration parameters (sample rate, chip rates, NCO bits)
- Individual test results with PASS/FAIL status
- Informational messages showing calculated values
- Final summary with pass/fail counts

Example output:
```
=== Test 2: Frequency Word Calculations ===
  [PASS] Zero frequency -> word 0: expected=0x00000000, actual=0x00000000
  [INFO] GPS L1 C/A (1.023 MHz) -> 0x10000000 (ratio 0.062500)
  [PASS] GPS chip rate is ~6.25% of sample rate
```

## Test Architecture

### Design Principles

1. **No Hardware Dependencies** - Tests run entirely in software without FPGA or embedded target
2. **Standard C99** - Portable code using only standard library functions
3. **Simple Assertions** - Clear pass/fail criteria with helpful messages
4. **Realistic Test Cases** - Values based on actual GNSS parameters

### Test Structure

Each test file follows this pattern:
- Include necessary headers and define test macros
- Implement test functions for each feature area
- Use TEST_ASSERT macros for validation
- Provide main() function that runs all tests and reports results

### Test Macros

- `TEST_ASSERT(condition, message)` - Verify boolean condition
- `TEST_ASSERT_EQUAL(expected, actual, message)` - Check exact equality
- `TEST_ASSERT_DELTA(expected, actual, tolerance, message)` - Check approximate equality

## Key Test Parameters

### GNSS System Configuration
- **Sample Rate**: 16.368 MHz (Vahya MAX2771)
- **GPS L1 C/A Chip Rate**: 1.023 MHz
- **NavIC L5 Chip Rate**: 10.23 MHz
- **NCO Bits**: 32-bit

### Memory Map
- **GNSS Base**: 0x40000000
- **Global Base**: 0x40001000
- **Channel Spacing**: 0x100 (256 bytes per channel)
- **Number of Channels**: 8

### Frequency Word Calculation
```c
GNSS_FREQ_TO_WORD(freq, fs) = (uint32_t)((freq / fs) * 2^32)
```

## Validation Examples

### GPS L1 C/A Parameters
- Code length: 1023 chips
- Code period: 1 ms
- Chip rate: 1.023 MHz (exactly 1023 chips/ms)
- Frequency word: 0x10000000 (1/16 of sample rate)

### NavIC L5 Parameters
- Code length: 10230 chips
- Code period: 1 ms
- Chip rate: 10.23 MHz
- Frequency word: 0xA0000000 (10/16 of sample rate)

### Doppler Range
- Typical GPS Doppler: ±5 kHz
- Resolution: 0.0038 Hz (with 32-bit NCO)

## Adding New Tests

To add new test cases:

1. Create test function following naming convention `test_feature_name()`
2. Use TEST_ASSERT macros for validation
3. Add informative printf statements for debugging
4. Call function from main() test runner
5. Update this README with coverage information

## Continuous Integration

These tests are designed to run in CI/CD pipelines:
- Exit code 0 on success, 1 on failure
- No interactive input required
- Fast execution (< 1 second)
- Detailed output for debugging failures

## References

- GNSS CSR Header: `../include/gnss_csr.h`
- GNSS CSR Implementation: `../src/gnss_csr.c`
- Firmware README: `../README.md`

## License

BSD 2-Clause License (same as PocketSDR project)

## Author

PocketSDR Firmware Team
