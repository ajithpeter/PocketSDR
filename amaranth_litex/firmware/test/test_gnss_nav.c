/**
 * Unit Tests for GNSS Navigation Message Decoders
 *
 * Tests GPS and NavIC navigation message decoding including:
 * - Preamble detection
 * - Word parity checking
 * - Subframe decoding
 * - Ephemeris extraction
 * - Bit synchronization
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

// Include the navigation decoder header
#include "../include/gnss_nav.h"

/* Test framework macros */
#define TEST_PASS 0
#define TEST_FAIL 1

static int test_count = 0;
static int test_passed = 0;
static int test_failed = 0;

#define TEST_START(name) \
    do { \
        test_count++; \
        printf("\n[TEST %d] %s\n", test_count, name); \
    } while(0)

#define TEST_ASSERT(condition, message) \
    do { \
        if (condition) { \
            printf("  ✓ PASS: %s\n", message); \
            test_passed++; \
        } else { \
            printf("  ✗ FAIL: %s\n", message); \
            test_failed++; \
        } \
    } while(0)

#define TEST_ASSERT_EQ(expected, actual, message) \
    do { \
        if ((expected) == (actual)) { \
            printf("  ✓ PASS: %s (expected=%d, actual=%d)\n", message, (int)(expected), (int)(actual)); \
            test_passed++; \
        } else { \
            printf("  ✗ FAIL: %s (expected=%d, actual=%d)\n", message, (int)(expected), (int)(actual)); \
            test_failed++; \
        } \
    } while(0)

#define TEST_ASSERT_NEAR(expected, actual, tolerance, message) \
    do { \
        double diff = fabs((double)(expected) - (double)(actual)); \
        if (diff <= (tolerance)) { \
            printf("  ✓ PASS: %s (expected=%.6f, actual=%.6f, diff=%.6e)\n", \
                   message, (double)(expected), (double)(actual), diff); \
            test_passed++; \
        } else { \
            printf("  ✗ FAIL: %s (expected=%.6f, actual=%.6f, diff=%.6e, tolerance=%.6e)\n", \
                   message, (double)(expected), (double)(actual), diff, (double)(tolerance)); \
            test_failed++; \
        } \
    } while(0)

/* ========================================================================
 * GPS Navigation Message Test Vectors
 * ======================================================================== */

/**
 * GPS Subframe 1 - Clock and Health Data
 * TLM: 0x8B (preamble)
 * HOW: Contains TOW and subframe ID
 * Clock parameters: toc, af0, af1, af2
 * Health and accuracy
 */
static const uint32_t gps_subframe1_sample[] = {
    // Word 1: TLM (with preamble 0x8B in MSBs)
    0x22C00000,  // TLM word with preamble
    // Word 2: HOW (with subframe ID = 1)
    0x00001684,  // TOW count, subframe ID in bits
    // Word 3: Week number, SV accuracy, SV health, IODC
    0x3FFC1234,
    // Word 4: Reserved
    0x00000000,
    // Word 5: Reserved
    0x00000000,
    // Word 6: Reserved
    0x00000000,
    // Word 7: toc (reference time for clock)
    0x00FF0000,
    // Word 8: af2, af1 (clock drift rate, drift)
    0x00008000,
    // Word 9: af0 (clock bias)
    0x00100000,
    // Word 10: Reserved
    0x00000000
};

/**
 * GPS Subframe 2 - Ephemeris Part 1
 * Contains: IODE, crs, delta_n, M0, cuc, e, cus, sqrt(A), toe
 */
static const uint32_t gps_subframe2_sample[] = {
    // Word 1: TLM
    0x22C00000,
    // Word 2: HOW with subframe ID = 2
    0x00002684,
    // Word 3: IODE, crs
    0x01001000,
    // Word 4: delta_n, M0 (MSBs)
    0x00200000,
    // Word 5: M0 (LSBs)
    0x12345678,
    // Word 6: cuc, e (MSBs)
    0x00800000,
    // Word 7: e (LSBs)
    0x01234567,
    // Word 8: cus, sqrt(A) (MSBs)
    0x00400000,
    // Word 9: sqrt(A) (LSBs)
    0x5153A000,  // ~26560 km semi-major axis
    // Word 10: toe
    0x00FF0000
};

