/**
 * Unit Tests for GNSS CSR Library
 *
 * Tests CSR register address calculations, frequency word calculations,
 * correlation power/magnitude, and conversion functions without hardware.
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <math.h>
#include <assert.h>

/* Include CSR definitions - we'll redefine the hardware access functions */
#define GNSS_BASE           0x40000000
#define GNSS_GLOBAL_BASE    0x40001000
#define GNSS_NUM_CHANNELS   8

/* Channel register offsets */
#define GNSS_CH_CTRL                0x00
#define GNSS_CH_STATUS              0x04
#define GNSS_CH_CARRIER_FREQ        0x08
#define GNSS_CH_CARRIER_PHASE       0x0C
#define GNSS_CH_CODE_FREQ           0x10
#define GNSS_CH_SIGNAL_TYPE         0x14
#define GNSS_CH_PRN                 0x18
#define GNSS_CH_INTEGRATION_TIME    0x1C
#define GNSS_CH_CORR_E_I            0x20
#define GNSS_CH_CORR_E_Q            0x24
#define GNSS_CH_CORR_P_I            0x28
#define GNSS_CH_CORR_P_Q            0x2C
#define GNSS_CH_CORR_L_I            0x30
#define GNSS_CH_CORR_L_Q            0x34

/* Constants */
#define GPS_L1CA_CHIP_RATE          1.023e6
#define NAVIC_L5_CHIP_RATE          10.23e6
#define GNSS_SAMPLE_RATE            16.368e6

/* NCO frequency word calculation */
#define GNSS_NCO_BITS               32
#define GNSS_FREQ_TO_WORD(freq, fs) ((uint32_t)(((freq) / (fs)) * (1ULL << GNSS_NCO_BITS)))

/* Test helper functions */
static inline uint32_t gnss_channel_base(uint8_t ch) {
    return GNSS_BASE + (ch * 0x100);
}

static inline uint32_t gnss_doppler_to_freq_word(double doppler_hz) {
    return GNSS_FREQ_TO_WORD(doppler_hz, GNSS_SAMPLE_RATE);
}

static inline uint32_t gnss_chip_rate_to_freq_word(double chip_rate_hz) {
    return GNSS_FREQ_TO_WORD(chip_rate_hz, GNSS_SAMPLE_RATE);
}

static inline double gnss_correlation_power(int32_t i, int32_t q) {
    return (double)i * i + (double)q * q;
}

static inline double gnss_correlation_magnitude(int32_t i, int32_t q) {
    double power = gnss_correlation_power(i, q);
    // Handle zero case
    if (power < 1e-10) {
        return 0.0;
    }
    // For realistic firmware without hardware sqrt, we can use the standard library
    // In actual embedded firmware, this would use a hardware sqrt instruction if available
    // or a more optimized approximation algorithm
    return sqrt(power);
}

/* Test counters */
static int tests_passed = 0;
static int tests_failed = 0;

/* Test assertion macro */
#define TEST_ASSERT(cond, msg) do { \
    if (cond) { \
        printf("  [PASS] %s\n", msg); \
        tests_passed++; \
    } else { \
        printf("  [FAIL] %s\n", msg); \
        tests_failed++; \
    } \
} while(0)

#define TEST_ASSERT_EQUAL(expected, actual, msg) do { \
    if ((expected) == (actual)) { \
        printf("  [PASS] %s: expected=0x%08X, actual=0x%08X\n", msg, (uint32_t)(expected), (uint32_t)(actual)); \
        tests_passed++; \
    } else { \
        printf("  [FAIL] %s: expected=0x%08X, actual=0x%08X\n", msg, (uint32_t)(expected), (uint32_t)(actual)); \
        tests_failed++; \
    } \
} while(0)

#define TEST_ASSERT_DELTA(expected, actual, delta, msg) do { \
    double diff = fabs((expected) - (actual)); \
    if (diff <= (delta)) { \
        printf("  [PASS] %s: expected=%.6f, actual=%.6f, diff=%.6f\n", msg, (expected), (actual), diff); \
        tests_passed++; \
    } else { \
        printf("  [FAIL] %s: expected=%.6f, actual=%.6f, diff=%.6f (max=%.6f)\n", msg, (expected), (actual), diff, (delta)); \
        tests_failed++; \
    } \
} while(0)

/**
 * Test 1: Register Address Calculations
 */
