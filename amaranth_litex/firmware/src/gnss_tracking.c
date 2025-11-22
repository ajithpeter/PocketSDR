/**
 * GNSS Tracking Loops Implementation
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include "gnss_tracking.h"
#include <stdio.h>
#include <string.h>

#define PI 3.14159265358979323846

void gnss_track_init(gnss_track_channel_t *track, uint8_t channel,
                     uint8_t prn, uint8_t signal_type) {
    memset(track, 0, sizeof(gnss_track_channel_t));

    track->channel = channel;
    track->prn = prn;
    track->signal_type = signal_type;
    track->state = TRACK_STATE_IDLE;

    // Initialize with nominal values
    double chip_rate = (signal_type == GNSS_SIGNAL_GPS_L1CA) ?
                       GPS_L1CA_CHIP_RATE : NAVIC_L5_CHIP_RATE;

    // Integration time: 1 ms
    double t_int = 0.001;

    // Initialize tracking loops with typical bandwidths
    gnss_dll_init(&track->dll, 2.0, t_int);      // 2 Hz DLL bandwidth
    gnss_pll_init(&track->pll, 15.0, t_int);     // 15 Hz PLL bandwidth
    gnss_fll_init(&track->fll, 10.0, t_int);     // 10 Hz FLL bandwidth

    track->dll.chip_rate = chip_rate;
    track->dll.code_freq = chip_rate;

    printf("[TRACK] Initialized channel %u for PRN %u (%s)\n",
           channel, prn,
           signal_type == GNSS_SIGNAL_GPS_L1CA ? "GPS" : "NavIC");
}

void gnss_dll_init(dll_state_t *dll, double bw_hz, double t_int) {
    dll->filter.bw = bw_hz;
    dll->filter.damping = 0.707;  // Critical damping
    dll->filter.t = t_int;

    // 2nd order loop filter coefficients
    double wn = bw_hz / 0.53;  // Natural frequency
    dll->filter.a2 = 1.0;
    dll->filter.a3 = wn * wn * t_int;
    dll->filter.b3 = 2.0 * dll->filter.damping * wn;

    dll->filter_state = 0.0;
    dll->chip_error = 0.0;
}

void gnss_pll_init(pll_state_t *pll, double bw_hz, double t_int) {
    pll->filter.bw = bw_hz;
    pll->filter.damping = 0.707;
    pll->filter.t = t_int;

    double wn = bw_hz / 0.53;
    pll->filter.a2 = 1.0;
    pll->filter.a3 = wn * wn * t_int;
    pll->filter.b3 = 2.0 * pll->filter.damping * wn;

    pll->filter_state = 0.0;
    pll->phase_error = 0.0;
    pll->frequency = 0.0;
    pll->carrier_freq = 0.0;
}

void gnss_fll_init(fll_state_t *fll, double bw_hz, double t_int) {
    fll->filter.bw = bw_hz;
    fll->filter.damping = 0.707;
    fll->filter.t = t_int;

    double wn = bw_hz / 0.53;
    fll->filter.a2 = 1.0;
    fll->filter.a3 = wn * wn * t_int;
    fll->filter.b3 = 2.0 * fll->filter.damping * wn;

    fll->filter_state = 0.0;
    fll->freq_error = 0.0;
    fll->frequency = 0.0;
    fll->prev_phase = 0.0;
}

double gnss_fll_discriminator(const gnss_correlation_t *curr,
                              const gnss_correlation_t *prev,
                              double t_int) {
    // Cross-product discriminator
    double dot = (double)curr->p_i * prev->p_i + (double)curr->p_q * prev->p_q;
    double cross = (double)curr->p_i * prev->p_q - (double)curr->p_q * prev->p_i;

    if (fabs(dot) < 1e-10) return 0.0;

    double freq_error = atan2(cross, dot) / (2.0 * PI * t_int);
    return freq_error;
}

double gnss_loop_filter_update(loop_filter_t *filter, double *state, double error) {
    // 2nd order loop filter
    // x[n] = x[n-1] + a3*e[n] + b3*e[n-1]
    // y[n] = x[n] + a2*e[n]

    double x_new = *state + filter->a3 * error;
    double y = x_new;

    *state = x_new;
    return y;
}

void gnss_dll_update(dll_state_t *dll, const gnss_correlation_t *corr) {
    // Calculate code phase error
    dll->chip_error = gnss_dll_discriminator(corr);

    // Update loop filter
    double code_freq_adj = gnss_loop_filter_update(&dll->filter,
                                                    &dll->filter_state,
                                                    dll->chip_error);

    // Update code frequency
    dll->code_freq = dll->chip_rate + code_freq_adj;

    // Clamp to reasonable range
    if (dll->code_freq < dll->chip_rate * 0.99) {
        dll->code_freq = dll->chip_rate * 0.99;
    }
    if (dll->code_freq > dll->chip_rate * 1.01) {
        dll->code_freq = dll->chip_rate * 1.01;
    }
}

void gnss_pll_update(pll_state_t *pll, const gnss_correlation_t *corr, int data_bit) {
    // Calculate phase error
    if (data_bit != 0) {
        // Decision-directed (when data bit is known)
        pll->phase_error = gnss_pll_dd_discriminator(corr, data_bit);
    } else {
        // Costas loop (data-wiping)
        pll->phase_error = gnss_pll_costas_discriminator(corr);
    }

    // Update loop filter
    double freq_adj = gnss_loop_filter_update(&pll->filter,
                                              &pll->filter_state,
                                              pll->phase_error);

    // Update carrier frequency
    pll->carrier_freq = pll->frequency + freq_adj;
}

void gnss_fll_update(fll_state_t *fll, const gnss_correlation_t *curr,
                     const gnss_correlation_t *prev, double t_int) {
    // Calculate frequency error
    fll->freq_error = gnss_fll_discriminator(curr, prev, t_int);

    // Update loop filter
    double freq_adj = gnss_loop_filter_update(&fll->filter,
                                              &fll->filter_state,
                                              fll->freq_error);

    // Update frequency estimate
    fll->frequency += freq_adj;

    // Clamp to ±10 kHz (typical Doppler range)
    if (fll->frequency < -10000.0) fll->frequency = -10000.0;
    if (fll->frequency > 10000.0) fll->frequency = 10000.0;
}

void gnss_track_update(gnss_track_channel_t *track, const gnss_correlation_t *corr) {
    static gnss_correlation_t prev_corr[GNSS_NUM_CHANNELS];

    // Update DLL (code tracking)
    gnss_dll_update(&track->dll, corr);

    // Update tracking loops based on state
    switch (track->state) {
        case TRACK_STATE_IDLE:
            // Not tracking yet
            break;

        case TRACK_STATE_PULL_IN:
        case TRACK_STATE_FREQUENCY:
            // Use FLL for frequency acquisition
            gnss_fll_update(&track->fll, corr, &prev_corr[track->channel], 0.001);
            track->pll.carrier_freq = track->fll.frequency;

            // Check if frequency is stable
            if (fabs(track->fll.freq_error) < 10.0) {  // < 10 Hz error
                track->lock_count++;
                if (track->lock_count > 100) {  // 100 ms stable
                    track->state = TRACK_STATE_PHASE;
                    printf("[TRACK] Ch%u: FLL locked, switching to PLL\n", track->channel);
                }
            } else {
                track->lock_count = 0;
            }
            break;

        case TRACK_STATE_PHASE:
        case TRACK_STATE_LOCKED:
            // Use PLL for phase tracking
            int data_bit = gnss_detect_bit_transition(track, corr);
            gnss_pll_update(&track->pll, corr, data_bit);

            // Check lock quality
            track->lock_indicator = gnss_lock_detector(corr);
            if (track->lock_indicator > 0.8) {
                track->lock_count++;
                if (track->lock_count > 50 && track->state == TRACK_STATE_PHASE) {
                    track->state = TRACK_STATE_LOCKED;
                    printf("[TRACK] Ch%u: PLL locked\n", track->channel);
                }
            } else {
                track->lock_count = 0;
                if (track->state == TRACK_STATE_LOCKED) {
                    track->state = TRACK_STATE_FREQUENCY;
                    printf("[TRACK] Ch%u: Lost lock, reverting to FLL\n", track->channel);
                }
            }
            break;
    }

    // Update signal quality
    track->cn0 = gnss_estimate_cn0(corr, 0.001);

    // Save correlation for next iteration
    prev_corr[track->channel] = *corr;
}

double gnss_estimate_cn0(const gnss_correlation_t *corr, double t_int) {
    // Simplified C/N0 estimation
    double P = gnss_correlation_power(corr->p_i, corr->p_q);
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);

    // Noise power estimate from Early-Late
    double N = (E + L) / 2.0 - P;
    if (N <= 0.0) N = 1.0;

    // C/N0 in dB-Hz
    double cn0 = 10.0 * log10(P / N / t_int);

    // Clamp to reasonable range
    if (cn0 < 20.0) cn0 = 20.0;
    if (cn0 > 60.0) cn0 = 60.0;

    return cn0;
}

double gnss_lock_detector(const gnss_correlation_t *corr) {
    // Normalized power ratio
    double P = gnss_correlation_power(corr->p_i, corr->p_q);
    double E = gnss_correlation_power(corr->e_i, corr->e_q);
    double L = gnss_correlation_power(corr->l_i, corr->l_q);

    double total = P + E + L;
    if (total < 1e-10) return 0.0;

    return P / total;  // Higher is better (0-1 range)
}

int gnss_detect_bit_transition(gnss_track_channel_t *track,
                               const gnss_correlation_t *corr) {
    // Accumulate prompt I/Q for bit synchronization
    track->prompt_i_sum += corr->p_i;
    track->prompt_q_sum += corr->p_q;
    track->bit_sync_count++;

    // GPS: 20 ms per bit, NavIC: 1 ms per symbol (assuming BPSK)
    uint32_t samples_per_bit = (track->signal_type == GNSS_SIGNAL_GPS_L1CA) ? 20 : 1;

    if (track->bit_sync_count >= samples_per_bit) {
        // Determine bit value
        int bit = (track->prompt_i_sum > 0) ? 1 : -1;

        // Reset accumulator
        track->prompt_i_sum = 0;
        track->prompt_q_sum = 0;
        track->bit_sync_count = 0;

        return bit;
    }

    return 0;  // No bit transition yet
}
