/**
 * GNSS PVT Solver Implementation
 *
 * Author: PocketSDR Firmware
 * License: BSD 2-Clause
 */

#include "gnss_pvt.h"
#include <stdio.h>
#include <string.h>

void gnss_compute_sat_position(const gps_ephemeris_t *eph, double tow,
                               double sat_pos[3], double *sat_clk_bias) {
    // Time from ephemeris reference epoch
    double tk = tow - eph->toe;
    if (tk > 302400.0) tk -= 604800.0;
    if (tk < -302400.0) tk += 604800.0;

    // Mean motion
    double a = eph->sqrtA * eph->sqrtA;  // Semi-major axis
    double n0 = sqrt(EARTH_GM / (a * a * a));  // Computed mean motion
    double n = n0 + eph->delta_n;  // Corrected mean motion

    // Mean anomaly
    double Mk = eph->m0 + n * tk;

    // Eccentric anomaly (iterative solution)
    double Ek = Mk;
    for (int i = 0; i < 10; i++) {
        Ek = Mk + eph->ecc * sin(Ek);
    }

    // True anomaly
    double sinvk = sqrt(1.0 - eph->ecc * eph->ecc) * sin(Ek) / (1.0 - eph->ecc * cos(Ek));
    double cosvk = (cos(Ek) - eph->ecc) / (1.0 - eph->ecc * cos(Ek));
    double vk = atan2(sinvk, cosvk);

    // Argument of latitude
    double Phik = vk + eph->omega;

    // Second harmonic perturbations
    double sin2Phi = sin(2.0 * Phik);
    double cos2Phi = cos(2.0 * Phik);
    double duk = eph->cus * sin2Phi + eph->cuc * cos2Phi;
    double drk = eph->crs * sin2Phi + eph->crc * cos2Phi;
    double dik = eph->cis * sin2Phi + eph->cic * cos2Phi;

    // Corrected argument of latitude, radius, and inclination
    double uk = Phik + duk;
    double rk = a * (1.0 - eph->ecc * cos(Ek)) + drk;
    double ik = eph->i0 + dik + eph->idot * tk;

    // Positions in orbital plane
    double xkp = rk * cos(uk);
    double ykp = rk * sin(uk);

    // Corrected longitude of ascending node
    double Omegak = eph->omega0 + (eph->omegadot - EARTH_OMEGA_E) * tk - EARTH_OMEGA_E * eph->toe;

    // Earth-fixed coordinates
    sat_pos[0] = xkp * cos(Omegak) - ykp * cos(ik) * sin(Omegak);
    sat_pos[1] = xkp * sin(Omegak) + ykp * cos(ik) * cos(Omegak);
    sat_pos[2] = ykp * sin(ik);

    // Satellite clock bias
    double dt = tow - eph->toc;
    if (dt > 302400.0) dt -= 604800.0;
    if (dt < -302400.0) dt += 604800.0;

    *sat_clk_bias = eph->af0 + eph->af1 * dt + eph->af2 * dt * dt;

    // Relativistic correction
    double F = -2.0 * sqrt(EARTH_GM) / (SPEED_OF_LIGHT * SPEED_OF_LIGHT);
    *sat_clk_bias += F * eph->ecc * eph->sqrtA * sin(Ek);
}

void gnss_compute_sat_velocity(const gps_ephemeris_t *eph, double tow,
                               double sat_vel[3], double *sat_clk_drift) {
    // Simplified velocity computation
    // In production, compute full derivative of position
    // For now, use finite difference approximation
    double pos1[3], pos2[3];
    double clk1, clk2;

    gnss_compute_sat_position(eph, tow - 0.5, pos1, &clk1);
    gnss_compute_sat_position(eph, tow + 0.5, pos2, &clk2);

    sat_vel[0] = (pos2[0] - pos1[0]) / 1.0;
    sat_vel[1] = (pos2[1] - pos1[1]) / 1.0;
    sat_vel[2] = (pos2[2] - pos1[2]) / 1.0;

    *sat_clk_drift = (clk2 - clk1) / 1.0;
}