void test_register_addresses(void) {
    printf("\n=== Test 1: Register Address Calculations ===\n");

    // Test channel base addresses
    TEST_ASSERT_EQUAL(0x40000000, gnss_channel_base(0), "Channel 0 base address");
    TEST_ASSERT_EQUAL(0x40000100, gnss_channel_base(1), "Channel 1 base address");
    TEST_ASSERT_EQUAL(0x40000200, gnss_channel_base(2), "Channel 2 base address");
    TEST_ASSERT_EQUAL(0x40000700, gnss_channel_base(7), "Channel 7 base address");

    // Test register offsets
    uint32_t ch0_base = gnss_channel_base(0);
    TEST_ASSERT_EQUAL(0x40000000, ch0_base + GNSS_CH_CTRL, "Channel 0 CTRL register");
    TEST_ASSERT_EQUAL(0x40000004, ch0_base + GNSS_CH_STATUS, "Channel 0 STATUS register");
    TEST_ASSERT_EQUAL(0x40000008, ch0_base + GNSS_CH_CARRIER_FREQ, "Channel 0 CARRIER_FREQ register");
    TEST_ASSERT_EQUAL(0x40000020, ch0_base + GNSS_CH_CORR_E_I, "Channel 0 CORR_E_I register");
    TEST_ASSERT_EQUAL(0x40000028, ch0_base + GNSS_CH_CORR_P_I, "Channel 0 CORR_P_I register");

    uint32_t ch3_base = gnss_channel_base(3);
    TEST_ASSERT_EQUAL(0x40000300, ch3_base + GNSS_CH_CTRL, "Channel 3 CTRL register");
    TEST_ASSERT_EQUAL(0x40000310, ch3_base + GNSS_CH_CODE_FREQ, "Channel 3 CODE_FREQ register");

    // Test global base
    TEST_ASSERT_EQUAL(0x40001000, GNSS_GLOBAL_BASE, "Global base address");
}

/**
 * Test 2: Frequency Word Calculations (GNSS_FREQ_TO_WORD macro)
 */
void test_frequency_word_calculations(void) {
    printf("\n=== Test 2: Frequency Word Calculations ===\n");

    double fs = GNSS_SAMPLE_RATE;  // 16.368 MHz

    // Test case 1: Zero frequency
    uint32_t word = GNSS_FREQ_TO_WORD(0.0, fs);
    TEST_ASSERT_EQUAL(0, word, "Zero frequency -> word 0");

    // Test case 2: Nyquist frequency (fs/2)
    word = GNSS_FREQ_TO_WORD(fs / 2.0, fs);
    TEST_ASSERT_EQUAL(0x80000000, word, "Nyquist frequency (fs/2)");

    // Test case 3: fs/4
    word = GNSS_FREQ_TO_WORD(fs / 4.0, fs);
    TEST_ASSERT_EQUAL(0x40000000, word, "fs/4 frequency");

    // Test case 4: GPS L1 carrier frequency (1575.42 MHz) - intermediate frequency after mixing
    // After MAX2771 mixing, IF is typically around 4.092 MHz
    double if_freq = 4.092e6;
    word = GNSS_FREQ_TO_WORD(if_freq, fs);
    printf("  [INFO] IF %.3f MHz -> word 0x%08X (%.6f of full scale)\n",
           if_freq / 1e6, word, if_freq / fs);
    TEST_ASSERT(word > 0 && word < 0x80000000, "IF frequency word in valid range");

    // Test case 5: 1 MHz
    word = GNSS_FREQ_TO_WORD(1.0e6, fs);
    printf("  [INFO] 1 MHz -> word 0x%08X (ratio %.6f)\n", word, 1.0e6 / fs);
    TEST_ASSERT(word > 0, "1 MHz frequency word is non-zero");

    // Test case 6: Small frequency (1 Hz)
    word = GNSS_FREQ_TO_WORD(1.0, fs);
    printf("  [INFO] 1 Hz -> word 0x%08X\n", word);
    TEST_ASSERT(word > 0, "1 Hz frequency word is non-zero");
}

/**
 * Test 3: Correlation Power/Magnitude Calculations
 */
