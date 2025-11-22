/**
 * GNSS PVT (Position, Velocity, Time) Solver
 *
 * Computes user position, velocity, and time from:
 * - Pseudoranges (code phase measurements)
 * - Carrier Doppler measurements
 * - Satellite ephemeris
 *
 * Uses iterative least-squares algorithm.
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#ifndef GNSS_PVT_H
#define GNSS_PVT_H

#include "gnss_nav.h"
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* Physical constants */
#define SPEED_OF_LIGHT      299792458.0    // m/s
#define EARTH_GM            3.986005e14    // m^3/s^2 (Earth gravitational constant)
#define EARTH_OMEGA_E       7.2921151467e-5  // rad/s (Earth rotation rate)
#define PI                  3.14159265358979323846

/* WGS-84 Earth model */
#define WGS84_A             6378137.0      // Semi-major axis (m)
#define WGS84_F             (1.0/298.257223563)  // Flattening
#define WGS84_E2            (2.0*WGS84_F - WGS84_F*WGS84_F)  // Eccentricity squared

/* Maximum satellites */
#define MAX_SATELLITES      16

/* Satellite observation */
typedef struct {
    uint8_t prn;                // PRN number
    uint8_t signal_type;        // GPS or NavIC

    /* Measurements */
    double pseudorange;         // Pseudorange (m)
    double carrier_phase;       // Carrier phase (cycles)
    double doppler;             // Doppler frequency (Hz)
    double cn0;                 // C/N0 (dB-Hz)

    /* Satellite position/velocity (ECEF) */
    double sat_pos[3];          // X, Y, Z (m)
    double sat_vel[3];          // Vx, Vy, Vz (m/s)
    double sat_clk_bias;        // Satellite clock bias (s)
    double sat_clk_drift;       // Satellite clock drift (s/s)

    /* Validity */
    bool valid;                 // Observation is valid

} satellite_obs_t;

/* PVT solution */
typedef struct {
    /* Position (ECEF) */
    double pos_ecef[3];         // X, Y, Z (m)

    /* Position (LLA) */
    double latitude;            // Latitude (degrees)
    double longitude;           // Longitude (degrees)
    double altitude;            // Altitude above WGS-84 ellipsoid (m)

    /* Velocity (ECEF) */
    double vel_ecef[3];         // Vx, Vy, Vz (m/s)

    /* Velocity (ENU) */
    double vel_north;           // North velocity (m/s)
    double vel_east;            // East velocity (m/s)
    double vel_up;              // Up velocity (m/s)

    /* Clock */
    double clock_bias;          // Receiver clock bias (m)
    double clock_drift;         // Receiver clock drift (m/s)

    /* Time */
    uint32_t tow;               // GPS time of week (s)
    uint16_t week;              // GPS week number

    /* Quality */
    double gdop;                // Geometric dilution of precision
    double pdop;                // Position dilution of precision
    double hdop;                // Horizontal dilution of precision
    double vdop;                // Vertical dilution of precision
    uint8_t num_sats;           // Number of satellites used

    bool valid;                 // Solution is valid

} pvt_solution_t;

/* === Satellite position computation === */

/**
 * Compute satellite position and clock from ephemeris
 */
void gnss_compute_sat_position(const gps_ephemeris_t *eph, double tow,
                               double sat_pos[3], double *sat_clk_bias);

/**
 * Compute satellite velocity
 */
void gnss_compute_sat_velocity(const gps_ephemeris_t *eph, double tow,
                               double sat_vel[3], double *sat_clk_drift);

/* === Coordinate transformations === */

/**
 * ECEF to LLA (geodetic coordinates)
 */
void ecef_to_lla(const double ecef[3], double *lat, double *lon, double *alt);

/**
 * LLA to ECEF
 */
void lla_to_ecef(double lat, double lon, double alt, double ecef[3]);

/**
 * ECEF velocity to ENU (East-North-Up)
 */
void ecef_vel_to_enu(const double vel_ecef[3], double lat, double lon,
                     double *ve, double *vn, double *vu);

/* === PVT solver === */

/**
 * Initialize PVT solver with initial position estimate
 */
void pvt_init(pvt_solution_t *pvt, double lat, double lon, double alt);

/**
 * Add satellite observation
 */
bool pvt_add_observation(pvt_solution_t *pvt, const satellite_obs_t *obs,
                         satellite_obs_t obs_array[], uint8_t *num_obs);

/**
 * Compute PVT solution using least-squares
 * Returns: true if solution is valid
 */
bool pvt_compute(pvt_solution_t *pvt, satellite_obs_t obs_array[], uint8_t num_obs);

/**
 * Compute DOP (Dilution of Precision)
 */
void pvt_compute_dop(pvt_solution_t *pvt, satellite_obs_t obs_array[], uint8_t num_obs);

/* === Pseudorange calculation === */

/**
 * Calculate pseudorange from code phase
 */
static inline double gnss_calc_pseudorange(double code_phase, uint32_t code_epoch,
                                           uint32_t code_length, double chip_rate) {
    // Total chips = code_epoch * code_length + code_phase
    double total_chips = (double)code_epoch * code_length + code_phase;

    // Pseudorange = chips / chip_rate * speed_of_light
    return (total_chips / chip_rate) * SPEED_OF_LIGHT;
}

/**
 * Calculate Doppler from carrier frequency
 */
static inline double gnss_calc_doppler(double carrier_freq, double carrier_nominal) {
    return carrier_freq - carrier_nominal;
}

/* === Utility functions === */

/**
 * Print PVT solution
 */
void pvt_print(const pvt_solution_t *pvt);

/**
 * Degrees to radians
 */
static inline double deg2rad(double deg) {
    return deg * PI / 180.0;
}

/**
 * Radians to degrees
 */
static inline double rad2deg(double rad) {
    return rad * 180.0 / PI;
}

#endif /* GNSS_PVT_H */
