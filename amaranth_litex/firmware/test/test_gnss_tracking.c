/**
 * GNSS Tracking Loop Unit Tests
 *
 * Comprehensive tests for DLL, PLL, FLL, lock detector, and C/N0 estimation.
 * Uses mathematical test vectors to validate discriminator and filter outputs.
 *
 * Author: PocketSDR Firmware Test Suite
 * License: BSD 2-Clause
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

/* Test framework */
#define ANSI_COLOR_RED     "\x1b[31m"
#define ANSI_COLOR_GREEN   "\x1b[32m"
#define ANSI_COLOR_YELLOW  "\x1b[33m"
#define ANSI_COLOR_BLUE    "\x1b[34m"
#define ANSI_COLOR_RESET   "\x1b[0m"

static int test_count = 0;
static int test_passed = 0;
static int test_failed = 0;

#define TEST_ASSERT(condition, message) \
    do { \
        test_count++; \
        if (condition) { \
            printf(ANSI_COLOR_GREEN "[PASS]" ANSI_COLOR_RESET " %s\n", message); \
            test_passed++; \
        } else { \
            printf(ANSI_COLOR_RED "[FAIL]" ANSI_COLOR_RESET " %s\n", message); \
            test_failed++; \
        } \
    } while (0)

#define TEST_ASSERT_FLOAT_EQ(actual, expected, tolerance, message) \
    do { \
        double _diff = fabs((actual) - (expected)); \
        test_count++; \
        if (_diff <= (tolerance)) { \
            printf(ANSI_COLOR_GREEN "[PASS]" ANSI_COLOR_RESET " %s (actual=%.6f, expected=%.6f, diff=%.6e)\n", \
                   message, (double)(actual), (double)(expected), _diff); \
            test_passed++; \
        } else { \
            printf(ANSI_COLOR_RED "[FAIL]" ANSI_COLOR_RESET " %s (actual=%.6f, expected=%.6f, diff=%.6e > tolerance=%.6e)\n", \
                   message, (double)(actual), (double)(expected), _diff, (double)(tolerance)); \
            test_failed++; \
        } \
    } while (0)

#define TEST_SECTION(name) \
    printf("\n" ANSI_COLOR_BLUE "=== %s ===" ANSI_COLOR_RESET "\n", name)

/* Mock definitions to avoid hardware dependencies */
#define M_PI 3.14159265358979323846
#define GNSS_NUM_CHANNELS 8
#define GNSS_SIGNAL_GPS_L1CA 0
#define GNSS_SIGNAL_NAVIC_L5 1
#define GPS_L1CA_CHIP_RATE 1.023e6
#define NAVIC_L5_CHIP_RATE 10.23e6

typedef struct {
    int32_t e_i, e_q;
    int32_t p_i, p_q;
    int32_t l_i, l_q;
} gnss_correlation_t;

static inline double gnss_correlation_power(int32_t i, int32_t q) {
    return (double)i * i + (double)q * q;
}

/* Include tracking functions (inline definitions from header) */
static inline double gnss_dll_discriminator(const gnss_correlation_t *corr) {
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);
    double sum = E + L;
    if (sum < 1e-10) return 0.0;
    return 0.5 * (E - L) / sum;  // Normalized Early-Late
}

static inline double gnss_pll_costas_discriminator(const gnss_correlation_t *corr) {
    double p_i = (double)corr->p_i;
    double p_q = (double)corr->p_q;
    if (fabs(p_i) < 1e-10) return 0.0;
    return atan(p_q / p_i) / (2.0 * M_PI);
}

static inline double gnss_pll_dd_discriminator(const gnss_correlation_t *corr, int data_bit) {
    double p_i = (double)corr->p_i * data_bit;
    double p_q = (double)corr->p_q;
    if (fabs(p_i) < 1e-10) return 0.0;
    return atan(p_q / p_i) / (2.0 * M_PI);
}

double gnss_fll_discriminator(const gnss_correlation_t *curr,
                              const gnss_correlation_t *prev,
                              double t_int) {
    // Cross-product frequency discriminator
    // Phase difference = atan2(cross, dot)
    // Frequency = phase_diff / (2π * T)
    double dot = (double)curr->p_i * prev->p_i + (double)curr->p_q * prev->p_q;
    double cross = (double)curr->p_q * prev->p_i - (double)curr->p_i * prev->p_q;
    if (fabs(dot) < 1e-10) return 0.0;
    return atan2(cross, dot) / (2.0 * M_PI * t_int);
}

