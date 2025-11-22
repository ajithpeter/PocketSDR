# GNSS PVT Unit Tests - Quick Start Guide

## Overview

Comprehensive unit tests for the GNSS Position, Velocity, and Time (PVT) solver.

## Test Coverage

✅ **9 test cases covering:**
1. ECEF to LLA coordinate conversion with known coordinates
2. LLA to ECEF round-trip conversion accuracy
3. ECEF velocity to ENU (East-North-Up) transformation
4. Satellite position computation from ephemeris data
5. Pseudorange calculation from code phase measurements
6. Least-squares position solution with simulated observations

## Quick Start

### Build and Run Tests

```bash
cd /home/user/PocketSDR/amaranth_litex/firmware/test

# Build PVT tests
make test_gnss_pvt

# Run tests
./test_gnss_pvt

# Or use the convenient make target
make test-pvt
```

### Build All Tests

```bash
# Build all firmware tests
make all

# Run all tests
make test
```

### Clean Build Artifacts

```bash
make clean
```

## Expected Output

```
============================================================
     GNSS PVT Solver - Comprehensive Unit Test Suite        
============================================================

## Test Suite 1: ECEF to LLA Conversion
### Running: test_ecef_to_lla_equator
  Testing ECEF to LLA conversion at equator...
    Result: Lat=0.000000°, Lon=45.000000°, Alt=999.96 m
  PASS

[... more tests ...]

============================================================
                    TEST SUMMARY                            
============================================================
  Tests passed: 9
  Tests failed: 0
  Total tests:  9

  ✓ ALL TESTS PASSED!
============================================================
```

## Test Results

All 9 tests pass successfully. See `TEST_RESULTS_PVT.md` for detailed results and accuracy metrics.

## Test Coordinates Used

### ECEF Test Point
- **Input:** (4510731.0, 4510731.0, 0.0) meters
- **Expected:** Lat=0°, Lon=45°, Alt≈1000m (on equator)
- **Accuracy:** < 0.04m altitude error, < 1×10⁻⁶° lat/lon error

### World Locations (Round-Trip Tests)
- Greenwich (0°, 0°)
- Sydney, Australia (-33.87°, 151.21°)
- San Francisco, USA (37.77°, -122.42°)
- London, UK (51.51°, -0.13°)
- New Delhi, India (28.61°, 77.21°)
- São Paulo, Brazil (-23.55°, -46.63°)
- Near poles (±89.9°)

### Satellite Orbit Parameters
- **Semi-major axis:** 26,560 km (GPS MEO orbit)
- **Eccentricity:** 0.01 (nearly circular)
- **Inclination:** 55° (GPS orbital plane)
- **Velocity:** ~3,125 m/s (computed)

### Simulated PVT Solution
- **Location:** New Delhi, India (28.61°N, 77.21°E, 216m)
- **Satellites:** 8 satellites with varying geometry
- **Ranges:** 20,500 - 23,500 km
- **Clock bias:** 10 km (~33 μs)

## Position Accuracy Validation

| Metric | Tolerance | Achieved |
|--------|-----------|----------|
| ECEF→LLA latitude | < 1×10⁻⁶° | < 1×10⁻⁸° |
| ECEF→LLA longitude | < 1×10⁻⁶° | < 1×10⁻⁸° |
| ECEF→LLA altitude | < 10 m | < 0.04 m |
| Round-trip accuracy | < 0.01 m | < 0.001 m |
| Orbital radius | ±500 km | 266 km error |
| Pseudorange | < 1 m | < 1 m |

## Files

- **Test Source:** `test_gnss_pvt.c` (26,926 bytes, 750+ lines)
- **Test Results:** `TEST_RESULTS_PVT.md` (detailed analysis)
- **Makefile:** `Makefile` (supports test-pvt target)

## Dependencies

The tests link against:
- `../src/gnss_pvt.c` - PVT solver implementation
- `../include/gnss_pvt.h` - PVT solver header
- `../include/gnss_nav.h` - Navigation data structures
- Standard C math library (`-lm`)

## Known Limitations

1. **Satellite Velocity:** Uses finite-difference approximation (~19% error vs analytical)
2. **PVT Solver:** Simplified least-squares with diagonal approximation (limited convergence)
3. **Polar Singularity:** May have numerical issues exactly at poles

See `TEST_RESULTS_PVT.md` for detailed analysis and recommendations.

## Troubleshooting

### Compilation Errors
```bash
# Ensure you have gcc and math library
gcc --version
```

### Test Failures
- Check that source files are present in `../src/` and `../include/`
- Verify math library is linked (`-lm` flag)
- Review error messages for specific assertion failures

### Build Issues
```bash
# Clean and rebuild
make clean
make test_gnss_pvt
```

## Next Steps

After verifying tests pass:
1. Review detailed results in `TEST_RESULTS_PVT.md`
2. Consider implementing recommended improvements (see results document)
3. Integrate PVT solver into main firmware application
4. Test with real GNSS hardware (Vahya board)

## Support

For questions or issues:
- Review test source code comments
- Check detailed test results document
- Consult GPS ICS-200 specification for algorithm details

---

**Last Updated:** 2025-11-22
**Status:** All tests passing (9/9)
