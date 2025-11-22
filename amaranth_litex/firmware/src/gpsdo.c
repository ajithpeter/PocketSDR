/**
 * GPSDO (GPS Disciplined Oscillator) Control Implementation
 *
 * Author: PocketSDR GPSDO Firmware
 * License: BSD 2-Clause
 */

#include "gpsdo.h"
#include <stdio.h>
#include <string.h>

/* Helper macros for register access */
#define READ_REG(addr)          (*(volatile uint32_t *)(addr))
#define WRITE_REG(addr, val)    (*(volatile uint32_t *)(addr) = (val))

/* Default configuration */
const gpsdo_config_t gpsdo_default_config = {
    .kp_shift = 8,              /* Kp = 1/256 */
    .ki_shift = 16,             /* Ki = 1/65536 */
    .lock_threshold_ns = 100,   /* 100 ns lock threshold */
    .holdover_timeout = 300     /* 5 minutes */
};

/* Internal state */
static struct {
    gpsdo_mode_t mode;
    gpsdo_config_t config;
    gpsdo_stats_t stats;
    uint32_t mode_start_time;
    uint32_t last_tow_update;
    uint32_t current_time;
    uint16_t holdover_dac;
    bool initialized;
} gpsdo_state;

/**
 * Read current phase error from hardware.
 */
static inline int32_t gpsdo_read_phase_error(void)
{
    return (int32_t)READ_REG(GPSDO_PHASE_ERROR);
}

/**
 * Read current DAC value from hardware.
 */
static inline uint16_t gpsdo_read_dac_value(void)
{
    return (uint16_t)READ_REG(GPSDO_DAC_VALUE);
}

/**
 * Check if GPSDO is locked.
 */
static inline bool gpsdo_is_locked(void)
{
    return (READ_REG(GPSDO_STATUS) & GPSDO_STATUS_LOCKED) != 0;
}

/**
 * Check if GPS TOW is valid.
 */
static inline bool gpsdo_is_tow_valid(void)
{
    return (READ_REG(GPSDO_STATUS) & GPSDO_STATUS_TOW_VALID) != 0;
}

/**
 * Update statistics with current phase error.
 */
static void gpsdo_update_stats(int32_t phase_error)
{
    /* Update min/max */
    if (phase_error < gpsdo_state.stats.min_phase_error) {
        gpsdo_state.stats.min_phase_error = phase_error;
    }
    if (phase_error > gpsdo_state.stats.max_phase_error) {
        gpsdo_state.stats.max_phase_error = phase_error;
    }

    /* Update running average */
    gpsdo_state.stats.avg_phase_error =
        (gpsdo_state.stats.avg_phase_error * 7 + phase_error) / 8;
}

/**
 * Transition to new GPSDO mode.
 */
static void gpsdo_set_mode(gpsdo_mode_t new_mode)
{
    if (new_mode != gpsdo_state.mode) {
        printf("[GPSDO] Mode change: %d -> %d\n",
               gpsdo_state.mode, new_mode);

        gpsdo_state.mode = new_mode;
        gpsdo_state.mode_start_time = gpsdo_state.current_time;

        /* Mode-specific actions */
        switch (new_mode) {
        case GPSDO_MODE_HOLDOVER:
            /* Save current DAC value for holdover */
            gpsdo_state.holdover_dac = gpsdo_read_dac_value();
            WRITE_REG(GPSDO_HOLDOVER_DAC, gpsdo_state.holdover_dac);
            gpsdo_state.stats.holdover_events++;
            printf("[GPSDO] Entering holdover, DAC=%u\n",
                   gpsdo_state.holdover_dac);
            break;

        case GPSDO_MODE_LOCKED:
            gpsdo_state.stats.lock_count++;
            break;

        case GPSDO_MODE_ACQUIRING:
            /* Reset integrator when starting acquisition */
            gpsdo_reset_integrator();
            break;

        default:
            break;
        }
    }
}

void gpsdo_init(const gpsdo_config_t *config)
{
    printf("[GPSDO] Initializing...\n");

    /* Clear state */
    memset(&gpsdo_state, 0, sizeof(gpsdo_state));

    /* Set configuration */
    if (config) {
        gpsdo_state.config = *config;
    } else {
        gpsdo_state.config = gpsdo_default_config;
    }

    /* Initialize statistics */
    gpsdo_state.stats.min_phase_error = INT32_MAX;
    gpsdo_state.stats.max_phase_error = INT32_MIN;

    /* Configure hardware */
    WRITE_REG(GPSDO_KP_SHIFT, gpsdo_state.config.kp_shift);
    WRITE_REG(GPSDO_KI_SHIFT, gpsdo_state.config.ki_shift);

    /* Start in disabled mode */
    gpsdo_state.mode = GPSDO_MODE_DISABLED;
    WRITE_REG(GPSDO_CTRL, 0);

    gpsdo_state.initialized = true;

    printf("[GPSDO] Initialized\n");
    printf("  Kp shift: %u (Kp = 1/%u)\n",
           gpsdo_state.config.kp_shift,
           1 << gpsdo_state.config.kp_shift);
    printf("  Ki shift: %u (Ki = 1/%u)\n",
           gpsdo_state.config.ki_shift,
           1 << gpsdo_state.config.ki_shift);
}

