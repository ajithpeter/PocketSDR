/**
 * Vahya GNSS Receiver - Main Firmware
 *
 * Complete GNSS receiver firmware running on VexRiscv RISC-V CPU:
 * 1. Hardware initialization
 * 2. Satellite acquisition
 * 3. Tracking loop execution
 * 4. Navigation message decoding
 * 5. PVT computation and display
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "gnss_csr.h"
#include "gnss_tracking.h"
#include "gnss_nav.h"
#include "gnss_pvt.h"

/* Configuration */
#define NUM_CHANNELS        8  // Vahya board has 8 channels

/* GPS PRNs to track (example: PRN 1, 3, 6, 11, 19, 22, 28, 31) */
static const uint8_t gps_prns[] = {1, 3, 6, 11, 19, 22, 28, 31};

/* Initial Doppler estimates (Hz) - would come from acquisition */
static const double initial_doppler[] = {
    1200.0, -800.0, 500.0, -1500.0, 300.0, -200.0, 900.0, -600.0
};

/* Global state */
typedef struct {
    gnss_track_channel_t track[NUM_CHANNELS];
    gps_nav_decoder_t nav[NUM_CHANNELS];
    gps_ephemeris_t ephemeris[NUM_CHANNELS];
    uint32_t measurement_count;
} receiver_state_t;

static receiver_state_t rx_state;

/* Initialize receiver */
void receiver_init(void) {
    printf("\n");
    printf("============================================================\n");
    printf("       Vahya GNSS Receiver - Full PVT Solution             \n");
    printf("       Amaranth/LiteX Implementation                        \n");
    printf("============================================================\n");
    printf("\n");

    // Initialize GNSS baseband hardware
    gnss_init();

    // Initialize tracking channels
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
        uint8_t prn = gps_prns[ch];

        // Initialize tracking channel
        gnss_track_init(&rx_state.track[ch], ch, prn, GNSS_SIGNAL_GPS_L1CA);

        // Initialize navigation decoder
        gps_nav_init(&rx_state.nav[ch], prn);

        // Configure hardware channel
        gnss_channel_config_t config = {
            .prn = prn,
            .signal_type = GNSS_SIGNAL_GPS_L1CA,
            .carrier_freq = gnss_doppler_to_freq_word(initial_doppler[ch]),
            .carrier_phase = 0,
            .code_freq = gnss_chip_rate_to_freq_word(GPS_L1CA_CHIP_RATE),
            .integration_time = (uint16_t)(GNSS_SAMPLE_RATE * 0.001),  // 1 ms
            .enabled = true
        };

        gnss_channel_configure(ch, &config);

        // Start in pull-in state
        rx_state.track[ch].state = TRACK_STATE_PULL_IN;
    }

    rx_state.measurement_count = 0;

    printf("[RECEIVER] Initialization complete\n");
    printf("[RECEIVER] Tracking %u GPS satellites\n", NUM_CHANNELS);
}

/* Update tracking loops */
void receiver_update_tracking(void) {
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
        gnss_channel_status_t status;
        gnss_channel_read_status(ch, &status);

        if (status.dump_ready) {
            // Update tracking loops
            gnss_track_update(&rx_state.track[ch], &status.corr);

            // Update hardware NCO frequencies
            uint32_t carrier_freq = gnss_doppler_to_freq_word(
                rx_state.track[ch].pll.carrier_freq
            );
            uint32_t code_freq = gnss_chip_rate_to_freq_word(
                rx_state.track[ch].dll.code_freq
            );

            gnss_channel_set_carrier_freq(ch, carrier_freq);
            gnss_channel_set_code_freq(ch, code_freq);

            // Decode navigation data
            int data_bit = gnss_detect_bit_transition(&rx_state.track[ch], &status.corr);
            if (data_bit != 0) {
                bool new_eph = gps_nav_process_bit(&rx_state.nav[ch], data_bit);

                if (new_eph) {
                    gps_nav_get_ephemeris(&rx_state.nav[ch], &rx_state.ephemeris[ch]);
                    printf("[RECEIVER] Ch%u: New ephemeris received for PRN %u\n",
                           ch, gps_prns[ch]);
                }
            }

            // Print status periodically
            if (rx_state.measurement_count % 1000 == 0) {
                printf("[TRACK] Ch%u PRN%2u: State=%d, C/N0=%.1f dB-Hz, Lock=%.2f, "
                       "CarrErr=%.1f Hz, CodeErr=%.3f chips\n",
                       ch, gps_prns[ch],
                       rx_state.track[ch].state,
                       rx_state.track[ch].cn0,
                       rx_state.track[ch].lock_indicator,
                       rx_state.track[ch].pll.phase_error * 1000.0,  // Convert to Hz
                       rx_state.track[ch].dll.chip_error);
            }
        }
    }

    rx_state.measurement_count++;
}