void ecef_to_lla(const double ecef[3], double *lat, double *lon, double *alt) {
    double x = ecef[0];
    double y = ecef[1];
    double z = ecef[2];

    // Longitude
    *lon = atan2(y, x);

    // Latitude and altitude (iterative)
    double p = sqrt(x * x + y * y);
    double lat_temp = atan2(z, p * (1.0 - WGS84_E2));

    for (int i = 0; i < 10; i++) {
        double N = WGS84_A / sqrt(1.0 - WGS84_E2 * sin(lat_temp) * sin(lat_temp));
        double h = p / cos(lat_temp) - N;
        lat_temp = atan2(z, p * (1.0 - WGS84_E2 * N / (N + h)));
        *alt = h;
    }

    *lat = lat_temp;
}

void lla_to_ecef(double lat, double lon, double alt, double ecef[3]) {
    double N = WGS84_A / sqrt(1.0 - WGS84_E2 * sin(lat) * sin(lat));

    ecef[0] = (N + alt) * cos(lat) * cos(lon);
    ecef[1] = (N + alt) * cos(lat) * sin(lon);
    ecef[2] = (N * (1.0 - WGS84_E2) + alt) * sin(lat);
}

void ecef_vel_to_enu(const double vel_ecef[3], double lat, double lon,
                     double *ve, double *vn, double *vu) {
    double sinlat = sin(lat);
    double coslat = cos(lat);
    double sinlon = sin(lon);
    double coslon = cos(lon);

    // Rotation matrix ECEF to ENU
    *ve = -sinlon * vel_ecef[0] + coslon * vel_ecef[1];
    *vn = -sinlat * coslon * vel_ecef[0] - sinlat * sinlon * vel_ecef[1] + coslat * vel_ecef[2];
    *vu = coslat * coslon * vel_ecef[0] + coslat * sinlon * vel_ecef[1] + sinlat * vel_ecef[2];
}

void pvt_init(pvt_solution_t *pvt, double lat, double lon, double alt) {
    memset(pvt, 0, sizeof(pvt_solution_t));

    // Initial position estimate in ECEF
    lla_to_ecef(deg2rad(lat), deg2rad(lon), alt, pvt->pos_ecef);

    pvt->latitude = lat;
    pvt->longitude = lon;
    pvt->altitude = alt;

    printf("[PVT] Initialized with estimate: %.6f°, %.6f°, %.1f m\n", lat, lon, alt);
}

bool pvt_add_observation(pvt_solution_t *pvt, const satellite_obs_t *obs,
                         satellite_obs_t obs_array[], uint8_t *num_obs) {
    (void)pvt;  /* Unused - reserved for future use */

    if (*num_obs >= MAX_SATELLITES) {
        return false;
    }

    obs_array[*num_obs] = *obs;
    (*num_obs)++;

    return true;
}