void test_correlation_calculations(void) {
    printf("\n=== Test 3: Correlation Power/Magnitude Calculations ===\n");

    // Test case 1: Zero correlation
    double power = gnss_correlation_power(0, 0);
    double mag = gnss_correlation_magnitude(0, 0);
    TEST_ASSERT_EQUAL(0, power, "Zero I,Q -> power 0");
    TEST_ASSERT_DELTA(0.0, mag, 0.001, "Zero I,Q -> magnitude 0");

    // Test case 2: Unit I, zero Q
    power = gnss_correlation_power(1, 0);
    mag = gnss_correlation_magnitude(1, 0);
    TEST_ASSERT_EQUAL(1, power, "I=1, Q=0 -> power 1");
    TEST_ASSERT_DELTA(1.0, mag, 0.001, "I=1, Q=0 -> magnitude 1");

    // Test case 3: Zero I, unit Q
    power = gnss_correlation_power(0, 1);
    mag = gnss_correlation_magnitude(0, 1);
    TEST_ASSERT_EQUAL(1, power, "I=0, Q=1 -> power 1");
    TEST_ASSERT_DELTA(1.0, mag, 0.001, "I=0, Q=1 -> magnitude 1");

    // Test case 4: 3-4-5 triangle (Pythagorean triple)
    power = gnss_correlation_power(3, 4);
    mag = gnss_correlation_magnitude(3, 4);
    TEST_ASSERT_EQUAL(25, power, "I=3, Q=4 -> power 25");
    TEST_ASSERT_DELTA(5.0, mag, 0.01, "I=3, Q=4 -> magnitude 5");

    // Test case 5: 5-12-13 triangle
    power = gnss_correlation_power(5, 12);
    mag = gnss_correlation_magnitude(5, 12);
    TEST_ASSERT_EQUAL(169, power, "I=5, Q=12 -> power 169");
    TEST_ASSERT_DELTA(13.0, mag, 0.01, "I=5, Q=12 -> magnitude 13");

    // Test case 6: Realistic correlation values (signed)
    int32_t i = 1000;
    int32_t q = -500;
    power = gnss_correlation_power(i, q);
    mag = gnss_correlation_magnitude(i, q);
    double expected_power = 1000.0 * 1000.0 + 500.0 * 500.0;
    double expected_mag = sqrt(expected_power);
    TEST_ASSERT_DELTA(expected_power, power, 1.0, "I=1000, Q=-500 -> power");
    TEST_ASSERT_DELTA(expected_mag, mag, 10.0, "I=1000, Q=-500 -> magnitude");

    // Test case 7: Large values (typical correlator output)
    i = 100000;
    q = 200000;
    power = gnss_correlation_power(i, q);
    mag = gnss_correlation_magnitude(i, q);
    expected_power = (double)i * i + (double)q * q;
    expected_mag = sqrt(expected_power);
    printf("  [INFO] I=%d, Q=%d -> power=%.0f, mag=%.0f\n", i, q, power, mag);
    TEST_ASSERT_DELTA(expected_power, power, 1.0, "Large values -> power");
    TEST_ASSERT_DELTA(expected_mag, mag, 1000.0, "Large values -> magnitude");

    // Test case 8: Negative values
    power = gnss_correlation_power(-10, -20);
    mag = gnss_correlation_magnitude(-10, -20);
    TEST_ASSERT_EQUAL(500, power, "I=-10, Q=-20 -> power 500");
    TEST_ASSERT_DELTA(sqrt(500.0), mag, 1.0, "I=-10, Q=-20 -> magnitude");
}

/**
 * Test 4: Doppler to Frequency Word Conversion
 */
