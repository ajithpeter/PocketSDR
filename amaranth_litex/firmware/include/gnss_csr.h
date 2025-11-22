/**
 * GNSS Baseband CSR (Control/Status Register) Interface
 *
 * Register definitions and access functions for Vahya GNSS receiver.
 * Maps to hardware registers implemented in gnss_baseband.py
 *
 * Memory Map:
 * 0x40000000 - 0x40000FFF: Channel 0-11 registers (0x100 per channel)
 * 0x40001000 - 0x400010FF: Global registers
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#ifndef GNSS_CSR_H
#define GNSS_CSR_H

#include <stdint.h>
#include <stdbool.h>

/* Base addresses */
#define GNSS_BASE           0x40000000
#define GNSS_GLOBAL_BASE    0x40001000

/* Number of channels */
#define GNSS_NUM_CHANNELS   8  // Vahya board configuration

/* Channel register offsets (per channel, base + ch*0x100) */
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
#define GNSS_CH_CHIP_COUNT          0x38
#define GNSS_CH_EPOCH_COUNT         0x3C

/* CTRL register bits */
#define GNSS_CTRL_ENABLE            (1 << 0)
#define GNSS_CTRL_RESET             (1 << 1)

/* STATUS register bits */
#define GNSS_STATUS_DUMP_READY      (1 << 0)
#define GNSS_STATUS_CODE_EPOCH      (1 << 1)

/* Signal types */
#define GNSS_SIGNAL_GPS_L1CA        0
#define GNSS_SIGNAL_NAVIC_L5        1

/* Global register offsets */
#define GNSS_GLOBAL_CTRL            0x00
#define GNSS_GLOBAL_STATUS          0x04
#define GNSS_GLOBAL_VERSION         0x08
#define GNSS_GLOBAL_CHANNEL_COUNT   0x0C
#define GNSS_GLOBAL_SAMPLE_COUNT    0x10
#define GNSS_GLOBAL_IRQ_MASK        0x14
#define GNSS_GLOBAL_IRQ_STATUS      0x18

/* Global CTRL bits */
#define GNSS_GLOBAL_ENABLE          (1 << 0)
#define GNSS_GLOBAL_RESET           (1 << 1)
#define GNSS_GLOBAL_SAMPLE_ENABLE   (1 << 2)

/* Constants */
#define GPS_L1CA_CHIP_RATE          1.023e6     // 1.023 Mcps
#define NAVIC_L5_CHIP_RATE          10.23e6     // 10.23 Mcps
#define GPS_L1CA_CODE_LENGTH        1023
#define NAVIC_L5_CODE_LENGTH        1023
#define GNSS_SAMPLE_RATE            16.368e6    // Vahya MAX2771 sample rate

/* NCO frequency word calculation */
#define GNSS_NCO_BITS               32
#define GNSS_FREQ_TO_WORD(freq, fs) ((uint32_t)(((freq) / (fs)) * (1ULL << GNSS_NCO_BITS)))

/* Correlation structure */
typedef struct {
    int32_t e_i;    // Early I
    int32_t e_q;    // Early Q
    int32_t p_i;    // Prompt I
    int32_t p_q;    // Prompt Q
    int32_t l_i;    // Late I
    int32_t l_q;    // Late Q
} gnss_correlation_t;

/* Channel configuration */
typedef struct {
    uint8_t prn;                    // PRN number
    uint8_t signal_type;            // GPS_L1CA or NAVIC_L5
    uint32_t carrier_freq;          // Carrier frequency word
    uint32_t carrier_phase;         // Carrier phase offset
    uint32_t code_freq;             // Code frequency word
    uint16_t integration_time;      // Integration period (samples)
    bool enabled;                   // Channel enabled
} gnss_channel_config_t;

/* Channel status */
typedef struct {
    bool dump_ready;                // Correlation dump available
    bool code_epoch;                // Code epoch occurred
    uint16_t chip_count;            // Current chip index
    uint32_t epoch_count;           // Total epochs
    gnss_correlation_t corr;        // Correlation results
} gnss_channel_status_t;

/* === Low-level register access === */

static inline uint32_t gnss_read_reg(uint32_t addr) {
    return *(volatile uint32_t *)addr;
}

static inline void gnss_write_reg(uint32_t addr, uint32_t val) {
    *(volatile uint32_t *)addr = val;
}

static inline uint32_t gnss_channel_base(uint8_t ch) {
    return GNSS_BASE + (ch * 0x100);
}

/* === Channel register access === */

static inline void gnss_channel_enable(uint8_t ch, bool enable) {
    uint32_t base = gnss_channel_base(ch);
    uint32_t ctrl = gnss_read_reg(base + GNSS_CH_CTRL);
    if (enable)
        ctrl |= GNSS_CTRL_ENABLE;
    else
        ctrl &= ~GNSS_CTRL_ENABLE;
    gnss_write_reg(base + GNSS_CH_CTRL, ctrl);
}

static inline void gnss_channel_reset(uint8_t ch) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_CTRL, GNSS_CTRL_RESET);
}