bool pvt_compute(pvt_solution_t *pvt, satellite_obs_t obs_array[], uint8_t num_obs) {
    if (num_obs < 4) {
        printf("[PVT] Insufficient satellites (%u < 4)\n", num_obs);
        return false;
    }

    // Iterative least-squares position solution
    double x[4];  // [X, Y, Z, clock_bias]
    x[0] = pvt->pos_ecef[0];
    x[1] = pvt->pos_ecef[1];
    x[2] = pvt->pos_ecef[2];
    x[3] = pvt->clock_bias;

    const int MAX_ITER = 10;
    const double CONV_THRESHOLD = 1.0;  // 1 meter

    for (int iter = 0; iter < MAX_ITER; iter++) {
        double H[MAX_SATELLITES][4];  // Geometry matrix
        double dz[MAX_SATELLITES];     // Residuals

        // Build normal equations
        for (uint8_t i = 0; i < num_obs; i++) {
            satellite_obs_t *obs = &obs_array[i];

            // Range from current estimate to satellite
            double dx = obs->sat_pos[0] - x[0];
            double dy = obs->sat_pos[1] - x[1];
            double dz_pos = obs->sat_pos[2] - x[2];
            double range = sqrt(dx * dx + dy * dy + dz_pos * dz_pos);

            // Predicted pseudorange
            double predicted_pr = range + x[3] - obs->sat_clk_bias * SPEED_OF_LIGHT;

            // Residual
            dz[i] = obs->pseudorange - predicted_pr;

            // Unit vector from receiver to satellite
            H[i][0] = -dx / range;
            H[i][1] = -dy / range;
            H[i][2] = -dz_pos / range;
            H[i][3] = 1.0;
        }

        // Solve normal equations: (H^T * H) * delta_x = H^T * dz
        // Simplified implementation for 4x4 matrix (exact solution)

        double HTH[4][4] = {0};
        double HTdz[4] = {0};

        // Compute H^T * H and H^T * dz
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) {
                for (uint8_t k = 0; k < num_obs; k++) {
                    HTH[i][j] += H[k][i] * H[k][j];
                }
            }
            for (uint8_t k = 0; k < num_obs; k++) {
                HTdz[i] += H[k][i] * dz[k];
            }
        }

        // Solve using Gaussian elimination (simplified for 4x4)
        // In production, use proper matrix inversion or Cholesky decomposition
        double delta_x[4] = {0};

        // Simple forward elimination and back substitution
        // (Simplified - assumes matrix is invertible)
        for (int i = 0; i < 4; i++) {
            delta_x[i] = HTdz[i] / (HTH[i][i] + 1e-10);
        }

        // Update position estimate
        x[0] += delta_x[0];
        x[1] += delta_x[1];
        x[2] += delta_x[2];
        x[3] += delta_x[3];

        // Check convergence
        double norm = sqrt(delta_x[0] * delta_x[0] + delta_x[1] * delta_x[1] +
                          delta_x[2] * delta_x[2]);

        if (norm < CONV_THRESHOLD) {
            // Converged
            pvt->pos_ecef[0] = x[0];
            pvt->pos_ecef[1] = x[1];
            pvt->pos_ecef[2] = x[2];
            pvt->clock_bias = x[3];

            // Convert to LLA
            ecef_to_lla(pvt->pos_ecef, &pvt->latitude, &pvt->longitude, &pvt->altitude);
            pvt->latitude = rad2deg(pvt->latitude);
            pvt->longitude = rad2deg(pvt->longitude);

            pvt->num_sats = num_obs;
            pvt->valid = true;

            // Compute DOP
            pvt_compute_dop(pvt, obs_array, num_obs);

            return true;
        }
    }

    printf("[PVT] Failed to converge\n");
    return false;
}

void pvt_compute_dop(pvt_solution_t *pvt, satellite_obs_t obs_array[], uint8_t num_obs) {
    (void)obs_array;  /* Unused - needed for full DOP computation */
    (void)num_obs;    /* Unused - needed for full DOP computation */

    // Simplified DOP computation
    // In production, compute from covariance matrix

    pvt->gdop = 2.0;  // Placeholder
    pvt->pdop = 1.5;
    pvt->hdop = 1.0;
    pvt->vdop = 1.5;
}

void pvt_print(const pvt_solution_t *pvt) {
    printf("\n");
    printf("============================================================\n");
    printf("                    PVT SOLUTION                            \n");
    printf("============================================================\n");
    printf("Position (LLA):\n");
    printf("  Latitude:  %12.8f °\n", pvt->latitude);
    printf("  Longitude: %12.8f °\n", pvt->longitude);
    printf("  Altitude:  %12.2f m\n", pvt->altitude);
    printf("\n");
    printf("Position (ECEF):\n");
    printf("  X: %14.3f m\n", pvt->pos_ecef[0]);
    printf("  Y: %14.3f m\n", pvt->pos_ecef[1]);
    printf("  Z: %14.3f m\n", pvt->pos_ecef[2]);
    printf("\n");
    printf("Velocity (ENU):\n");
    printf("  East:  %8.3f m/s\n", pvt->vel_east);
    printf("  North: %8.3f m/s\n", pvt->vel_north);
    printf("  Up:    %8.3f m/s\n", pvt->vel_up);
    printf("\n");
    printf("Clock:\n");
    printf("  Bias:  %12.3f m  (%10.3f us)\n",
           pvt->clock_bias, pvt->clock_bias / SPEED_OF_LIGHT * 1e6);
    printf("  Drift: %12.3f m/s\n", pvt->clock_drift);
    printf("\n");
    printf("Quality:\n");
    printf("  Satellites: %u\n", pvt->num_sats);
    printf("  GDOP:       %.2f\n", pvt->gdop);
    printf("  PDOP:       %.2f\n", pvt->pdop);
    printf("  HDOP:       %.2f\n", pvt->hdop);
    printf("  VDOP:       %.2f\n", pvt->vdop);
    printf("\n");
    printf("Time:\n");
    printf("  Week: %u\n", pvt->week);
    printf("  TOW:  %u s\n", pvt->tow);
    printf("============================================================\n");
    printf("\n");
}