void gpsdo_update_time(uint32_t tow_ms, bool tow_valid)
{
    if (!gpsdo_state.initialized) {
        return;
    }

    /* Write TOW to hardware */
    WRITE_REG(GPSDO_TOW, tow_ms);

    /* Update status based on TOW validity */
    if (tow_valid) {
        gpsdo_state.last_tow_update = gpsdo_state.current_time;

        /* If we were in holdover, transition back to disciplining */
        if (gpsdo_state.mode == GPSDO_MODE_HOLDOVER) {
            uint32_t holdover_duration =
                gpsdo_state.current_time - gpsdo_state.mode_start_time;

            if (holdover_duration > gpsdo_state.stats.max_holdover_time) {
                gpsdo_state.stats.max_holdover_time = holdover_duration;
            }

            printf("[GPSDO] Exiting holdover after %u seconds\n",
                   holdover_duration);

            gpsdo_set_mode(GPSDO_MODE_ACQUIRING);
        }
    }
}

void gpsdo_periodic_update(void)
{
    if (!gpsdo_state.initialized) {
        return;
    }

    gpsdo_state.current_time++;

    /* Check for GPS timeout */
    uint32_t time_since_update =
        gpsdo_state.current_time - gpsdo_state.last_tow_update;

    bool tow_valid = gpsdo_is_tow_valid();
    bool locked = gpsdo_is_locked();
    int32_t phase_error = gpsdo_read_phase_error();

    /* Update statistics */
    if (gpsdo_state.mode == GPSDO_MODE_DISCIPLINING ||
        gpsdo_state.mode == GPSDO_MODE_LOCKED) {
        gpsdo_update_stats(phase_error);
    }

    /* State machine */
    switch (gpsdo_state.mode) {
    case GPSDO_MODE_DISABLED:
        /* Nothing to do */
        break;

    case GPSDO_MODE_ACQUIRING:
        if (!tow_valid || time_since_update > gpsdo_state.config.holdover_timeout) {
            gpsdo_set_mode(GPSDO_MODE_HOLDOVER);
        } else if (locked) {
            gpsdo_set_mode(GPSDO_MODE_LOCKED);
        } else {
            /* Check if we've been acquiring long enough */
            uint32_t time_in_mode =
                gpsdo_state.current_time - gpsdo_state.mode_start_time;
            if (time_in_mode > 10) {
                gpsdo_set_mode(GPSDO_MODE_DISCIPLINING);
            }
        }
        break;

    case GPSDO_MODE_DISCIPLINING:
        if (!tow_valid || time_since_update > gpsdo_state.config.holdover_timeout) {
            gpsdo_set_mode(GPSDO_MODE_HOLDOVER);
        } else if (locked) {
            gpsdo_set_mode(GPSDO_MODE_LOCKED);
        }
        break;

    case GPSDO_MODE_LOCKED:
        if (!tow_valid || time_since_update > gpsdo_state.config.holdover_timeout) {
            gpsdo_set_mode(GPSDO_MODE_HOLDOVER);
        } else if (!locked) {
            gpsdo_set_mode(GPSDO_MODE_DISCIPLINING);
        } else {
            /* Update lock time */
            gpsdo_state.stats.lock_time++;
        }
        break;

    case GPSDO_MODE_HOLDOVER:
        /* Check if GPS came back */
        if (tow_valid && time_since_update < gpsdo_state.config.holdover_timeout) {
            uint32_t holdover_duration =
                gpsdo_state.current_time - gpsdo_state.mode_start_time;

            if (holdover_duration > gpsdo_state.stats.max_holdover_time) {
                gpsdo_state.stats.max_holdover_time = holdover_duration;
            }

            gpsdo_set_mode(GPSDO_MODE_ACQUIRING);
        }
        break;
    }
}

