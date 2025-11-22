/**
 * GNSS Navigation Message Decoders Implementation
 *
 * Simplified implementation focusing on ephemeris extraction
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include "gnss_nav.h"
#include <stdio.h>
#include <string.h>

/* GPS parity check lookup table (simplified) - Reserved for future use */
// static const uint8_t gps_parity_table[6] = {
//     0x3B, 0x1D, 0x2E, 0x17, 0x3A, 0x1D
// };

void gps_nav_init(gps_nav_decoder_t *nav, uint8_t prn) {
    memset(nav, 0, sizeof(gps_nav_decoder_t));
    nav->prn = prn;
    printf("[GPS NAV] Initialized decoder for PRN %u\n", prn);
}

bool gps_check_parity(uint32_t word, uint32_t prev_word) {
    (void)word;      // TODO: Implement proper parity checking
    (void)prev_word; // TODO: Implement proper parity checking

    // Simplified parity check
    // In production, implement full Hamming code parity checking
    // For now, just check that we have reasonable data
    return true;  // TODO: Implement proper parity
}

uint32_t gps_extract_data(uint32_t word) {
    // Remove parity bits (bits 25-30)
    // GPS word: 24 data bits + 6 parity bits
    return (word >> 6) & 0xFFFFFF;
}

void gps_decode_subframe(gps_nav_decoder_t *nav) {
    // Extract TLM and HOW words
    // uint32_t tlm = gps_extract_data(nav->subframe[0]);  // Reserved for future use
    uint32_t how = gps_extract_data(nav->subframe[1]);

    // Subframe ID from HOW
    nav->subframe_id = (how >> 8) & 0x07;

    printf("[GPS NAV] PRN %u: Subframe %u\n", nav->prn, nav->subframe_id);

    // Decode based on subframe ID
    switch (nav->subframe_id) {
        case 1: {
            // Subframe 1: Clock corrections and satellite health
            uint32_t w3 = gps_extract_data(nav->subframe[2]);
            uint32_t w7 = gps_extract_data(nav->subframe[6]);
            uint32_t w8 = gps_extract_data(nav->subframe[7]);
            uint32_t w9 = gps_extract_data(nav->subframe[8]);

            nav->eph.week = (w3 >> 14) & 0x3FF;
            nav->eph.health = (w3 >> 8) & 0x3F;
            nav->eph.ura = (w3 >> 2) & 0x0F;

            // Clock parameters (simplified extraction)
            nav->eph.toc = (double)((w7 >> 6) & 0xFFFF) * 16.0;
            nav->eph.af2 = (int8_t)((w8 >> 16) & 0xFF) * 3.637978807091713e-12;
            nav->eph.af1 = (int16_t)((w8) & 0xFFFF) * 1.818989403545856e-9;
            nav->eph.af0 = (int32_t)((w9 >> 2) & 0x3FFFFF) * 9.094947017729282e-8;

            nav->eph_received[0] = true;
            break;
        }

        case 2: {
            // Subframe 2: Ephemeris part 1
            uint32_t w3 = gps_extract_data(nav->subframe[2]);
            uint32_t w4 = gps_extract_data(nav->subframe[3]);
            uint32_t w5 = gps_extract_data(nav->subframe[4]);
            uint32_t w6 = gps_extract_data(nav->subframe[5]);
            uint32_t w7 = gps_extract_data(nav->subframe[6]);
            uint32_t w8 = gps_extract_data(nav->subframe[7]);
            uint32_t w9 = gps_extract_data(nav->subframe[8]);

            nav->eph.iode = (w3 >> 16) & 0xFF;
            nav->eph.crs = (int16_t)((w3) & 0xFFFF) * 0.0625;
            nav->eph.delta_n = (int16_t)((w4 >> 8) & 0xFFFF) * 5.39093883996156e-11;
            nav->eph.m0 = ((int32_t)(((w4 & 0xFF) << 24) | (w5 >> 0))) * 5.96046447753906e-32;
            nav->eph.cuc = (int16_t)((w6 >> 8) & 0xFFFF) * 2.91038304567337e-7;
            nav->eph.ecc = (double)(((w6 & 0xFF) << 24) | (w7 >> 0)) * 1.19209289550781e-7;
            nav->eph.cus = (int16_t)((w8 >> 8) & 0xFFFF) * 2.91038304567337e-7;
            nav->eph.sqrtA = (double)(((w8 & 0xFF) << 24) | (w9 >> 0)) * 1.90734863281250e-6;

            nav->eph_received[1] = true;
            break;
        }

        case 3: {
            // Subframe 3: Ephemeris part 2
            uint32_t w3 = gps_extract_data(nav->subframe[2]);
            uint32_t w4 = gps_extract_data(nav->subframe[3]);
            uint32_t w5 = gps_extract_data(nav->subframe[4]);
            uint32_t w6 = gps_extract_data(nav->subframe[5]);
            uint32_t w7 = gps_extract_data(nav->subframe[6]);
            uint32_t w8 = gps_extract_data(nav->subframe[7]);
            uint32_t w9 = gps_extract_data(nav->subframe[8]);

            nav->eph.cic = (int16_t)((w3 >> 8) & 0xFFFF) * 2.91038304567337e-7;
            nav->eph.omega0 = ((int32_t)(((w3 & 0xFF) << 24) | (w4 >> 0))) * 5.96046447753906e-32;
            nav->eph.cis = (int16_t)((w5 >> 8) & 0xFFFF) * 2.91038304567337e-7;
            nav->eph.i0 = ((int32_t)(((w5 & 0xFF) << 24) | (w6 >> 0))) * 5.96046447753906e-32;
            nav->eph.crc = (int16_t)((w7 >> 8) & 0xFFFF) * 0.0625;
            nav->eph.omega = ((int32_t)(((w7 & 0xFF) << 24) | (w8 >> 0))) * 5.96046447753906e-32;
            nav->eph.omegadot = (int32_t)w9 * 2.36682230152372e-38;

            nav->eph_received[2] = true;
            break;
        }

        case 4:
        case 5:
            // Subframes 4 and 5: Almanac and other data
            // Not needed for basic PVT
            break;
    }

    // Check if complete ephemeris is received
    if (nav->eph_received[0] && nav->eph_received[1] && nav->eph_received[2]) {
        nav->eph.valid = true;
        printf("[GPS NAV] PRN %u: Ephemeris complete!\n", nav->prn);
    }
}