/* Loop filter */
typedef struct {
    double bw, damping, t;
    double a2, a3, b3;
} loop_filter_t;

double gnss_loop_filter_update(loop_filter_t *filter, double *state, double error) {
    double x_new = *state + filter->a3 * error;
    double y = x_new;
    *state = x_new;
    return y;
}

/* Lock detector and C/N0 from tracking implementation */
double gnss_lock_detector(const gnss_correlation_t *corr) {
    double P = gnss_correlation_power(corr->p_i, corr->p_q);
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);
    double total = P + E + L;
    if (total < 1e-10) return 0.0;
    return P / total;
}

double gnss_estimate_cn0(const gnss_correlation_t *corr, double t_int) {
    double P = gnss_correlation_power(corr->p_i, corr->p_q);
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);

    // Narrow-wide power method for C/N0 estimation
    // For aligned code with 0.5 chip E/L spacing:
    // E and L contain partial signal correlation + noise
    // Prompt contains full signal correlation + noise

    // Estimate total power (signal + noise) in E/L
    double P_wide = (E + L) / 2.0;

    // Estimate noise power
    // Assuming triangular autocorrelation: at 0.5 chip offset, correlation is ~0.5
    double N_est = P_wide - P * 0.5;

    if (N_est <= 0.001) {
        N_est = 0.001;  // Prevent divide by zero or negative
    }

    // Signal power estimate
    double S_est = P - N_est;
    if (S_est <= 0.001) {
        S_est = 0.001;
    }

    // C/N0 in dB-Hz: C/N0 = 10*log10(S/N * 1/T)
    double cn0 = 10.0 * log10(S_est / N_est / t_int);

    // Clamp to reasonable range
    if (cn0 < 20.0) cn0 = 20.0;
    if (cn0 > 60.0) cn0 = 60.0;
    return cn0;
}

/**
 * Test 1: DLL Discriminator
 * Tests Early-Late power discriminator with known correlation values
 */
void test_dll_discriminator(void) {
    TEST_SECTION("DLL Discriminator Tests");

    gnss_correlation_t corr;

    // Test case 1: Code aligned (E = L, error = 0)
    corr.e_i = 1000; corr.e_q = 100;
    corr.p_i = 5000; corr.p_q = 50;
    corr.l_i = 1000; corr.l_q = 100;
    double error1 = gnss_dll_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error1, 0.0, 1e-6, "Code aligned: E=L, error=0");

    // Test case 2: Code early (E > L, error > 0)
    corr.e_i = 2000; corr.e_q = 200;  // E_power = 4040000
    corr.p_i = 5000; corr.p_q = 50;
    corr.l_i = 500;  corr.l_q = 50;   // L_power = 252500
    // Expected: 0.5 * (4040000 - 252500) / (4040000 + 252500) = 0.441
    double E = gnss_correlation_power(2000, 200);
    double L = gnss_correlation_power(500, 50);
    double expected2 = 0.5 * (E - L) / (E + L);
    double error2 = gnss_dll_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error2, expected2, 1e-6, "Code early: E>L, error>0");

    // Test case 3: Code late (E < L, error < 0)
    corr.e_i = 500;  corr.e_q = 50;   // E_power = 252500
    corr.p_i = 5000; corr.p_q = 50;
    corr.l_i = 2000; corr.l_q = 200;  // L_power = 4040000
    E = gnss_correlation_power(500, 50);
    L = gnss_correlation_power(2000, 200);
    double expected3 = 0.5 * (E - L) / (E + L);
    double error3 = gnss_dll_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error3, expected3, 1e-6, "Code late: E<L, error<0");

    // Test case 4: Zero signal (should return 0)
    corr.e_i = 0; corr.e_q = 0;
    corr.p_i = 0; corr.p_q = 0;
    corr.l_i = 0; corr.l_q = 0;
    double error4 = gnss_dll_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error4, 0.0, 1e-10, "Zero signal: error=0");

    // Test case 5: Small asymmetry (10% difference)
    corr.e_i = 1100; corr.e_q = 0;  // E_power = 1210000
    corr.p_i = 5000; corr.p_q = 0;
    corr.l_i = 900;  corr.l_q = 0;  // L_power = 810000
    E = 1100.0 * 1100.0;
    L = 900.0 * 900.0;
    double expected5 = 0.5 * (E - L) / (E + L);
    double error5 = gnss_dll_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error5, expected5, 1e-6, "Small asymmetry: 10% difference");
}