/**
 * GPS Subframe 3 - Ephemeris Part 2
 * Contains: cic, OMEGA0, cis, i0, crc, omega, OMEGA_DOT
 */
static const uint32_t gps_subframe3_sample[] = {
    // Word 1: TLM
    0x22C00000,
    // Word 2: HOW with subframe ID = 3
    0x00003684,
    // Word 3: cic, OMEGA0 (MSBs)
    0x00100000,
    // Word 4: OMEGA0 (LSBs)
    0x87654321,
    // Word 5: cis, i0 (MSBs)
    0x00080000,
    // Word 6: i0 (LSBs)
    0xABCDEF00,
    // Word 7: crc, omega (MSBs)
    0x00200000,
    // Word 8: omega (LSBs)
    0x11223344,
    // Word 9: OMEGA_DOT
    0xFFFFFFC0,
    // Word 10: IODE, IDOT
    0x01000100
};

/**
 * GPS Preamble patterns for testing (commented - defined in header)
 */
// static const uint8_t gps_preamble_normal = 0x8B;    // 10001011
// static const uint8_t gps_preamble_inverted = 0x74;  // 01110100 (inverted)

/**
 * NavIC Sync pattern (commented - defined in header)
 */
// static const uint16_t navic_sync_pattern = 0xEB90;

/* ========================================================================
 * Test 1: GPS Preamble Detection
 * ======================================================================== */

void test_gps_preamble_detection(void) {
    TEST_START("GPS Preamble Detection (0x8B pattern)");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Test 1.1: Detect normal preamble
    uint8_t test_pattern1[] = {1, 0, 0, 0, 1, 0, 1, 1};  // 0x8B
    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, test_pattern1[i]);
    }
    TEST_ASSERT(nav.frame_sync, "Normal preamble 0x8B detected");

    // Test 1.2: Detect inverted preamble
    gps_nav_init(&nav, 2);
    uint8_t test_pattern2[] = {0, 1, 1, 1, 0, 1, 0, 0};  // 0x74 (inverted)
    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, test_pattern2[i]);
    }
    TEST_ASSERT(nav.frame_sync, "Inverted preamble 0x74 detected");

    // Test 1.3: Reject false preamble
    gps_nav_init(&nav, 3);
    uint8_t test_pattern3[] = {1, 1, 1, 1, 0, 0, 0, 0};  // 0xF0 (invalid)
    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, test_pattern3[i]);
    }
    TEST_ASSERT(!nav.frame_sync, "Invalid pattern rejected");

    // Test 1.4: Preamble at different positions
    gps_nav_init(&nav, 4);
    uint8_t test_pattern4[] = {0, 0, 1, 0, 0, 0, 1, 0, 1, 1};  // preamble after 2 bits
    for (int i = 0; i < 10; i++) {
        gps_nav_process_bit(&nav, test_pattern4[i]);
    }
    TEST_ASSERT(nav.frame_sync, "Preamble detected at offset position");

    printf("  → GPS preamble = 0x%02X (binary: 10001011)\n", GPS_PREAMBLE);
}

/* ========================================================================
 * Test 2: GPS Word Parity Checking
 * ======================================================================== */