void gpsdo_get_status(gpsdo_status_t *status)
{
    if (!status || !gpsdo_state.initialized) {
        return;
    }

    status->mode = gpsdo_state.mode;
    status->phase_error_ns = gpsdo_read_phase_error();
    status->dac_value = gpsdo_read_dac_value();
    status->pps_count = READ_REG(GPSDO_PPS_COUNT);
    status->locked = gpsdo_is_locked();
    status->tow_valid = gpsdo_is_tow_valid();
    status->time_in_mode =
        gpsdo_state.current_time - gpsdo_state.mode_start_time;
    status->lock_count = gpsdo_state.stats.lock_count;
}

void gpsdo_get_statistics(gpsdo_stats_t *stats)
{
    if (!stats || !gpsdo_state.initialized) {
        return;
    }

    *stats = gpsdo_state.stats;
}

void gpsdo_reset_statistics(void)
{
    memset(&gpsdo_state.stats, 0, sizeof(gpsdo_stats_t));
    gpsdo_state.stats.min_phase_error = INT32_MAX;
    gpsdo_state.stats.max_phase_error = INT32_MIN;
}

void gpsdo_set_config(const gpsdo_config_t *config)
{
    if (!config || !gpsdo_state.initialized) {
        return;
    }

    gpsdo_state.config = *config;

    /* Update hardware */
    WRITE_REG(GPSDO_KP_SHIFT, config->kp_shift);
    WRITE_REG(GPSDO_KI_SHIFT, config->ki_shift);
}

void gpsdo_get_config(gpsdo_config_t *config)
{
    if (!config || !gpsdo_state.initialized) {
        return;
    }

    *config = gpsdo_state.config;
}

void gpsdo_enable(bool enable)
{
    if (!gpsdo_state.initialized) {
        return;
    }

    uint32_t ctrl = READ_REG(GPSDO_CTRL);

    if (enable) {
        ctrl |= GPSDO_CTRL_ENABLE;
        gpsdo_set_mode(GPSDO_MODE_ACQUIRING);
    } else {
        ctrl &= ~GPSDO_CTRL_ENABLE;
        gpsdo_set_mode(GPSDO_MODE_DISABLED);
    }

    WRITE_REG(GPSDO_CTRL, ctrl);
}

void gpsdo_set_manual_dac(uint16_t value)
{
    WRITE_REG(GPSDO_DAC_MANUAL, value);
}

void gpsdo_set_manual_mode(bool manual)
{
    uint32_t ctrl = READ_REG(GPSDO_CTRL);

    if (manual) {
        ctrl |= GPSDO_CTRL_MANUAL_MODE;
    } else {
        ctrl &= ~GPSDO_CTRL_MANUAL_MODE;
    }

    WRITE_REG(GPSDO_CTRL, ctrl);
}

void gpsdo_reset_integrator(void)
{
    uint32_t ctrl = READ_REG(GPSDO_CTRL);

    /* Pulse reset bit */
    WRITE_REG(GPSDO_CTRL, ctrl | GPSDO_CTRL_RESET_INT);
    WRITE_REG(GPSDO_CTRL, ctrl & ~GPSDO_CTRL_RESET_INT);
}

void gpsdo_print_status(void)
{
    gpsdo_status_t status;
    gpsdo_get_status(&status);

    printf("\n");
    printf("============================================================\n");
    printf("                    GPSDO STATUS\n");
    printf("============================================================\n");

    const char *mode_str[] = {
        "Disabled",
        "Acquiring",
        "Disciplining",
        "Locked",
        "Holdover"
    };

    printf("Mode:          %s\n", mode_str[status.mode]);
    printf("Time in mode:  %u seconds\n", status.time_in_mode);
    printf("Phase error:   %d ns\n", status.phase_error_ns);
    printf("DAC value:     %u (0x%04X)\n", status.dac_value, status.dac_value);
    printf("PPS count:     %u\n", status.pps_count);
    printf("Locked:        %s\n", status.locked ? "Yes" : "No");
    printf("GPS TOW valid: %s\n", status.tow_valid ? "Yes" : "No");
    printf("Lock count:    %u\n", status.lock_count);
    printf("============================================================\n");
}

void gpsdo_print_statistics(void)
{
    gpsdo_stats_t stats;
    gpsdo_get_statistics(&stats);

    printf("\n");
    printf("============================================================\n");
    printf("                  GPSDO STATISTICS\n");
    printf("============================================================\n");
    printf("Phase Error:\n");
    printf("  Min:     %d ns\n", stats.min_phase_error);
    printf("  Max:     %d ns\n", stats.max_phase_error);
    printf("  Average: %d ns\n", stats.avg_phase_error);
    printf("\n");
    printf("Performance:\n");
    printf("  Total lock time:    %u seconds\n", stats.lock_time);
    printf("  Holdover events:    %u\n", stats.holdover_events);
    printf("  Max holdover time:  %u seconds\n", stats.max_holdover_time);
    printf("============================================================\n");
}