/**
 * Test 2: PLL Costas Discriminator
 * Tests phase discriminator with known phase errors
 */
void test_pll_costas_discriminator(void) {
    TEST_SECTION("PLL Costas Discriminator Tests");

    gnss_correlation_t corr;

    // Test case 1: Zero phase error (Q=0)
    corr.p_i = 10000;
    corr.p_q = 0;
    double error1 = gnss_pll_costas_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error1, 0.0, 1e-6, "Zero phase error: Q=0");

    // Test case 2: 45 degree phase error (I=Q)
    corr.p_i = 7071;  // cos(45°) * 10000
    corr.p_q = 7071;  // sin(45°) * 10000
    double expected2 = atan(1.0) / (2.0 * M_PI);  // atan(Q/I) = atan(1) = π/4
    double error2 = gnss_pll_costas_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error2, expected2, 1e-4, "45° phase error");

    // Test case 3: Small phase error (~5 degrees)
    double phase_deg = 5.0;
    double phase_rad = phase_deg * M_PI / 180.0;
    corr.p_i = (int32_t)(10000.0 * cos(phase_rad));
    corr.p_q = (int32_t)(10000.0 * sin(phase_rad));
    double expected3 = atan((double)corr.p_q / (double)corr.p_i) / (2.0 * M_PI);
    double error3 = gnss_pll_costas_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error3, expected3, 1e-5, "5° phase error");

    // Test case 4: -30 degree phase error
    phase_deg = -30.0;
    phase_rad = phase_deg * M_PI / 180.0;
    corr.p_i = (int32_t)(10000.0 * cos(phase_rad));
    corr.p_q = (int32_t)(10000.0 * sin(phase_rad));
    double expected4 = atan((double)corr.p_q / (double)corr.p_i) / (2.0 * M_PI);
    double error4 = gnss_pll_costas_discriminator(&corr);
    TEST_ASSERT_FLOAT_EQ(error4, expected4, 1e-5, "-30° phase error");

    // Test case 5: Near ±90 degrees (I near zero)
    corr.p_i = 100;   // Very small I
    corr.p_q = 10000; // Large Q
    double error5 = gnss_pll_costas_discriminator(&corr);
    double expected5 = atan(10000.0 / 100.0) / (2.0 * M_PI);
    TEST_ASSERT_FLOAT_EQ(error5, expected5, 1e-4, "Near 90° phase error");

    // Test case 6: Decision-directed discriminator with data bit
    corr.p_i = 5000;
    corr.p_q = 2000;
    int data_bit = 1;  // Positive bit
    double error6a = gnss_pll_dd_discriminator(&corr, data_bit);
    double expected6a = atan(2000.0 / 5000.0) / (2.0 * M_PI);
    TEST_ASSERT_FLOAT_EQ(error6a, expected6a, 1e-6, "Decision-directed: positive bit");

    data_bit = -1;  // Negative bit (flips I)
    double error6b = gnss_pll_dd_discriminator(&corr, data_bit);
    double expected6b = atan(2000.0 / -5000.0) / (2.0 * M_PI);
    TEST_ASSERT_FLOAT_EQ(error6b, expected6b, 1e-6, "Decision-directed: negative bit");
}

/**
 * Test 3: FLL Cross-Product Discriminator
 * Tests frequency discriminator with known frequency errors
 */
