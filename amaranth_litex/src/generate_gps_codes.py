#!/usr/bin/env python3
"""
Generate correct GPS L1 C/A codes using IS-GPS-200 specification.

This script computes the correct Gold codes for GPS satellites and
generates G2 initialization values or code tables.

Reference: IS-GPS-200 Section 3.3.2.5
"""

def lfsr_g1_step(state):
    """Advance G1 LFSR by one step."""
    # G1: x^10 + x^3 + 1
    # Taps at bits 3 and 10 (or indices 2 and 9 in zero-indexed)
    feedback = ((state >> 2) & 1) ^ ((state >> 9) & 1)
    return ((state >> 1) | (feedback << 9)) & 0x3FF


def lfsr_g2_step(state):
    """Advance G2 LFSR by one step."""
    # G2: x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1
    # Taps at bits 2,3,6,8,9,10 (or indices 1,2,5,7,8,9 in zero-indexed)
    feedback = (((state >> 1) & 1) ^ ((state >> 2) & 1) ^
                ((state >> 5) & 1) ^ ((state >> 7) & 1) ^
                ((state >> 8) & 1) ^ ((state >> 9) & 1))
    return ((state >> 1) | (feedback << 9)) & 0x3FF


def generate_gps_ca_code_delay_method(prn, delay):
    """
    Generate GPS L1 C/A code using delay method.

    This is the simple approach: delay G2 by a fixed amount,
    then generate code as G1[9] XOR G2[9].
    """
    g1 = 0x3FF  # All ones
    g2 = 0x3FF  # All ones

    # Advance G2 by delay chips
    for _ in range(delay):
        g2 = lfsr_g2_step(g2)

    # Generate 1023-chip code
    code = []
    for _ in range(1023):
        # Output: G1[9] XOR G2[9] (MSB of each register)
        code.append(((g1 >> 9) & 1) ^ ((g2 >> 9) & 1))

        # Advance both LFSRs
        g1 = lfsr_g1_step(g1)
        g2 = lfsr_g2_step(g2)

    return code, g2  # Return code and final G2 state for init value


def generate_gps_ca_code_tap_method(prn, tap1, tap2):
    """
    Generate GPS L1 C/A code using tap selection method (IS-GPS-200).

    This is the official IS-GPS-200 method:
    Code = G1[9] XOR (G2[tap1-1] XOR G2[tap2-1])

    Taps are 1-indexed in the spec, so we subtract 1 for zero-indexing.
    """
    g1 = 0x3FF  # All ones
    g2 = 0x3FF  # All ones

    # Generate 1023-chip code
    code = []
    for _ in range(1023):
        # Output: G1[9] XOR (G2[tap1-1] XOR G2[tap2-1])
        g1_out = (g1 >> 9) & 1
        g2_out = ((g2 >> (tap1-1)) & 1) ^ ((g2 >> (tap2-1)) & 1)
        code.append(g1_out ^ g2_out)

        # Advance both LFSRs
        g1 = lfsr_g1_step(g1)
        g2 = lfsr_g2_step(g2)

    return code


# GPS L1 C/A delay table from IS-GPS-200
GPS_DELAYS = [
    5, 6, 7, 8, 17, 18, 139, 140, 141, 251,      # PRN 1-10
    252, 254, 255, 256, 257, 258, 469, 470, 471, # PRN 11-19
    472, 473, 474, 509, 512, 513, 514, 515, 516, # PRN 20-28
    859, 860, 861, 862,                           # PRN 29-32
]

# GPS L1 C/A tap selection table from IS-GPS-200
# Each entry is (tap1, tap2) - these are 1-indexed as in the spec
GPS_TAPS = [
    (2, 6), (3, 7), (4, 8), (5, 9), (1, 9), (2, 10), (1, 8), (2, 9), (3, 10), (2, 3),   # PRN 1-10
    (3, 4), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (1, 4), (2, 5), (3, 6),             # PRN 11-19
    (4, 7), (5, 8), (6, 9), (1, 3), (4, 6), (5, 7), (6, 8), (7, 9), (8, 10),             # PRN 20-28
    (1, 6), (2, 7), (3, 8), (4, 9),                                                      # PRN 29-32
]


def test_both_methods():
    """Test both delay and tap methods and compare results."""
    print("="*80)
    print("GPS L1 C/A Code Generation - Testing Both Methods")
    print("="*80)

    all_match = True
    g2_init_values = []

    for prn in range(1, 33):
        delay = GPS_DELAYS[prn-1]
        tap1, tap2 = GPS_TAPS[prn-1]

        # Generate using both methods
        code_delay, g2_final = generate_gps_ca_code_delay_method(prn, delay)
        code_tap = generate_gps_ca_code_tap_method(prn, tap1, tap2)

        # Compute balance
        ones_delay = sum(code_delay)
        zeros_delay = len(code_delay) - ones_delay
        balance_delay = abs(ones_delay - zeros_delay)

        ones_tap = sum(code_tap)
        zeros_tap = len(code_tap) - ones_tap
        balance_tap = abs(ones_tap - zeros_tap)

        # Check if methods match
        match = (code_delay == code_tap)

        # Compute G2 init value (state after delay advancement)
        g1_init = 0x3FF
        g2_init = 0x3FF
        for _ in range(delay):
            g2_init = lfsr_g2_step(g2_init)

        g2_init_values.append(g2_init)

        status_delay = "✅" if balance_delay == 1 else "❌"
        status_tap = "✅" if balance_tap == 1 else "❌"
        status_match = "✅" if match else "❌"

        print(f"PRN {prn:2d}: Delay={delay:4d}, Taps=({tap1:2d},{tap2:2d}), "
              f"G2_init=0x{g2_init:03X}, "
              f"Balance(delay)={balance_delay} {status_delay}, "
              f"Balance(tap)={balance_tap} {status_tap}, "
              f"Match={status_match}")

        if not match:
            all_match = False
            print(f"  ⚠️ Methods don't match for PRN {prn}!")
            print(f"  First 20 chips (delay): {code_delay[:20]}")
            print(f"  First 20 chips (tap):   {code_tap[:20]}")

    print("\n" + "="*80)
    if all_match:
        print("✅ Both methods produce identical codes for all PRNs!")
    else:
        print("❌ Methods produce different codes - need to use tap method!")

    print("\n" + "="*80)
    print("G2 Initialization Values (for delay method):")
    print("="*80)
    print("self.g2_init = [")
    for i in range(0, 32, 8):
        values = [f"0x{g2_init_values[j]:03X}" for j in range(i, min(i+8, 32))]
        comment = f"# PRN {i+1}-{min(i+8, 32)}"
        print(f"    {', '.join(values)}, {comment}")
    print("]")

    return all_match, g2_init_values


if __name__ == "__main__":
    match, g2_inits = test_both_methods()

    print("\n" + "="*80)
    print("Summary:")
    print("="*80)
    print(f"Methods match: {match}")
    print(f"Generated {len(g2_inits)} G2 initialization values")
    print("\nRecommendation:")
    if match:
        print("Use delay method with G2 initialization table (simpler, less logic)")
    else:
        print("Must use tap selection method as per IS-GPS-200 specification")
