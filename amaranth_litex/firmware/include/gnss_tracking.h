/**
 * GNSS Tracking Loops
 *
 * Implements carrier and code tracking loops:
 * - FLL (Frequency Lock Loop) for initial frequency acquisition
 * - PLL (Phase Lock Loop) for carrier phase tracking
 * - DLL (Delay Lock Loop) for code phase tracking
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#ifndef GNSS_TRACKING_H
#define GNSS_TRACKING_H

#include "gnss_csr.h"
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* Tracking state machine */
typedef enum {
    TRACK_STATE_IDLE,           // Not tracking
    TRACK_STATE_PULL_IN,        // Initial pull-in (FLL)
    TRACK_STATE_FREQUENCY,      // Frequency tracking (FLL)
    TRACK_STATE_PHASE,          // Phase tracking (PLL)
    TRACK_STATE_LOCKED          // Fully locked
} track_state_t;

/* Loop filter configuration */
typedef struct {
    double bw;                  // Loop bandwidth (Hz)
    double damping;             // Damping ratio
    double t;                   // Integration time (s)
    double a2;                  // Filter coefficient a2
    double a3;                  // Filter coefficient a3
    double b3;                  // Filter coefficient b3
} loop_filter_t;

/* DLL (Code tracking) state */
typedef struct {
    double chip_error;          // Code phase error (chips)
    double chip_rate;           // Code chip rate (Hz)
    double code_freq;           // Code NCO frequency (Hz)
    loop_filter_t filter;       // Loop filter
    double filter_state;        // Filter integrator state
} dll_state_t;

/* PLL (Carrier phase tracking) state */
typedef struct {
    double phase_error;         // Carrier phase error (cycles)
    double frequency;           // Carrier frequency (Hz)
    double carrier_freq;        // Carrier NCO frequency (Hz)
    loop_filter_t filter;       // Loop filter
    double filter_state;        // Filter integrator state
} pll_state_t;

/* FLL (Frequency tracking) state */
typedef struct {
    double freq_error;          // Frequency error (Hz)
    double frequency;           // Current frequency estimate (Hz)
    loop_filter_t filter;       // Loop filter
    double filter_state;        // Filter integrator state
    double prev_phase;          // Previous phase for frequency estimation
} fll_state_t;

/* Complete tracking channel state */
typedef struct {
    uint8_t channel;            // Hardware channel number
    uint8_t prn;                // PRN being tracked
    uint8_t signal_type;        // Signal type (GPS/NavIC)
    track_state_t state;        // Current tracking state

    /* Tracking loops */
    dll_state_t dll;            // Code tracking
    pll_state_t pll;            // Carrier phase tracking
    fll_state_t fll;            // Carrier frequency tracking

    /* Signal quality metrics */
    double cn0;                 // Carrier-to-noise ratio (dB-Hz)
    double lock_indicator;      // Lock detector output
    uint32_t lock_count;        // Consecutive locks

    /* Navigation data */
    int32_t prompt_i_sum;       // Accumulated prompt I (for nav bits)
    int32_t prompt_q_sum;       // Accumulated prompt Q
    uint32_t bit_sync_count;    // Bit synchronization counter

    /* Pseudorange */
    double code_phase;          // Code phase (chips)
    uint32_t code_epoch;        // Code epoch count
    double carrier_phase;       // Carrier phase (cycles)

} gnss_track_channel_t;

/* === Tracking initialization === */

/**
 * Initialize tracking channel
 */
void gnss_track_init(gnss_track_channel_t *track, uint8_t channel,
                     uint8_t prn, uint8_t signal_type);

/**
 * Initialize DLL with bandwidth
 */
void gnss_dll_init(dll_state_t *dll, double bw_hz, double t_int);

/**
 * Initialize PLL with bandwidth
 */
void gnss_pll_init(pll_state_t *pll, double bw_hz, double t_int);

/**
 * Initialize FLL with bandwidth
 */
void gnss_fll_init(fll_state_t *fll, double bw_hz, double t_int);

/* === Discriminators === */

/**
 * Early-Late Power DLL discriminator
 * Returns code phase error in chips
 */
static inline double gnss_dll_discriminator(const gnss_correlation_t *corr) {
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);
    double sum = E + L;
    if (sum < 1e-10) return 0.0;
    return 0.5 * (E - L) / sum;  // Normalized Early-Late
}

/**
 * Costas PLL discriminator (for data-wiping)
 * Returns phase error in cycles
 */
static inline double gnss_pll_costas_discriminator(const gnss_correlation_t *corr) {
    double p_i = (double)corr->p_i;
    double p_q = (double)corr->p_q;
    if (fabs(p_i) < 1e-10) return 0.0;
    return atan(p_q / p_i) / (2.0 * M_PI);
}

/**
 * Decision-directed PLL discriminator (when data is known)
 * Returns phase error in cycles
 */
static inline double gnss_pll_dd_discriminator(const gnss_correlation_t *corr, int data_bit) {
    double p_i = (double)corr->p_i * data_bit;
    double p_q = (double)corr->p_q;
    if (fabs(p_i) < 1e-10) return 0.0;
    return atan(p_q / p_i) / (2.0 * M_PI);
}

/**
 * FLL discriminator (cross-product)
 * Returns frequency error in Hz
 */
double gnss_fll_discriminator(const gnss_correlation_t *curr,
                              const gnss_correlation_t *prev,
                              double t_int);

/* === Loop filters === */

/**
 * 2nd order loop filter update
 */
double gnss_loop_filter_update(loop_filter_t *filter, double *state, double error);

/* === Tracking updates === */

/**
 * Update DLL (code tracking)
 */
void gnss_dll_update(dll_state_t *dll, const gnss_correlation_t *corr);

/**
 * Update PLL (carrier phase tracking)
 */
void gnss_pll_update(pll_state_t *pll, const gnss_correlation_t *corr, int data_bit);

/**
 * Update FLL (carrier frequency tracking)
 */
void gnss_fll_update(fll_state_t *fll, const gnss_correlation_t *curr,
                     const gnss_correlation_t *prev, double t_int);

/**
 * Complete tracking channel update
 * Called when correlation dump is ready
 */
void gnss_track_update(gnss_track_channel_t *track, const gnss_correlation_t *corr);

/* === Signal quality === */

/**
 * Estimate C/N0 (Carrier-to-Noise ratio)
 */
double gnss_estimate_cn0(const gnss_correlation_t *corr, double t_int);

/**
 * Lock detector
 * Returns value 0.0 (unlocked) to 1.0 (locked)
 */
double gnss_lock_detector(const gnss_correlation_t *corr);

/* === Bit synchronization === */

/**
 * Detect navigation data bit transitions
 * Returns: 1 = positive bit, -1 = negative bit, 0 = no transition
 */
int gnss_detect_bit_transition(gnss_track_channel_t *track,
                               const gnss_correlation_t *corr);

#endif /* GNSS_TRACKING_H */