static inline void gnss_channel_set_carrier_freq(uint8_t ch, uint32_t freq_word) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_CARRIER_FREQ, freq_word);
}

static inline void gnss_channel_set_carrier_phase(uint8_t ch, uint32_t phase) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_CARRIER_PHASE, phase);
}

static inline void gnss_channel_set_code_freq(uint8_t ch, uint32_t freq_word) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_CODE_FREQ, freq_word);
}

static inline void gnss_channel_set_signal_type(uint8_t ch, uint8_t type) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_SIGNAL_TYPE, type);
}

static inline void gnss_channel_set_prn(uint8_t ch, uint8_t prn) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_PRN, prn);
}

static inline void gnss_channel_set_integration_time(uint8_t ch, uint16_t samples) {
    uint32_t base = gnss_channel_base(ch);
    gnss_write_reg(base + GNSS_CH_INTEGRATION_TIME, samples);
}

static inline uint32_t gnss_channel_get_status(uint8_t ch) {
    uint32_t base = gnss_channel_base(ch);
    return gnss_read_reg(base + GNSS_CH_STATUS);
}

static inline void gnss_channel_read_correlation(uint8_t ch, gnss_correlation_t *corr) {
    uint32_t base = gnss_channel_base(ch);
    corr->e_i = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_E_I);
    corr->e_q = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_E_Q);
    corr->p_i = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_P_I);
    corr->p_q = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_P_Q);
    corr->l_i = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_L_I);
    corr->l_q = (int32_t)gnss_read_reg(base + GNSS_CH_CORR_L_Q);
}

static inline uint16_t gnss_channel_get_chip_count(uint8_t ch) {
    uint32_t base = gnss_channel_base(ch);
    return (uint16_t)gnss_read_reg(base + GNSS_CH_CHIP_COUNT);
}

static inline uint32_t gnss_channel_get_epoch_count(uint8_t ch) {
    uint32_t base = gnss_channel_base(ch);
    return gnss_read_reg(base + GNSS_CH_EPOCH_COUNT);
}

/* === Global register access === */

static inline void gnss_global_enable(bool enable) {
    uint32_t ctrl = gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CTRL);
    if (enable)
        ctrl |= GNSS_GLOBAL_ENABLE;
    else
        ctrl &= ~GNSS_GLOBAL_ENABLE;
    gnss_write_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CTRL, ctrl);
}

static inline void gnss_global_reset(void) {
    gnss_write_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CTRL, GNSS_GLOBAL_RESET);
}

static inline void gnss_sample_enable(bool enable) {
    uint32_t ctrl = gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CTRL);
    if (enable)
        ctrl |= GNSS_GLOBAL_SAMPLE_ENABLE;
    else
        ctrl &= ~GNSS_GLOBAL_SAMPLE_ENABLE;
    gnss_write_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CTRL, ctrl);
}

static inline uint32_t gnss_get_version(void) {
    return gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_VERSION);
}

static inline uint32_t gnss_get_channel_count(void) {
    return gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_CHANNEL_COUNT);
}

static inline uint32_t gnss_get_sample_count(void) {
    return gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_SAMPLE_COUNT);
}

static inline void gnss_set_irq_mask(uint32_t mask) {
    gnss_write_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_IRQ_MASK, mask);
}

static inline uint32_t gnss_get_irq_status(void) {
    return gnss_read_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_IRQ_STATUS);
}

static inline void gnss_clear_irq(uint32_t mask) {
    gnss_write_reg(GNSS_GLOBAL_BASE + GNSS_GLOBAL_IRQ_STATUS, mask);  // W1C
}

/* === High-level API === */

/**
 * Initialize GNSS baseband
 */
void gnss_init(void);

/**
 * Configure channel
 */
void gnss_channel_configure(uint8_t ch, const gnss_channel_config_t *config);

/**
 * Read channel status
 */
void gnss_channel_read_status(uint8_t ch, gnss_channel_status_t *status);

/**
 * Calculate carrier frequency word from Doppler
 */
static inline uint32_t gnss_doppler_to_freq_word(double doppler_hz) {
    return GNSS_FREQ_TO_WORD(doppler_hz, GNSS_SAMPLE_RATE);
}

/**
 * Calculate code frequency word from chip rate
 */
static inline uint32_t gnss_chip_rate_to_freq_word(double chip_rate_hz) {
    return GNSS_FREQ_TO_WORD(chip_rate_hz, GNSS_SAMPLE_RATE);
}

/**
 * Calculate correlation power
 */
static inline double gnss_correlation_power(int32_t i, int32_t q) {
    return (double)i * i + (double)q * q;
}

/**
 * Calculate correlation magnitude
 */
static inline double gnss_correlation_magnitude(int32_t i, int32_t q) {
    double power = gnss_correlation_power(i, q);
    // Simple sqrt approximation (can use hardware sqrt if available)
    double x = power;
    double y = 1.0;
    int iterations = 10;
    for (int n = 0; n < iterations; n++) {
        y = (y + x / y) / 2.0;
    }
    return y;
}

#endif /* GNSS_CSR_H */