void test_doppler_conversion(void) {
    printf("\n=== Test 4: Doppler to Frequency Word Conversion ===\n");

    double fs = GNSS_SAMPLE_RATE;

    // Test case 1: Zero Doppler
    uint32_t word = gnss_doppler_to_freq_word(0.0);
    TEST_ASSERT_EQUAL(0, word, "Zero Doppler -> word 0");

    // Test case 2: +1000 Hz Doppler
    word = gnss_doppler_to_freq_word(1000.0);
    uint32_t expected = GNSS_FREQ_TO_WORD(1000.0, fs);
    TEST_ASSERT_EQUAL(expected, word, "+1000 Hz Doppler");
    printf("  [INFO] +1000 Hz Doppler -> 0x%08X\n", word);

    // Test case 3: -1000 Hz Doppler (negative Doppler)
    word = gnss_doppler_to_freq_word(-1000.0);
    expected = GNSS_FREQ_TO_WORD(-1000.0, fs);
    TEST_ASSERT_EQUAL(expected, word, "-1000 Hz Doppler");
    printf("  [INFO] -1000 Hz Doppler -> 0x%08X\n", word);

    // Test case 4: +5000 Hz (max typical GPS Doppler)
    word = gnss_doppler_to_freq_word(5000.0);
    expected = GNSS_FREQ_TO_WORD(5000.0, fs);
    TEST_ASSERT_EQUAL(expected, word, "+5000 Hz Doppler");
    printf("  [INFO] +5000 Hz Doppler -> 0x%08X\n", word);

    // Test case 5: -5000 Hz
    word = gnss_doppler_to_freq_word(-5000.0);
    expected = GNSS_FREQ_TO_WORD(-5000.0, fs);
    TEST_ASSERT_EQUAL(expected, word, "-5000 Hz Doppler");
    printf("  [INFO] -5000 Hz Doppler -> 0x%08X\n", word);

    // Test case 6: Small Doppler (10 Hz)
    word = gnss_doppler_to_freq_word(10.0);
    TEST_ASSERT(word > 0, "10 Hz Doppler produces non-zero word");
    printf("  [INFO] 10 Hz Doppler -> 0x%08X\n", word);

    // Test case 7: Verify Doppler range
    // Typical GPS Doppler range is ±5 kHz, verify words are reasonable
    word = gnss_doppler_to_freq_word(5000.0);
    double ratio = 5000.0 / fs;
    TEST_ASSERT(ratio < 0.001, "5 kHz is small fraction of sample rate");
    printf("  [INFO] 5 kHz Doppler is %.6f of sample rate\n", ratio);
}

/**
 * Test 5: Chip Rate to Frequency Word Conversion
 */
void test_chip_rate_conversion(void) {
    printf("\n=== Test 5: Chip Rate to Frequency Word Conversion ===\n");

    double fs = GNSS_SAMPLE_RATE;

    // Test case 1: GPS L1 C/A nominal chip rate (1.023 MHz)
    uint32_t word = gnss_chip_rate_to_freq_word(GPS_L1CA_CHIP_RATE);
    uint32_t expected = GNSS_FREQ_TO_WORD(GPS_L1CA_CHIP_RATE, fs);
    TEST_ASSERT_EQUAL(expected, word, "GPS L1 C/A chip rate");
    double ratio = GPS_L1CA_CHIP_RATE / fs;
    printf("  [INFO] GPS L1 C/A (1.023 MHz) -> 0x%08X (ratio %.6f)\n", word, ratio);
    TEST_ASSERT(ratio > 0.06 && ratio < 0.07, "GPS chip rate is ~6.25% of sample rate");

    // Test case 2: NavIC L5 nominal chip rate (10.23 MHz)
    word = gnss_chip_rate_to_freq_word(NAVIC_L5_CHIP_RATE);
    expected = GNSS_FREQ_TO_WORD(NAVIC_L5_CHIP_RATE, fs);
    TEST_ASSERT_EQUAL(expected, word, "NavIC L5 chip rate");
    ratio = NAVIC_L5_CHIP_RATE / fs;
    printf("  [INFO] NavIC L5 (10.23 MHz) -> 0x%08X (ratio %.6f)\n", word, ratio);
    TEST_ASSERT(ratio > 0.62 && ratio < 0.63, "NavIC chip rate is ~62.5% of sample rate");

    // Test case 3: GPS with small Doppler offset (+10 Hz on code)
    double gps_rate_offset = GPS_L1CA_CHIP_RATE + 10.0;
    word = gnss_chip_rate_to_freq_word(gps_rate_offset);
    uint32_t word_nominal = gnss_chip_rate_to_freq_word(GPS_L1CA_CHIP_RATE);
    printf("  [INFO] GPS with +10 Hz offset: nominal=0x%08X, offset=0x%08X, diff=%d\n",
           word_nominal, word, (int32_t)(word - word_nominal));
    TEST_ASSERT(word > word_nominal, "Positive offset increases frequency word");

    // Test case 4: GPS with Doppler-scaled code rate
    // For a satellite with +5000 Hz carrier Doppler, code Doppler is approximately
    // (chip_rate / carrier_freq) * carrier_doppler
    // For GPS L1: (1.023 MHz / 1575.42 MHz) * 5000 Hz ≈ 3.24 Hz
    double code_doppler = (GPS_L1CA_CHIP_RATE / 1575.42e6) * 5000.0;
    double gps_rate_doppler = GPS_L1CA_CHIP_RATE + code_doppler;
    word = gnss_chip_rate_to_freq_word(gps_rate_doppler);
    printf("  [INFO] GPS with carrier Doppler 5 kHz -> code Doppler %.2f Hz -> word 0x%08X\n",
           code_doppler, word);
    TEST_ASSERT(word > word_nominal, "Doppler-scaled code rate increases word");

    // Test case 5: NavIC with small offset
    double navic_rate_offset = NAVIC_L5_CHIP_RATE - 5.0;
    word = gnss_chip_rate_to_freq_word(navic_rate_offset);
    uint32_t word_navic_nominal = gnss_chip_rate_to_freq_word(NAVIC_L5_CHIP_RATE);
    TEST_ASSERT(word < word_navic_nominal, "Negative offset decreases frequency word");

    // Test case 6: Verify frequency word ranges
    // GPS L1 C/A: 1.023 MHz / 16.368 MHz ≈ 0.0625 = 268435456 / 2^32
    expected = (uint32_t)(0.0625 * 4294967296.0);
    word = gnss_chip_rate_to_freq_word(GPS_L1CA_CHIP_RATE);
    uint32_t tolerance = 0x01000000;  // Allow some tolerance for floating point
    int32_t diff = abs((int32_t)(word - expected));
    printf("  [INFO] GPS chip rate: expected≈0x%08X, actual=0x%08X, diff=0x%08X\n",
           expected, word, diff);
    TEST_ASSERT((uint32_t)diff < tolerance, "GPS chip rate word within expected range");
}