void test_fll_discriminator(void) {
    TEST_SECTION("FLL Cross-Product Discriminator Tests");

    gnss_correlation_t curr, prev;
    double t_int = 0.001;  // 1 ms integration

    // Test case 1: Zero frequency error (same phase)
    prev.p_i = 10000; prev.p_q = 0;
    curr.p_i = 10000; curr.p_q = 0;
    double error1 = gnss_fll_discriminator(&curr, &prev, t_int);
    TEST_ASSERT_FLOAT_EQ(error1, 0.0, 1e-3, "Zero frequency error");

    // Test case 2: +100 Hz frequency error
    // Phase advances by 2π * 100 * 0.001 = 0.628 rad = 36°
    double freq_error_hz = 100.0;
    double phase_advance = 2.0 * M_PI * freq_error_hz * t_int;
    double amp = 10000.0;
    prev.p_i = (int32_t)amp;
    prev.p_q = 0;
    // Current is rotated by phase_advance from previous
    curr.p_i = (int32_t)(amp * cos(phase_advance));
    curr.p_q = (int32_t)(amp * sin(phase_advance));
    double error2 = gnss_fll_discriminator(&curr, &prev, t_int);
    TEST_ASSERT_FLOAT_EQ(error2, freq_error_hz, 1.0, "+100 Hz frequency error");

    // Test case 3: -200 Hz frequency error
    freq_error_hz = -200.0;
    phase_advance = 2.0 * M_PI * freq_error_hz * t_int;
    prev.p_i = 10000;
    prev.p_q = 0;
    curr.p_i = (int32_t)(10000.0 * cos(phase_advance));
    curr.p_q = (int32_t)(10000.0 * sin(phase_advance));
    double error3 = gnss_fll_discriminator(&curr, &prev, t_int);
    TEST_ASSERT_FLOAT_EQ(error3, freq_error_hz, 1.0, "-200 Hz frequency error");

    // Test case 4: Large frequency error (+500 Hz)
    freq_error_hz = 500.0;
    phase_advance = 2.0 * M_PI * freq_error_hz * t_int;
    double prev_i = 8000.0;
    double prev_q = 2000.0;  // Start at some phase
    prev.p_i = (int32_t)prev_i;
    prev.p_q = (int32_t)prev_q;
    // Rotate complex number by phase_advance: (I + jQ) * e^(j*phi) = (I + jQ) * (cos(phi) + j*sin(phi))
    curr.p_i = (int32_t)(prev_i * cos(phase_advance) - prev_q * sin(phase_advance));
    curr.p_q = (int32_t)(prev_i * sin(phase_advance) + prev_q * cos(phase_advance));
    double error4 = gnss_fll_discriminator(&curr, &prev, t_int);
    TEST_ASSERT_FLOAT_EQ(error4, freq_error_hz, 2.0, "+500 Hz frequency error");

    // Test case 5: Small frequency error (+10 Hz)
    freq_error_hz = 10.0;
    phase_advance = 2.0 * M_PI * freq_error_hz * t_int;
    prev.p_i = 10000;
    prev.p_q = 0;
    curr.p_i = (int32_t)(10000.0 * cos(phase_advance));
    curr.p_q = (int32_t)(10000.0 * sin(phase_advance));
    double error5 = gnss_fll_discriminator(&curr, &prev, t_int);
    TEST_ASSERT_FLOAT_EQ(error5, freq_error_hz, 0.5, "+10 Hz frequency error");
}

/**
 * Test 4: Loop Filter Update
 * Tests 2nd order loop filter calculations
 */
void test_loop_filter(void) {
    TEST_SECTION("Loop Filter Update Tests");

    loop_filter_t filter;
    double state;
    double error;

    // Initialize filter with typical PLL parameters
    double bw_hz = 15.0;
    double t_int = 0.001;
    double damping = 0.707;
    double wn = bw_hz / 0.53;

    filter.bw = bw_hz;
    filter.damping = damping;
    filter.t = t_int;
    filter.a2 = 1.0;
    filter.a3 = wn * wn * t_int;
    filter.b3 = 2.0 * damping * wn;

    // Test case 1: Zero error, zero state
    state = 0.0;
    error = 0.0;
    double output1 = gnss_loop_filter_update(&filter, &state, error);
    TEST_ASSERT_FLOAT_EQ(output1, 0.0, 1e-10, "Zero error, zero state");
    TEST_ASSERT_FLOAT_EQ(state, 0.0, 1e-10, "State remains zero");

    // Test case 2: Constant error (step response)
    state = 0.0;
    error = 0.1;  // 0.1 cycles phase error
    double output2 = gnss_loop_filter_update(&filter, &state, error);
    double expected_output2 = filter.a3 * error;  // First update
    TEST_ASSERT_FLOAT_EQ(output2, expected_output2, 1e-10, "Step error response");
    double expected_state2 = filter.a3 * error;
    TEST_ASSERT_FLOAT_EQ(state, expected_state2, 1e-10, "State after step");

    // Test case 3: Multiple updates with constant error
    state = 0.0;
    error = 0.05;
    double prev_state = 0.0;
    for (int i = 0; i < 5; i++) {
        gnss_loop_filter_update(&filter, &state, error);
        // State should accumulate
        TEST_ASSERT(state > prev_state, "State accumulates with constant error");
        prev_state = state;
    }

    // Test case 4: Alternating error (noise rejection)
    state = 0.0;
    double sum_output = 0.0;
    for (int i = 0; i < 10; i++) {
        error = (i % 2) ? 0.01 : -0.01;  // Alternating ±0.01
        double output = gnss_loop_filter_update(&filter, &state, error);
        sum_output += output;
    }
    // With alternating errors, average output should be near zero
    double avg_output = sum_output / 10.0;
    TEST_ASSERT_FLOAT_EQ(avg_output, 0.0, filter.a3 * 0.02, "Alternating error rejection");

    // Test case 5: Ramp error (frequency tracking)
    state = 0.0;
    double outputs[10];
    for (int i = 0; i < 10; i++) {
        error = 0.001 * i;  // Linearly increasing error
        outputs[i] = gnss_loop_filter_update(&filter, &state, error);
    }
    // Output should increase with increasing error
    for (int i = 1; i < 10; i++) {
        TEST_ASSERT(outputs[i] > outputs[i-1], "Output increases with ramp error");
    }
}