void test_gps_word_parity(void) {
    TEST_START("GPS Word Parity Checking");

    // GPS uses Hamming code for error detection/correction
    // 30-bit word = 24 data bits + 6 parity bits

    // Test 2.1: Valid word with correct parity
    uint32_t valid_word = 0x22C00000;  // TLM word with preamble
    uint32_t prev_word = 0x00000000;
    bool parity_ok = gps_check_parity(valid_word, prev_word);
    TEST_ASSERT(parity_ok, "Valid word parity check passes");

    // Test 2.2: Extract data bits from word
    uint32_t data = gps_extract_data(valid_word);
    TEST_ASSERT((data & 0xFFFFFF) == (data), "Extracted data is 24 bits");
    printf("  → Original word: 0x%08X, Extracted data: 0x%06X\n", valid_word, data);

    // Test 2.3: Verify data extraction removes parity
    uint32_t test_word = 0x3FFFFFFF;  // All bits set
    uint32_t extracted = gps_extract_data(test_word);
    TEST_ASSERT_EQ(0xFFFFFF, extracted, "Parity bits removed correctly");

    // Test 2.4: Multiple sequential words
    for (int i = 0; i < 10; i++) {
        uint32_t word = gps_subframe1_sample[i];
        uint32_t prev = (i > 0) ? gps_subframe1_sample[i-1] : 0;
        bool ok = gps_check_parity(word, prev);
        TEST_ASSERT(ok, "Subframe word parity valid");
    }
}

/* ========================================================================
 * Test 3: GPS Subframe Decoding
 * ======================================================================== */