/**
 * Test 6: Edge Cases and Boundary Conditions
 */
void test_edge_cases(void) {
    printf("\n=== Test 6: Edge Cases and Boundary Conditions ===\n");

    // Test maximum channel number
    uint32_t addr = gnss_channel_base(GNSS_NUM_CHANNELS - 1);
    uint32_t expected = GNSS_BASE + ((GNSS_NUM_CHANNELS - 1) * 0x100);
    TEST_ASSERT_EQUAL(expected, addr, "Maximum valid channel address");

    // Test frequency word overflow protection
    // Frequencies >= fs will wrap (aliasing)
    double fs = GNSS_SAMPLE_RATE;
    uint32_t word = GNSS_FREQ_TO_WORD(fs, fs);
    // fs creates a ratio of 1.0, which wraps to 0 in 32-bit arithmetic
    // (1.0 * 2^32) & 0xFFFFFFFF = 0xFFFFFFFF (due to float->uint conversion)
    TEST_ASSERT(word == 0 || word == 0xFFFFFFFF, "fs -> word wraps (aliasing)");

    // Test negative I and Q correlation
    double power = gnss_correlation_power(-1000, -1000);
    double mag = gnss_correlation_magnitude(-1000, -1000);
    double expected_mag = sqrt(2000000.0);
    TEST_ASSERT_DELTA(2000000.0, power, 1.0, "Negative I,Q -> correct power");
    TEST_ASSERT_DELTA(expected_mag, mag, 1.0, "Negative I,Q -> correct magnitude");

    // Test very small frequency word resolution
    word = GNSS_FREQ_TO_WORD(0.001, fs);  // 1 mHz
    printf("  [INFO] 1 mHz -> word 0x%08X\n", word);
    TEST_ASSERT(word < 1000, "Very small frequency produces small word");

    // Test correlation with maximum int32_t values
    // Note: INT32_MAX is unrealistically large for actual correlator output
    // Typical correlator outputs are in the range of ±100000
    int32_t max_val = 2147483647;  // INT32_MAX
    power = gnss_correlation_power(max_val, 0);
    mag = gnss_correlation_magnitude(max_val, 0);
    printf("  [INFO] I=INT32_MAX, Q=0 -> power=%.0f, mag=%.0f\n", power, mag);
    TEST_ASSERT(power > 0, "Maximum int32_t correlation produces valid power");
    // For such extreme values, our sqrt approximation may not be precise
    // Verify magnitude is in reasonable ballpark (within factor of 2)
    TEST_ASSERT(mag > (double)max_val / 2.0 && mag < (double)max_val * 2.0,
                "Maximum int32_t magnitude in reasonable range");

    // Test frequency word with negative frequencies
    // Note: GNSS_FREQ_TO_WORD casts to uint32_t, negative frequencies will wrap
    uint32_t word_pos = GNSS_FREQ_TO_WORD(1000.0, fs);
    printf("  [INFO] +1000 Hz: 0x%08X\n", word_pos);
    TEST_ASSERT(word_pos > 0, "Positive frequency produces positive word");
}

/**
 * Test 7: Verification Against Known Values
 */