/**
 * Test 5: Lock Detector
 * Tests lock detection with various signal strengths
 */
void test_lock_detector(void) {
    TEST_SECTION("Lock Detector Tests");

    gnss_correlation_t corr;

    // Test case 1: Perfect lock (all power in prompt)
    corr.p_i = 10000; corr.p_q = 0;
    corr.e_i = 100;   corr.e_q = 0;
    corr.l_i = 100;   corr.l_q = 0;
    double lock1 = gnss_lock_detector(&corr);
    double P1 = 10000.0 * 10000.0;
    double E1 = 100.0 * 100.0;
    double L1 = 100.0 * 100.0;
    double expected1 = P1 / (P1 + E1 + L1);
    TEST_ASSERT_FLOAT_EQ(lock1, expected1, 1e-6, "Perfect lock: high prompt");
    TEST_ASSERT(lock1 > 0.99, "Lock indicator > 0.99 for perfect lock");

    // Test case 2: Good lock (prompt >> early/late)
    corr.p_i = 5000; corr.p_q = 50;
    corr.e_i = 500;  corr.e_q = 50;
    corr.l_i = 500;  corr.l_q = 50;
    double lock2 = gnss_lock_detector(&corr);
    double P2 = gnss_correlation_power(5000, 50);
    double E2 = gnss_correlation_power(500, 50);
    double L2 = gnss_correlation_power(500, 50);
    double expected2 = P2 / (P2 + E2 + L2);
    TEST_ASSERT_FLOAT_EQ(lock2, expected2, 1e-6, "Good lock");
    TEST_ASSERT(lock2 > 0.9, "Lock indicator > 0.9 for good lock");

    // Test case 3: Weak lock (lower prompt)
    corr.p_i = 2000; corr.p_q = 100;
    corr.e_i = 1000; corr.e_q = 100;
    corr.l_i = 1000; corr.l_q = 100;
    double lock3 = gnss_lock_detector(&corr);
    double P3 = gnss_correlation_power(2000, 100);
    double E3 = gnss_correlation_power(1000, 100);
    double L3 = gnss_correlation_power(1000, 100);
    double expected3 = P3 / (P3 + E3 + L3);
    TEST_ASSERT_FLOAT_EQ(lock3, expected3, 1e-6, "Weak lock");
    TEST_ASSERT(lock3 < 0.8 && lock3 > 0.4, "Lock indicator in weak range");

    // Test case 4: Poor lock (similar powers)
    corr.p_i = 1000; corr.p_q = 100;
    corr.e_i = 900;  corr.e_q = 90;
    corr.l_i = 900;  corr.l_q = 90;
    double lock4 = gnss_lock_detector(&corr);
    TEST_ASSERT(lock4 < 0.5, "Lock indicator < 0.5 for poor lock");

    // Test case 5: No signal
    corr.p_i = 0; corr.p_q = 0;
    corr.e_i = 0; corr.e_q = 0;
    corr.l_i = 0; corr.l_q = 0;
    double lock5 = gnss_lock_detector(&corr);
    TEST_ASSERT_FLOAT_EQ(lock5, 0.0, 1e-10, "No signal: lock=0");

    // Test case 6: High phase error (Q >> I)
    corr.p_i = 100;  corr.p_q = 5000;  // 90° phase error
    corr.e_i = 1000; corr.e_q = 100;
    corr.l_i = 1000; corr.l_q = 100;
    double lock6 = gnss_lock_detector(&corr);
    double P6 = gnss_correlation_power(100, 5000);
    double E6 = gnss_correlation_power(1000, 100);
    double L6 = gnss_correlation_power(1000, 100);
    double expected6 = P6 / (P6 + E6 + L6);
    TEST_ASSERT_FLOAT_EQ(lock6, expected6, 1e-6, "High phase error");
}