bool gps_nav_process_bit(gps_nav_decoder_t *nav, int bit) {
    if (bit == 0) return false;  // No bit available

    // Add bit to buffer
    nav->bit_buffer = (nav->bit_buffer << 1) | (bit > 0 ? 1 : 0);
    nav->bit_count++;

    // Search for preamble if not synchronized
    if (!nav->frame_sync) {
        // Look for GPS preamble: 10001011
        uint8_t pattern = nav->bit_buffer & 0xFF;
        if (pattern == GPS_PREAMBLE || pattern == (~GPS_PREAMBLE & 0xFF)) {
            nav->frame_sync = true;
            nav->word_count = 0;
            nav->bit_count = 0;
            printf("[GPS NAV] PRN %u: Frame sync acquired\n", nav->prn);
        }
        return false;
    }

    // Collect 30-bit words
    if (nav->bit_count >= GPS_WORD_BITS) {
        uint32_t word = nav->bit_buffer & 0x3FFFFFFF;

        // Check parity (simplified)
        uint32_t prev_word = (nav->word_count > 0) ? nav->subframe[nav->word_count - 1] : 0;
        if (gps_check_parity(word, prev_word)) {
            nav->subframe[nav->word_count] = word;
            nav->word_count++;

            // If complete subframe (10 words)
            if (nav->word_count >= 10) {
                gps_decode_subframe(nav);
                nav->word_count = 0;

                // Return true if ephemeris is now valid
                if (nav->eph.valid) {
                    return true;
                }
            }
        } else {
            // Parity error - lose sync
            nav->frame_sync = false;
            nav->word_count = 0;
        }

        nav->bit_count = 0;
    }

    return false;
}

bool gps_nav_get_ephemeris(gps_nav_decoder_t *nav, gps_ephemeris_t *eph) {
    if (!nav->eph.valid) return false;
    *eph = nav->eph;
    return true;
}

/* === NavIC Navigation (Simplified) === */

void navic_nav_init(navic_nav_decoder_t *nav, uint8_t prn) {
    memset(nav, 0, sizeof(navic_nav_decoder_t));
    nav->prn = prn;
    printf("[NavIC NAV] Initialized decoder for PRN %u\n", prn);
}

bool navic_nav_process_bit(navic_nav_decoder_t *nav, int bit) {
    if (bit == 0) return false;

    // Simplified NavIC decoder
    // NavIC uses similar structure to GPS but with different parameters
    // For brevity, implement basic synchronization only

    nav->bit_buffer = (nav->bit_buffer << 1) | (bit > 0 ? 1 : 0);
    nav->bit_count++;

    // Search for sync pattern
    if (!nav->sync) {
        uint16_t pattern = nav->bit_buffer & 0xFFFF;
        if (pattern == NAVIC_SYNC_PATTERN) {
            nav->sync = true;
            nav->bit_count = 0;
            printf("[NavIC NAV] PRN %u: Sync acquired\n", nav->prn);
        }
        return false;
    }

    // TODO: Implement full NavIC subframe decoding
    // For now, mark as placeholder

    return false;
}

bool navic_nav_get_ephemeris(navic_nav_decoder_t *nav, navic_ephemeris_t *eph) {
    if (!nav->eph_valid) return false;
    *eph = nav->eph;
    return true;
}