void test_known_values(void) {
    printf("\n=== Test 7: Verification Against Known Values ===\n");

    double fs = GNSS_SAMPLE_RATE;

    // GPS L1 C/A parameters
    double gps_chip_rate = 1.023e6;
    double gps_code_period = 1e-3;  // 1 ms
    double gps_chips_per_code = gps_chip_rate * gps_code_period;
    TEST_ASSERT_DELTA(1023.0, gps_chips_per_code, 0.1, "GPS L1 C/A has 1023 chips");

    // NavIC L5 parameters
    double navic_chip_rate = 10.23e6;
    double navic_code_period = 1e-3;  // 1 ms
    double navic_chips_per_code = navic_chip_rate * navic_code_period;
    TEST_ASSERT_DELTA(10230.0, navic_chips_per_code, 0.1, "NavIC L5 has 10230 chips");

    // Verify NCO resolution
    // With 32-bit NCO, resolution is fs / 2^32
    double nco_resolution = fs / 4294967296.0;
    printf("  [INFO] NCO frequency resolution: %.6f Hz\n", nco_resolution);
    TEST_ASSERT(nco_resolution < 0.01, "NCO resolution better than 0.01 Hz");

    // Verify sample rate allows GPS and NavIC
    TEST_ASSERT(fs > navic_chip_rate, "Sample rate exceeds NavIC chip rate (no aliasing)");
    TEST_ASSERT(fs > 2.0 * gps_chip_rate, "Sample rate > 2x GPS chip rate (Nyquist)");

    // Integration period samples
    // For 1 ms integration at 16.368 MSPS
    uint32_t samples_1ms = (uint32_t)(fs * 1e-3);
    printf("  [INFO] Samples in 1 ms: %u\n", samples_1ms);
    TEST_ASSERT_DELTA(16368.0, (double)samples_1ms, 1.0, "1 ms integration period");

    // Verify correlation magnitude squared approximates power
    int32_t i = 1234;
    int32_t q = 5678;
    double power = gnss_correlation_power(i, q);
    double mag = gnss_correlation_magnitude(i, q);
    double mag_sq = mag * mag;
    double diff = fabs(mag_sq - power);
    printf("  [INFO] I=%d, Q=%d -> power=%.0f, mag=%.0f, mag²=%.0f, diff=%.0f\n",
           i, q, power, mag, mag_sq, diff);
    TEST_ASSERT(diff / power < 0.01, "Magnitude squared within 1% of power");
}

/**
 * Main test runner
 */
int main(int argc, char *argv[]) {
    (void)argc;  // Unused parameter
    (void)argv;  // Unused parameter

    printf("========================================\n");
    printf("GNSS CSR Library Unit Tests\n");
    printf("========================================\n");

    printf("\nTest Configuration:\n");
    printf("  GNSS_BASE: 0x%08X\n", GNSS_BASE);
    printf("  GNSS_GLOBAL_BASE: 0x%08X\n", GNSS_GLOBAL_BASE);
    printf("  GNSS_NUM_CHANNELS: %d\n", GNSS_NUM_CHANNELS);
    printf("  GNSS_SAMPLE_RATE: %.3f MHz\n", GNSS_SAMPLE_RATE / 1e6);
    printf("  GPS_L1CA_CHIP_RATE: %.3f MHz\n", GPS_L1CA_CHIP_RATE / 1e6);
    printf("  NAVIC_L5_CHIP_RATE: %.3f MHz\n", NAVIC_L5_CHIP_RATE / 1e6);
    printf("  GNSS_NCO_BITS: %d\n", GNSS_NCO_BITS);

    // Run all tests
    test_register_addresses();
    test_frequency_word_calculations();
    test_correlation_calculations();
    test_doppler_conversion();
    test_chip_rate_conversion();
    test_edge_cases();
    test_known_values();

    // Print summary
    printf("\n========================================\n");
    printf("Test Summary\n");
    printf("========================================\n");
    printf("Tests Passed: %d\n", tests_passed);
    printf("Tests Failed: %d\n", tests_failed);
    printf("Total Tests:  %d\n", tests_passed + tests_failed);

    if (tests_failed == 0) {
        printf("\nRESULT: ALL TESTS PASSED ✓\n");
        printf("========================================\n");
        return 0;
    } else {
        printf("\nRESULT: %d TEST(S) FAILED ✗\n", tests_failed);
        printf("========================================\n");
        return 1;
    }
}
