#!/usr/bin/env python3
"""
Verify LFSR operation for GPS Gold code generation.

Reference implementation to validate hardware design.
"""


def lfsr_g1(state):
    """
    GPS L1 C/A G1 LFSR.
    Polynomial: x^10 + x^3 + 1
    Feedback taps: bit 10 and bit 3 (indices 9 and 2 in 0-indexed)

    Hardware uses MSB (bit 9) as output, shifts left, feedback to LSB.
    """
    feedback = ((state >> 9) ^ (state >> 2)) & 1
    output = (state >> 9) & 1  # MSB is output (matches hardware)
    state = ((state << 1) | feedback) & 0x3FF  # Shift left, feedback to bit 0
    return state, output


def lfsr_g2(state):
    """
    GPS L1 C/A G2 LFSR.
    Polynomial: x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1
    Feedback taps: bits 10,9,8,6,3,2 (indices 9,8,7,5,2,1)

    Hardware uses MSB (bit 9) as output, shifts left, feedback to LSB.
    """
    feedback = ((state >> 9) ^ (state >> 8) ^ (state >> 7) ^
                (state >> 5) ^ (state >> 2) ^ (state >> 1)) & 1
    output = (state >> 9) & 1  # MSB is output (matches hardware)
    state = ((state << 1) | feedback) & 0x3FF  # Shift left, feedback to bit 0
    return state, output


def generate_gps_code_reference(prn=1):
    """
    Generate GPS L1 C/A Gold code using reference implementation.
    Uses phase selection (G2 delay table).
    """
    # G2 delay table (phase selection) for GPS PRNs
    g2_delay = [
        5, 6, 7, 8, 17, 18, 139, 140, 141, 251,
        252, 254, 255, 256, 257, 258, 469, 470, 471,
        472, 473, 474, 509, 512, 513, 514, 515, 516,
        859, 860, 861, 862
    ]

    if prn < 1 or prn > 32:
        raise ValueError(f"PRN must be 1-32, got {prn}")

    delay = g2_delay[prn - 1]

    # Initialize both LFSRs to all ones
    g1_state = 0x3FF
    g2_state = 0x3FF

    # Generate G1 sequence
    g1_sequence = []
    g1_temp = g1_state
    for _ in range(1023):
        g1_temp, output = lfsr_g1(g1_temp)
        g1_sequence.append(output)

    # Generate G2 sequence
    g2_sequence = []
    g2_temp = g2_state
    for _ in range(1023):
        g2_temp, output = lfsr_g2(g2_temp)
        g2_sequence.append(output)

    # Apply delay (phase shift) to G2 and XOR with G1
    code = []
    for i in range(1023):
        g2_index = (i + delay) % 1023
        code.append(g1_sequence[i] ^ g2_sequence[g2_index])

    return code


def generate_navic_code_reference(prn=1):
    """
    Generate NavIC L5 code using reference implementation.
    Uses G2 initial state selection.
    """
    g2_init = [
        0x0C8,  # PRN 1
        0x019,  # PRN 2
        0x040,  # PRN 3
        0x0B4,  # PRN 4
        0x175,  # PRN 5
        0x1D6,  # PRN 6
        0x237,  # PRN 7
        0x2F8,  # PRN 8
        0x0D1,  # PRN 9
        0x132,  # PRN 10
        0x193,  # PRN 11
        0x0ED,  # PRN 12
        0x14E,  # PRN 13
        0x1AF,  # PRN 14
    ]

    if prn < 1 or prn > 14:
        raise ValueError(f"PRN must be 1-14, got {prn}")

    # Initialize LFSRs
    g1_state = 0x3FF
    g2_state = g2_init[prn - 1]

    # Generate code by advancing both LFSRs and XORing outputs
    code = []
    for _ in range(1023):
        g1_state, g1_out = lfsr_g1(g1_state)
        g2_state, g2_out = lfsr_g2(g2_state)
        code.append(g1_out ^ g2_out)

    return code


def verify_gold_properties(code, prn_name):
    """Verify Gold code properties."""
    ones = sum(code)
    zeros = len(code) - ones
    balance = abs(ones - zeros)

    print(f"\n{prn_name}:")
    print(f"  Length: {len(code)}")
    print(f"  Ones:   {ones}")
    print(f"  Zeros:  {zeros}")
    print(f"  Balance: {balance}")
    print(f"  First 20: {''.join(str(b) for b in code[:20])}")
    print(f"  Status: {'✓ PASS' if balance == 1 else '✗ FAIL'}")

    return balance == 1


if __name__ == "__main__":
    print("="*70)
    print("GPS L1 C/A Gold Code Reference Implementation")
    print("="*70)

    # Test GPS PRNs 1-10
    print("\nGenerating GPS L1 C/A codes using reference implementation:")
    all_passed = True
    for prn in range(1, 11):
        code = generate_gps_code_reference(prn)
        passed = verify_gold_properties(code, f"GPS PRN {prn}")
        all_passed = all_passed and passed

    print("\n" + "="*70)
    print("NavIC L5 Gold Code Reference Implementation")
    print("="*70)

    # Test NavIC PRNs 1-14
    print("\nGenerating NavIC L5 codes using reference implementation:")
    for prn in range(1, 15):
        code = generate_navic_code_reference(prn)
        passed = verify_gold_properties(code, f"NavIC PRN {prn}")
        all_passed = all_passed and passed

    print("\n" + "="*70)
    if all_passed:
        print("✓ All reference codes have proper Gold code balance")
    else:
        print("✗ Some reference codes failed")
    print("="*70)