/* Compute and display PVT solution */
void receiver_compute_pvt(void) {
    pvt_solution_t pvt;
    satellite_obs_t observations[MAX_SATELLITES];
    uint8_t num_obs = 0;

    // Initialize with approximate location (example: somewhere in India for NavIC testing)
    pvt_init(&pvt, 12.9716, 77.5946, 920.0);  // Bangalore, India

    // Collect observations from locked channels
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
        // Only use locked channels with valid ephemeris
        if (rx_state.track[ch].state != TRACK_STATE_LOCKED) continue;
        if (!rx_state.ephemeris[ch].valid) continue;

        // Read channel status
        gnss_channel_status_t status;
        gnss_channel_read_status(ch, &status);

        // Create observation
        satellite_obs_t obs;
        obs.prn = gps_prns[ch];
        obs.signal_type = GNSS_SIGNAL_GPS_L1CA;

        // Calculate pseudorange
        obs.pseudorange = gnss_calc_pseudorange(
            (double)status.chip_count,
            status.epoch_count,
            GPS_L1CA_CODE_LENGTH,
            GPS_L1CA_CHIP_RATE
        );

        // Doppler
        obs.doppler = rx_state.track[ch].pll.carrier_freq;

        // Signal quality
        obs.cn0 = rx_state.track[ch].cn0;

        // Compute satellite position
        // Use current TOW estimate (would normally come from nav message)
        double tow = (double)status.epoch_count * 0.001;  // Approximate
        gnss_compute_sat_position(&rx_state.ephemeris[ch], tow,
                                  obs.sat_pos, &obs.sat_clk_bias);

        obs.valid = true;

        // Add to observation array
        pvt_add_observation(&pvt, &obs, observations, &num_obs);
    }

    // Compute PVT if enough satellites
    if (num_obs >= 4) {
        printf("\n[PVT] Computing position with %u satellites...\n", num_obs);

        if (pvt_compute(&pvt, observations, num_obs)) {
            // Print solution
            pvt_print(&pvt);
        } else {
            printf("[PVT] Solution failed\n");
        }
    } else {
        printf("[PVT] Insufficient satellites for solution (%u < 4)\n", num_obs);
        printf("[PVT] Waiting for more satellites to lock...\n");

        // Print which channels are locked
        for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
            printf("  Ch%u PRN%2u: %s, Eph: %s\n",
                   ch, gps_prns[ch],
                   rx_state.track[ch].state == TRACK_STATE_LOCKED ? "LOCKED" : "TRACKING",
                   rx_state.ephemeris[ch].valid ? "VALID" : "WAITING");
        }
    }
}

/* Main loop */
int main(void) {
    // Initialize receiver
    receiver_init();

    printf("\n[RECEIVER] Starting main loop...\n");
    printf("[RECEIVER] Waiting for satellite lock and ephemeris...\n\n");

    uint32_t pvt_update_counter = 0;
    const uint32_t PVT_UPDATE_PERIOD = 1000;  // Compute PVT every 1000 measurements (~1 second)

    while (1) {
        // Update tracking loops (runs on every correlation dump)
        receiver_update_tracking();

        // Compute PVT periodically
        pvt_update_counter++;
        if (pvt_update_counter >= PVT_UPDATE_PERIOD) {
            receiver_compute_pvt();
            pvt_update_counter = 0;
        }

        // Small delay to prevent busy-waiting
        // In production, would use interrupt-driven approach
        for (volatile int i = 0; i < 1000; i++);
    }

    return 0;
}