void test_gps_subframe_decoding(void) {
    TEST_START("GPS Subframe Decoding with Known Data");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Test 3.1: Decode Subframe 1 (Clock data)
    memcpy(nav.subframe, gps_subframe1_sample, sizeof(gps_subframe1_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    TEST_ASSERT_EQ(1, nav.subframe_id, "Subframe ID is 1");
    TEST_ASSERT(nav.eph_received[0], "Subframe 1 marked as received");
    TEST_ASSERT(nav.eph.week > 0, "GPS week number extracted");
    printf("  → GPS Week: %u, Health: 0x%02X, URA: %u\n",
           nav.eph.week, nav.eph.health, nav.eph.ura);

    // Test 3.2: Decode Subframe 2 (Ephemeris part 1)
    memcpy(nav.subframe, gps_subframe2_sample, sizeof(gps_subframe2_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    TEST_ASSERT_EQ(2, nav.subframe_id, "Subframe ID is 2");
    TEST_ASSERT(nav.eph_received[1], "Subframe 2 marked as received");
    TEST_ASSERT(nav.eph.iode > 0, "IODE extracted");
    TEST_ASSERT(fabs(nav.eph.sqrtA) > 0, "sqrt(A) extracted");
    printf("  → IODE: %u, sqrt(A): %.3f m^0.5, e: %.6e\n",
           nav.eph.iode, nav.eph.sqrtA, nav.eph.ecc);

    // Test 3.3: Decode Subframe 3 (Ephemeris part 2)
    memcpy(nav.subframe, gps_subframe3_sample, sizeof(gps_subframe3_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    TEST_ASSERT_EQ(3, nav.subframe_id, "Subframe ID is 3");
    TEST_ASSERT(nav.eph_received[2], "Subframe 3 marked as received");
    printf("  → cic: %.6e, cis: %.6e, crc: %.3f m\n",
           nav.eph.cic, nav.eph.cis, nav.eph.crc);

    // Test 3.4: Complete ephemeris validation
    TEST_ASSERT(nav.eph.valid, "Ephemeris marked as valid after all subframes");
}

/* ========================================================================
 * Test 4: NavIC Sync Pattern Detection
 * ======================================================================== */

void test_navic_sync_detection(void) {
    TEST_START("NavIC Sync Pattern Detection (0xEB90)");

    navic_nav_decoder_t nav;
    navic_nav_init(&nav, 1);

    // Test 4.1: Detect NavIC sync pattern
    // 0xEB90 = 1110 1011 1001 0000
    uint8_t sync_bits[] = {1,1,1,0, 1,0,1,1, 1,0,0,1, 0,0,0,0};

    for (int i = 0; i < 16; i++) {
        navic_nav_process_bit(&nav, sync_bits[i]);
    }
    TEST_ASSERT(nav.sync, "NavIC sync pattern 0xEB90 detected");

    // Test 4.2: Reject false sync
    navic_nav_init(&nav, 2);
    uint8_t false_sync[] = {1,1,1,1, 0,0,0,0, 1,1,1,1, 0,0,0,0};  // 0xF0F0
    for (int i = 0; i < 16; i++) {
        navic_nav_process_bit(&nav, false_sync[i]);
    }
    TEST_ASSERT(!nav.sync, "Invalid NavIC pattern rejected");

    // Test 4.3: Partial pattern
    navic_nav_init(&nav, 3);
    uint8_t partial_sync[] = {1,1,1,0, 1,0,1,1};  // Only 8 bits of 0xEB90
    for (int i = 0; i < 8; i++) {
        navic_nav_process_bit(&nav, partial_sync[i]);
    }
    TEST_ASSERT(!nav.sync, "Partial sync pattern not detected prematurely");

    printf("  → NavIC sync pattern = 0x%04X (binary: 1110101110010000)\n", NAVIC_SYNC_PATTERN);
}

/* ========================================================================
 * Test 5: Ephemeris Parameter Extraction
 * ======================================================================== */

void test_ephemeris_extraction(void) {
    TEST_START("Ephemeris Parameter Extraction");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Decode all three subframes to get complete ephemeris
    memcpy(nav.subframe, gps_subframe1_sample, sizeof(gps_subframe1_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    memcpy(nav.subframe, gps_subframe2_sample, sizeof(gps_subframe2_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    memcpy(nav.subframe, gps_subframe3_sample, sizeof(gps_subframe3_sample));
    nav.word_count = 10;
    gps_decode_subframe(&nav);

    // Test 5.1: Clock parameters
    TEST_ASSERT(nav.eph.toc >= 0, "Clock reference time (toc) valid");
    printf("  → Clock: toc=%.1f s, af0=%.6e s, af1=%.6e s/s, af2=%.6e s/s^2\n",
           nav.eph.toc, nav.eph.af0, nav.eph.af1, nav.eph.af2);

    // Test 5.2: Orbital parameters
    TEST_ASSERT(nav.eph.sqrtA > 5000, "Semi-major axis reasonable (sqrt(A) > 5000)");
    TEST_ASSERT(nav.eph.ecc >= 0 && nav.eph.ecc < 0.1, "Eccentricity in valid range");
    printf("  → Orbit: sqrt(A)=%.3f m^0.5, e=%.6e, M0=%.6e rad\n",
           nav.eph.sqrtA, nav.eph.ecc, nav.eph.m0);

    // Test 5.3: Correction terms
    printf("  → Corrections: crs=%.3f m, crc=%.3f m, cuc=%.6e rad\n",
           nav.eph.crs, nav.eph.crc, nav.eph.cuc);
    TEST_ASSERT(fabs(nav.eph.crs) < 1000, "crs in reasonable range");
    TEST_ASSERT(fabs(nav.eph.crc) < 1000, "crc in reasonable range");

    // Test 5.4: Get ephemeris via API
    gps_ephemeris_t eph;
    bool got_eph = gps_nav_get_ephemeris(&nav, &eph);
    TEST_ASSERT(got_eph, "Ephemeris retrieval successful");
    TEST_ASSERT(eph.valid, "Retrieved ephemeris is valid");
    TEST_ASSERT_EQ(nav.eph.week, eph.week, "Week number matches");
    TEST_ASSERT_NEAR(nav.eph.sqrtA, eph.sqrtA, 1e-6, "sqrt(A) matches");
}

/* ========================================================================
 * Test 6: Bit Synchronization
 * ======================================================================== */

void test_bit_synchronization(void) {
    TEST_START("Bit Synchronization");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Test 6.1: Process bit stream to achieve sync
    // Feed preamble pattern to establish synchronization
    uint8_t preamble[] = {1, 0, 0, 0, 1, 0, 1, 1};  // 0x8B

    TEST_ASSERT(!nav.frame_sync, "Initially not synchronized");

    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, preamble[i]);
    }

    TEST_ASSERT(nav.frame_sync, "Frame sync achieved after preamble");
    TEST_ASSERT_EQ(0, nav.word_count, "Word count reset after sync");

    // Test 6.2: Maintain sync through word collection
    // Feed 30-bit word
    for (int i = 0; i < 30; i++) {
        gps_nav_process_bit(&nav, (i % 2));  // Alternating pattern
    }

    TEST_ASSERT_EQ(1, nav.word_count, "First word collected");

    // Test 6.3: Collect full subframe (10 words = 300 bits)
    gps_nav_init(&nav, 2);

    // Feed preamble first
    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, preamble[i]);
    }

    // Feed 300 bits (10 words)
    for (int word = 0; word < 10; word++) {
        for (int bit = 0; bit < 30; bit++) {
            gps_nav_process_bit(&nav, 1);  // All ones for simplicity
        }
    }

    // Subframe should be decoded
    printf("  → Collected %u words before subframe decode\n", nav.word_count);

    // Test 6.4: Bit buffer management
    gps_nav_init(&nav, 3);
    TEST_ASSERT_EQ(0, nav.bit_count, "Bit count initialized to 0");
    TEST_ASSERT_EQ(0, nav.bit_buffer, "Bit buffer initialized to 0");

    // Add individual bits and check buffer
    gps_nav_process_bit(&nav, 1);
    TEST_ASSERT(nav.bit_buffer & 0x01, "Bit added to buffer");

    gps_nav_process_bit(&nav, 0);
    TEST_ASSERT_EQ(0x02, nav.bit_buffer & 0x03, "Second bit added (10 binary)");

    printf("  → Bit buffer after 2 bits: 0x%08X\n", nav.bit_buffer);

    // Test 6.5: Word boundary detection
    gps_nav_init(&nav, 4);

    // Sync first
    for (int i = 0; i < 8; i++) {
        gps_nav_process_bit(&nav, preamble[i]);
    }

    // Feed exactly 30 bits
    for (int i = 0; i < 30; i++) {
        gps_nav_process_bit(&nav, 1);
    }

    TEST_ASSERT_EQ(0, nav.bit_count, "Bit count reset after 30-bit word");
    TEST_ASSERT_EQ(1, nav.word_count, "Word count incremented at boundary");
}

/* ========================================================================
 * Test 7: End-to-End Navigation Message Processing
 * ======================================================================== */

void test_e2e_navigation_processing(void) {
    TEST_START("End-to-End Navigation Message Processing");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 15);  // PRN 15

    // Helper function to send a word bit-by-bit
    auto void send_word(uint32_t word) {
        for (int i = 29; i >= 0; i--) {  // MSB first
            int bit = (word >> i) & 0x01;
            gps_nav_process_bit(&nav, bit);
        }
    }

    // Test 7.1: Send complete subframe 1
    printf("  → Sending Subframe 1...\n");
    for (int i = 0; i < 10; i++) {
        send_word(gps_subframe1_sample[i]);
    }
    TEST_ASSERT(nav.eph_received[0], "Subframe 1 processed");

    // Test 7.2: Send complete subframe 2
    printf("  → Sending Subframe 2...\n");
    for (int i = 0; i < 10; i++) {
        send_word(gps_subframe2_sample[i]);
    }
    TEST_ASSERT(nav.eph_received[1], "Subframe 2 processed");

    // Test 7.3: Send complete subframe 3
    printf("  → Sending Subframe 3...\n");
    for (int i = 0; i < 10; i++) {
        send_word(gps_subframe3_sample[i]);
    }
    TEST_ASSERT(nav.eph_received[2], "Subframe 3 processed");

    // Test 7.4: Verify complete ephemeris
    TEST_ASSERT(nav.eph.valid, "Complete ephemeris available");

    gps_ephemeris_t eph;
    bool success = gps_nav_get_ephemeris(&nav, &eph);
    TEST_ASSERT(success, "Ephemeris retrieved successfully");

    printf("  → Final Ephemeris Summary:\n");
    printf("     PRN: %u, Week: %u, Health: 0x%02X\n", nav.prn, eph.week, eph.health);
    printf("     sqrt(A): %.3f m^0.5 (semi-major axis: %.3f km)\n",
           eph.sqrtA, (eph.sqrtA * eph.sqrtA) / 1000.0);
    printf("     Eccentricity: %.6e\n", eph.ecc);
    printf("     Clock bias (af0): %.6e s\n", eph.af0);
}

/* ========================================================================
 * Test 8: Error Handling and Edge Cases
 * ======================================================================== */

void test_error_handling(void) {
    TEST_START("Error Handling and Edge Cases");

    gps_nav_decoder_t nav;
    gps_nav_init(&nav, 1);

    // Test 8.1: Process bit with value 0 (no data)
    bool result = gps_nav_process_bit(&nav, 0);
    TEST_ASSERT(!result, "Returns false for zero bit (no data)");

    // Test 8.2: Get ephemeris before it's valid
    gps_ephemeris_t eph;
    bool got_eph = gps_nav_get_ephemeris(&nav, &eph);
    TEST_ASSERT(!got_eph, "Returns false when ephemeris not ready");

    // Test 8.3: Initialize decoder multiple times
    gps_nav_init(&nav, 1);
    TEST_ASSERT_EQ(1, nav.prn, "PRN set correctly");
    gps_nav_init(&nav, 10);
    TEST_ASSERT_EQ(10, nav.prn, "PRN updated on re-init");
    TEST_ASSERT(!nav.frame_sync, "Sync cleared on re-init");

    // Test 8.4: NavIC decoder initialization
    navic_nav_decoder_t navic;
    navic_nav_init(&navic, 5);
    TEST_ASSERT_EQ(5, navic.prn, "NavIC PRN set correctly");
    TEST_ASSERT(!navic.sync, "NavIC sync initially false");

    // Test 8.5: NavIC ephemeris retrieval without data
    navic_ephemeris_t navic_eph;
    bool got_navic = navic_nav_get_ephemeris(&navic, &navic_eph);
    TEST_ASSERT(!got_navic, "Returns false for invalid NavIC ephemeris");
}

/* ========================================================================
 * Main Test Runner
 * ======================================================================== */

int main(int argc, char *argv[]) {
    (void)argc;  // Unused
    (void)argv;  // Unused
    printf("╔════════════════════════════════════════════════════════════════╗\n");
    printf("║      GNSS Navigation Decoder Unit Test Suite                  ║\n");
    printf("║      PocketSDR Firmware - Test Version 1.0                    ║\n");
    printf("╚════════════════════════════════════════════════════════════════╝\n");

    printf("\nGPS Navigation Message Format:\n");
    printf("  - Frame: 1500 bits (30 seconds at 50 bps)\n");
    printf("  - Subframe: 300 bits (6 seconds, 10 words)\n");
    printf("  - Word: 30 bits (24 data + 6 parity)\n");
    printf("  - Preamble: 0x8B (10001011)\n");
    printf("\nNavIC Navigation Message Format:\n");
    printf("  - Sync Pattern: 0xEB90 (1110101110010000)\n");
    printf("  - Data Rate: 50 bps\n");

    // Run all tests
    test_gps_preamble_detection();
    test_gps_word_parity();
    test_gps_subframe_decoding();
    test_navic_sync_detection();
    test_ephemeris_extraction();
    test_bit_synchronization();
    test_e2e_navigation_processing();
    test_error_handling();

    // Print summary
    printf("\n╔════════════════════════════════════════════════════════════════╗\n");
    printf("║                     TEST SUMMARY                               ║\n");
    printf("╠════════════════════════════════════════════════════════════════╣\n");
    printf("║  Total Tests Run:    %3d                                       ║\n", test_count);
    printf("║  Assertions Passed:  %3d                                       ║\n", test_passed);
    printf("║  Assertions Failed:  %3d                                       ║\n", test_failed);
    printf("║  Success Rate:       %3.1f%%                                     ║\n",
           (test_passed * 100.0) / (test_passed + test_failed));
    printf("╚════════════════════════════════════════════════════════════════╝\n");

    if (test_failed == 0) {
        printf("\n✓ All tests PASSED! 🎉\n\n");
        return EXIT_SUCCESS;
    } else {
        printf("\n✗ Some tests FAILED. Review output above.\n\n");
        return EXIT_FAILURE;
    }
}