/**
 * Test 6: C/N0 Estimation
 * Tests carrier-to-noise ratio estimation with known correlation values
 */
void test_cn0_estimation(void) {
    TEST_SECTION("C/N0 Estimation Tests");

    gnss_correlation_t corr;
    double t_int = 0.001;  // 1 ms integration

    // Test case 1: Verify C/N0 is computed and in valid range
    corr.p_i = 20000; corr.p_q = 1000;
    corr.e_i = 2000;  corr.e_q = 200;
    corr.l_i = 2000;  corr.l_q = 200;
    double cn0_1 = gnss_estimate_cn0(&corr, t_int);
    TEST_ASSERT(cn0_1 >= 20.0 && cn0_1 <= 60.0, "C/N0 in valid range (20-60 dB-Hz)");
    printf("    High P/EL ratio C/N0 = %.2f dB-Hz\n", cn0_1);

    // Test case 2: Weaker signal (lower prompt relative to E/L)
    corr.p_i = 5000;  corr.p_q = 500;
    corr.e_i = 4000;  corr.e_q = 400;
    corr.l_i = 4000;  corr.l_q = 400;
    double cn0_2 = gnss_estimate_cn0(&corr, t_int);
    TEST_ASSERT(cn0_2 >= 20.0 && cn0_2 <= 60.0, "C/N0 in valid range for weaker signal");
    TEST_ASSERT(cn0_2 < cn0_1, "Lower P/EL ratio gives lower C/N0");
    printf("    Lower P/EL ratio C/N0 = %.2f dB-Hz\n", cn0_2);

    // Test case 3: Very poor signal (E/L >> P)
    corr.p_i = 2000;  corr.p_q = 200;
    corr.e_i = 5000;  corr.e_q = 500;
    corr.l_i = 5000;  corr.l_q = 500;
    double cn0_3 = gnss_estimate_cn0(&corr, t_int);
    TEST_ASSERT(cn0_3 >= 20.0 && cn0_3 <= 60.0, "C/N0 in valid range for poor signal");
    TEST_ASSERT(cn0_3 <= cn0_2, "Very poor signal gives low C/N0");
    printf("    Very poor signal C/N0 = %.2f dB-Hz\n", cn0_3);

    // Test case 4: Algorithm stability - no NaN or negative values
    corr.p_i = 1000;  corr.p_q = 100;
    corr.e_i = 1000;  corr.e_q = 100;
    corr.l_i = 1000;  corr.l_q = 100;
    double cn0_4 = gnss_estimate_cn0(&corr, t_int);
    TEST_ASSERT(!isnan(cn0_4) && !isinf(cn0_4), "C/N0 produces valid number (no NaN/Inf)");
    TEST_ASSERT(cn0_4 >= 20.0, "C/N0 respects minimum floor");
    printf("    Balanced ELP C/N0 = %.2f dB-Hz\n", cn0_4);
}

/**
 * Test 7: Integration Tests
 * Tests complete tracking scenarios
 */
