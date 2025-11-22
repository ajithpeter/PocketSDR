/**
 * GPSDO (GPS Disciplined Oscillator) Control
 *
 * Provides firmware control for the GPSDO hardware module including:
 * - Configuration of PI controller gains
 * - Status monitoring
 * - Holdover mode when GPS unavailable
 * - Oscillator health monitoring
 *
 * Author: PocketSDR GPSDO Firmware
 * License: BSD 2-Clause
 */

#ifndef GPSDO_H
#define GPSDO_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * GPSDO register map (memory-mapped at GPSDO_BASE)
 */
#define GPSDO_BASE          0x50000000

#define GPSDO_CTRL          (GPSDO_BASE + 0x00)  /* Control register */
#define GPSDO_STATUS        (GPSDO_BASE + 0x04)  /* Status register */
#define GPSDO_PHASE_ERROR   (GPSDO_BASE + 0x08)  /* Phase error (ns, signed) */
#define GPSDO_DAC_VALUE     (GPSDO_BASE + 0x0C)  /* Current DAC value */
#define GPSDO_PPS_COUNT     (GPSDO_BASE + 0x10)  /* PPS pulse count */
#define GPSDO_KP_SHIFT      (GPSDO_BASE + 0x14)  /* Proportional gain shift */
#define GPSDO_KI_SHIFT      (GPSDO_BASE + 0x18)  /* Integral gain shift */
#define GPSDO_DAC_MANUAL    (GPSDO_BASE + 0x1C)  /* Manual DAC value */
#define GPSDO_HOLDOVER_DAC  (GPSDO_BASE + 0x20)  /* Holdover DAC value */
#define GPSDO_TOW           (GPSDO_BASE + 0x24)  /* GPS Time of Week (ms) */

/* Control register bits */
#define GPSDO_CTRL_ENABLE           (1 << 0)   /* Enable GPSDO */
#define GPSDO_CTRL_RESET_INT        (1 << 1)   /* Reset integrator */
#define GPSDO_CTRL_MANUAL_MODE      (1 << 2)   /* Manual DAC mode */
#define GPSDO_CTRL_HOLDOVER_MODE    (1 << 3)   /* Holdover mode */

/* Status register bits */
#define GPSDO_STATUS_LOCKED         (1 << 0)   /* PLL locked */
#define GPSDO_STATUS_TOW_VALID      (1 << 1)   /* GPS TOW valid */
#define GPSDO_STATUS_PPS_ACTIVE     (1 << 2)   /* PPS pulse active */

/**
 * GPSDO operating mode
 */
typedef enum {
    GPSDO_MODE_DISABLED,        /* GPSDO disabled */
    GPSDO_MODE_ACQUIRING,       /* Waiting for GPS lock */
    GPSDO_MODE_DISCIPLINING,    /* Actively disciplining oscillator */
    GPSDO_MODE_LOCKED,          /* Phase locked */
    GPSDO_MODE_HOLDOVER         /* GPS lost, using last good DAC value */
} gpsdo_mode_t;

/**
 * GPSDO configuration parameters
 */
typedef struct {
    uint8_t kp_shift;           /* Proportional gain shift (8-16) */
    uint8_t ki_shift;           /* Integral gain shift (16-24) */
    int32_t lock_threshold_ns;  /* Lock threshold in nanoseconds */
    uint32_t holdover_timeout;  /* Holdover timeout in seconds */
} gpsdo_config_t;

/**
 * GPSDO status structure
 */
typedef struct {
    gpsdo_mode_t mode;          /* Current operating mode */
    int32_t phase_error_ns;     /* Phase error in nanoseconds */
    uint16_t dac_value;         /* Current DAC control value */
    uint32_t pps_count;         /* Count of PPS pulses */
    bool locked;                /* PLL lock status */
    bool tow_valid;             /* GPS TOW valid */
    uint32_t time_in_mode;      /* Time spent in current mode (seconds) */
    uint32_t lock_count;        /* Number of times locked */
} gpsdo_status_t;

/**
 * GPSDO statistics
 */
typedef struct {
    int32_t min_phase_error;    /* Minimum phase error seen (ns) */
    int32_t max_phase_error;    /* Maximum phase error seen (ns) */
    int32_t avg_phase_error;    /* Average phase error (ns) */
    uint32_t lock_time;         /* Total time locked (seconds) */
    uint32_t lock_count;        /* Number of times locked */
    uint32_t holdover_events;   /* Number of holdover events */
    uint32_t max_holdover_time; /* Longest holdover duration (seconds) */
} gpsdo_stats_t;

/**
 * Initialize GPSDO with default configuration.
 *
 * @param config  Configuration parameters (NULL for defaults)
 */
void gpsdo_init(const gpsdo_config_t *config);

/**
 * Update GPSDO with new GPS time solution.
 *
 * Called from PVT solver when new position/time available.
 *
 * @param tow_ms      GPS Time of Week in milliseconds
 * @param tow_valid   True if TOW is valid
 */
void gpsdo_update_time(uint32_t tow_ms, bool tow_valid);

/**
 * Get current GPSDO status.
 *
 * @param status  Pointer to status structure to fill
 */
void gpsdo_get_status(gpsdo_status_t *status);

/**
 * Get GPSDO statistics.
 *
 * @param stats  Pointer to statistics structure to fill
 */
void gpsdo_get_statistics(gpsdo_stats_t *stats);

/**
 * Reset GPSDO statistics.
 */
void gpsdo_reset_statistics(void);

/**
 * Set GPSDO configuration.
 *
 * @param config  New configuration parameters
 */
void gpsdo_set_config(const gpsdo_config_t *config);

/**
 * Get current configuration.
 *
 * @param config  Pointer to configuration structure to fill
 */
void gpsdo_get_config(gpsdo_config_t *config);

/**
 * Enable/disable GPSDO.
 *
 * @param enable  True to enable, false to disable
 */
void gpsdo_enable(bool enable);

/**
 * Set manual DAC value.
 *
 * Used for testing or manual frequency adjustment.
 *
 * @param value  DAC value (0-65535)
 */
void gpsdo_set_manual_dac(uint16_t value);

/**
 * Enter/exit manual mode.
 *
 * @param manual  True for manual mode, false for automatic
 */
void gpsdo_set_manual_mode(bool manual);

/**
 * Reset PI controller integrator.
 *
 * Useful when changing modes or after long holdover.
 */
void gpsdo_reset_integrator(void);

/**
 * Periodic update function.
 *
 * Should be called regularly (e.g., 1 Hz) to update state machine
 * and handle holdover transitions.
 */
void gpsdo_periodic_update(void);

/**
 * Print GPSDO status to console.
 */
void gpsdo_print_status(void);

/**
 * Print GPSDO statistics to console.
 */
void gpsdo_print_statistics(void);

/**
 * Default GPSDO configuration
 */
extern const gpsdo_config_t gpsdo_default_config;

#ifdef __cplusplus
}
#endif

#endif /* GPSDO_H */
