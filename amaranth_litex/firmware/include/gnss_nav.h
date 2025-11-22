/**
 * GNSS Navigation Message Decoders
 *
 * Decodes GPS and NavIC navigation messages to extract:
 * - Ephemeris (satellite orbit parameters)
 * - Clock correction parameters
 * - Time of week (TOW)
 * - Health and accuracy information
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#ifndef GNSS_NAV_H
#define GNSS_NAV_H

#include <stdint.h>
#include <stdbool.h>

/* GPS constants */
#define GPS_SUBFRAME_BITS       300
#define GPS_WORD_BITS           30
#define GPS_PREAMBLE            0x8B  // 10001011 (sync pattern)

/* NavIC constants */
#define NAVIC_SUBFRAME_BITS     292
#define NAVIC_SYNC_PATTERN      0xEB90  // Sync pattern

/* GPS Ephemeris */
typedef struct {
    uint32_t tow;               // Time of week (s)
    uint16_t week;              // GPS week number

    /* Clock parameters */
    double toc;                 // Clock data reference time (s)
    double af0, af1, af2;       // SV clock bias, drift, drift rate

    /* Ephemeris parameters */
    double toe;                 // Ephemeris reference time (s)
    double sqrtA;               // Square root of semi-major axis (m^0.5)
    double ecc;                 // Eccentricity
    double i0;                  // Inclination at reference time (rad)
    double omega0;              // Longitude of ascending node (rad)
    double omega;               // Argument of perigee (rad)
    double m0;                  // Mean anomaly at reference time (rad)
    double delta_n;             // Mean motion difference (rad/s)
    double omegadot;            // Rate of right ascension (rad/s)
    double idot;                // Rate of inclination angle (rad/s)
    double cuc, cus;            // Amplitude of cosine/sine correction terms (rad)
    double crc, crs;            // Amplitude of cosine/sine correction terms (m)
    double cic, cis;            // Amplitude of cosine/sine correction terms (rad)

    /* Health and accuracy */
    uint8_t health;             // Satellite health
    uint8_t ura;                // User range accuracy index
    uint16_t iodc;              // Issue of data, clock
    uint16_t iode;              // Issue of data, ephemeris

    bool valid;                 // Ephemeris is valid
} gps_ephemeris_t;

/* NavIC Ephemeris (simplified) */
typedef struct {
    uint32_t tow;               // Time of week (s)
    uint16_t week;              // Week number

    /* Clock parameters */
    double toc;
    double af0, af1, af2;

    /* Ephemeris parameters (similar to GPS) */
    double toe;
    double sqrtA;
    double ecc;
    double i0;
    double omega0;
    double omega;
    double m0;
    double delta_n;
    double omegadot;
    double idot;
    double cuc, cus;
    double crc, crs;
    double cic, cis;

    uint8_t health;
    bool valid;
} navic_ephemeris_t;

/* GPS Navigation decoder state */
typedef struct {
    uint8_t prn;                // PRN number

    /* Bit/word synchronization */
    uint32_t bit_buffer;        // Incoming bit buffer
    uint8_t bit_count;          // Bits in buffer
    bool bit_sync;              // Bit sync achieved
    bool frame_sync;            // Frame sync achieved

    /* Subframe decoding */
    uint32_t subframe[10];      // Current subframe (10 words)
    uint8_t word_count;         // Words decoded
    uint8_t subframe_id;        // Current subframe ID (1-5)

    /* Ephemeris data */
    gps_ephemeris_t eph;        // Ephemeris
    bool eph_received[5];       // Subframes 1-5 received

} gps_nav_decoder_t;

/* NavIC Navigation decoder state */
typedef struct {
    uint8_t prn;

    /* Synchronization */
    uint32_t bit_buffer;
    uint8_t bit_count;
    bool sync;

    /* Subframe decoding */
    uint32_t subframe[10];
    uint8_t word_count;

    /* Ephemeris */
    navic_ephemeris_t eph;
    bool eph_valid;

} navic_nav_decoder_t;

/* === GPS Navigation === */

/**
 * Initialize GPS navigation decoder
 */
void gps_nav_init(gps_nav_decoder_t *nav, uint8_t prn);

/**
 * Process navigation data bit
 * Returns: true if new ephemeris is available
 */
bool gps_nav_process_bit(gps_nav_decoder_t *nav, int bit);

/**
 * Get GPS ephemeris
 */
bool gps_nav_get_ephemeris(gps_nav_decoder_t *nav, gps_ephemeris_t *eph);

/* === NavIC Navigation === */

/**
 * Initialize NavIC navigation decoder
 */
void navic_nav_init(navic_nav_decoder_t *nav, uint8_t prn);

/**
 * Process navigation data bit
 * Returns: true if new ephemeris is available
 */
bool navic_nav_process_bit(navic_nav_decoder_t *nav, int bit);

/**
 * Get NavIC ephemeris
 */
bool navic_nav_get_ephemeris(navic_nav_decoder_t *nav, navic_ephemeris_t *eph);

/* === Parity checking === */

/**
 * Check GPS word parity
 */
bool gps_check_parity(uint32_t word, uint32_t prev_word);

/**
 * Extract GPS data from word (remove parity bits)
 */
uint32_t gps_extract_data(uint32_t word);

/**
 * Decode GPS subframe
 */
void gps_decode_subframe(gps_nav_decoder_t *nav);

#endif /* GNSS_NAV_H */