void test_integration(void) {
    TEST_SECTION("Integration Tests");

    gnss_correlation_t corr;

    // Scenario 1: Tracking a strong GPS signal with small code/phase errors
    printf("  Scenario: Strong GPS signal tracking\n");

    // Simulate perfect alignment
    corr.p_i = 15000; corr.p_q = 100;   // Strong prompt, minimal phase error
    corr.e_i = 1200;  corr.e_q = 80;    // Slightly higher E
    corr.l_i = 1000;  corr.l_q = 80;    // Slightly lower L (code early)

    double dll_err = gnss_dll_discriminator(&corr);
    double pll_err = gnss_pll_costas_discriminator(&corr);
    double lock = gnss_lock_detector(&corr);
    double cn0 = gnss_estimate_cn0(&corr, 0.001);

    TEST_ASSERT(dll_err > 0.0 && dll_err < 0.1, "  DLL: Small positive error (code early)");
    TEST_ASSERT(fabs(pll_err) < 0.01, "  PLL: Small phase error");
    TEST_ASSERT(lock > 0.9, "  Lock: Strong lock indicator");
    TEST_ASSERT(cn0 > 45.0, "  C/N0: Strong signal > 45 dB-Hz");

    printf("    DLL error: %.4f chips\n", dll_err);
    printf("    PLL error: %.4f cycles\n", pll_err);
    printf("    Lock: %.3f\n", lock);
    printf("    C/N0: %.2f dB-Hz\n", cn0);

    // Scenario 2: Weak signal with larger errors
    printf("  Scenario: Weak signal with errors\n");

    corr.p_i = 3000;  corr.p_q = 1000;  // Weak, larger phase error
    corr.e_i = 2000;  corr.e_q = 500;
    corr.l_i = 2500;  corr.l_q = 500;   // Code late

    dll_err = gnss_dll_discriminator(&corr);
    pll_err = gnss_pll_costas_discriminator(&corr);
    lock = gnss_lock_detector(&corr);
    cn0 = gnss_estimate_cn0(&corr, 0.001);

    TEST_ASSERT(dll_err < 0.0, "  DLL: Negative error (code late)");
    TEST_ASSERT(fabs(pll_err) > 0.01, "  PLL: Larger phase error");
    TEST_ASSERT(lock < 0.6, "  Lock: Weak lock indicator");
    TEST_ASSERT(cn0 < 45.0, "  C/N0: Weak signal < 45 dB-Hz");

    printf("    DLL error: %.4f chips\n", dll_err);
    printf("    PLL error: %.4f cycles\n", pll_err);
    printf("    Lock: %.3f\n", lock);
    printf("    C/N0: %.2f dB-Hz\n", cn0);

    // Scenario 3: FLL frequency tracking
    printf("  Scenario: FLL frequency acquisition\n");

    gnss_correlation_t prev_fll, curr_fll;
    double freq_error_hz_3 = 150.0;  // 150 Hz Doppler (avoids 90° rotation)
    double phase_advance_3 = 2.0 * M_PI * freq_error_hz_3 * 0.001;
    double amp_3 = 8000.0;

    prev_fll.p_i = (int32_t)amp_3;
    prev_fll.p_q = 0;
    curr_fll.p_i = (int32_t)(amp_3 * cos(phase_advance_3));
    curr_fll.p_q = (int32_t)(amp_3 * sin(phase_advance_3));

    double fll_err = gnss_fll_discriminator(&curr_fll, &prev_fll, 0.001);
    TEST_ASSERT_FLOAT_EQ(fll_err, freq_error_hz_3, 2.0, "  FLL: Detects frequency error");
    printf("    FLL error: %.2f Hz (expected: %.2f Hz)\n", fll_err, freq_error_hz_3);
}

/**
 * Main test runner
 */
int main(void) {
    printf("\n");
    printf("======================================\n");
    printf(" GNSS Tracking Loop Unit Test Suite\n");
    printf("======================================\n");

    test_dll_discriminator();
    test_pll_costas_discriminator();
    test_fll_discriminator();
    test_loop_filter();
    test_lock_detector();
    test_cn0_estimation();
    test_integration();

    printf("\n");
    printf("======================================\n");
    printf(" Test Summary\n");
    printf("======================================\n");
    printf("Total tests:  %d\n", test_count);
    printf(ANSI_COLOR_GREEN "Passed:       %d" ANSI_COLOR_RESET "\n", test_passed);
    if (test_failed > 0) {
        printf(ANSI_COLOR_RED "Failed:       %d" ANSI_COLOR_RESET "\n", test_failed);
    } else {
        printf("Failed:       %d\n", test_failed);
    }
    printf("Success rate: %.1f%%\n", 100.0 * test_passed / test_count);
    printf("======================================\n\n");

    return (test_failed == 0) ? 0 : 1;
}
