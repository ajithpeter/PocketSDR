/**
 * GNSS Baseband CSR Interface Implementation
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include "gnss_csr.h"
#include <stdio.h>

void gnss_init(void) {
    printf("[GNSS] Initializing GNSS baseband...\n");

    // Read and verify version
    uint32_t version = gnss_get_version();
    printf("[GNSS] Version: 0x%08X\n", version);

    if (version != 0xA5A50001) {
        printf("[GNSS] WARNING: Unexpected version!\n");
    }

    // Read channel count
    uint32_t num_channels = gnss_get_channel_count();
    printf("[GNSS] Channels: %u\n", num_channels);

    // Global reset
    printf("[GNSS] Performing global reset...\n");
    gnss_global_reset();

    // Reset all channels
    for (uint8_t ch = 0; ch < num_channels; ch++) {
        gnss_channel_reset(ch);
        gnss_channel_enable(ch, false);
    }

    // Enable IRQ for all channels
    gnss_set_irq_mask((1 << num_channels) - 1);

    // Enable global controls
    gnss_global_enable(true);
    gnss_sample_enable(true);

    printf("[GNSS] Initialization complete\n");
}

void gnss_channel_configure(uint8_t ch, const gnss_channel_config_t *config) {
    printf("[GNSS] Configuring channel %u: PRN=%u, Type=%s\n",
           ch, config->prn,
           config->signal_type == GNSS_SIGNAL_GPS_L1CA ? "GPS L1 C/A" : "NavIC L5");

    // Disable channel during configuration
    gnss_channel_enable(ch, false);

    // Reset channel
    gnss_channel_reset(ch);

    // Configure signal type and PRN
    gnss_channel_set_signal_type(ch, config->signal_type);
    gnss_channel_set_prn(ch, config->prn);

    // Configure NCOs
    gnss_channel_set_carrier_freq(ch, config->carrier_freq);
    gnss_channel_set_carrier_phase(ch, config->carrier_phase);
    gnss_channel_set_code_freq(ch, config->code_freq);

    // Configure integration time
    gnss_channel_set_integration_time(ch, config->integration_time);

    // Enable channel if requested
    if (config->enabled) {
        gnss_channel_enable(ch, true);
    }

    printf("[GNSS] Channel %u configured\n", ch);
}

void gnss_channel_read_status(uint8_t ch, gnss_channel_status_t *status) {
    uint32_t status_reg = gnss_channel_get_status(ch);

    status->dump_ready = (status_reg & GNSS_STATUS_DUMP_READY) != 0;
    status->code_epoch = (status_reg & GNSS_STATUS_CODE_EPOCH) != 0;
    status->chip_count = gnss_channel_get_chip_count(ch);
    status->epoch_count = gnss_channel_get_epoch_count(ch);

    // Read correlation results
    gnss_channel_read_correlation(ch, &status->corr);
}
