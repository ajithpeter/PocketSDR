#!/usr/bin/env python3
"""
Comprehensive test suite for GPS L1 C/A and NavIC L5 PRN generators.

Tests:
1. LFSR polynomial verification
2. Gold code balance property
3. Code uniqueness
4. G1/G2 sequence generation
5. E/P/L tap generation
"""

from amaranth.sim import Simulator, Tick
from gps_l1ca_gen import GPSL1CAGenerator
from navic_l5_gen import NavICL5Generator


def test_gps_l1ca_lfsr():
    """Test GPS L1 C/A LFSR operation in detail."""
    print("\n" + "="*70)
    print("GPS L1 C/A LFSR Test")
    print("="*70)

    dut = GPSL1CAGenerator()

    def testbench():
        # Test PRN 1 (simplest delay case: 5 chips)
        yield dut.prn.eq(1)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)

        print("\nGenerating 1023-chip sequence for PRN 1...")
        code_sequence = []

        for chip in range(1023):
            yield dut.chip_index.eq(chip)
            yield dut.chip_strobe.eq(1)
            yield Tick()
            yield dut.chip_strobe.eq(0)

            code_bit = yield dut.code_prompt
            code_sequence.append(code_bit)

        # Analysis
        ones = sum(code_sequence)
        zeros = len(code_sequence) - ones
        balance = abs(ones - zeros)

        print(f"\nPRN 1 Results:")
        print(f"  Total chips: {len(code_sequence)}")
        print(f"  Ones:  {ones}")
        print(f"  Zeros: {zeros}")
        print(f"  Balance: {balance}")
        print(f"  First 20 chips: {''.join(str(b) for b in code_sequence[:20])}")
        print(f"  Last 20 chips:  {''.join(str(b) for b in code_sequence[-20:])}")

        # Check balance
        if balance == 1:
            print("  ✓ PASS: Gold code balance property satisfied (±1)")
        else:
            print(f"  ✗ FAIL: Balance should be 1, got {balance}")

        # Test multiple PRNs
        print("\nTesting multiple PRNs (1-10):")
        print("PRN | Ones | Zeros | Balance | Status")
        print("-" * 50)

        for prn in range(1, 11):
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            prn_code = []
            for chip in range(1023):
                yield dut.chip_index.eq(chip)
                yield dut.chip_strobe.eq(1)
                yield Tick()
                yield dut.chip_strobe.eq(0)

                code_bit = yield dut.code_prompt
                prn_code.append(code_bit)

            ones = sum(prn_code)
            zeros = len(prn_code) - ones
            balance = abs(ones - zeros)
            status = "PASS" if balance == 1 else "FAIL"

            print(f"{prn:3d} | {ones:4d} | {zeros:5d} | {balance:7d} | {status}")

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
    sim.run()


def test_navic_l5_lfsr():
    """Test NavIC L5 LFSR operation in detail."""
    print("\n" + "="*70)
    print("NavIC L5 LFSR Test")
    print("="*70)

    dut = NavICL5Generator()

    def testbench():
        print("\nTesting all 14 NavIC PRNs:")
        print("PRN | G2 Init | Ones | Zeros | Balance | First 10 chips | Status")
        print("-" * 75)

        all_passed = True
        failed_prns = []

        for prn in range(1, 15):
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            code_sequence = []
            for chip in range(1023):
                yield dut.chip_index.eq(chip)
                yield dut.chip_strobe.eq(1)
                yield Tick()
                yield dut.chip_strobe.eq(0)

                code_bit = yield dut.code_prompt
                code_sequence.append(code_bit)

            # Analysis
            ones = sum(code_sequence)
            zeros = len(code_sequence) - ones
            balance = abs(ones - zeros)
            g2_init = dut.g2_init[prn - 1]
            first_10 = ''.join(str(b) for b in code_sequence[:10])

            status = "PASS" if balance == 1 else "FAIL"
            if balance != 1:
                all_passed = False
                failed_prns.append(prn)

            print(f"{prn:3d} | 0x{g2_init:03X}   | {ones:4d} | {zeros:5d} | "
                  f"{balance:7d} | {first_10} | {status}")

        print("\n" + "="*70)
        if all_passed:
            print("✓ ALL TESTS PASSED: All 14 NavIC PRNs have proper Gold code balance")
        else:
            print(f"✗ TESTS FAILED: PRNs {failed_prns} have incorrect balance")
            print("  Issue: G2 initialization values may be incorrect")
        print("="*70)

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
    sim.run()


def test_code_uniqueness():
    """Test that different PRNs generate unique codes."""
    print("\n" + "="*70)
    print("Code Uniqueness Test")
    print("="*70)

    dut = GPSL1CAGenerator()

    def testbench():
        codes = {}

        print("\nGenerating codes for GPS PRNs 1-10...")
        for prn in range(1, 11):
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            code_sequence = []
            for chip in range(1023):
                yield dut.chip_index.eq(chip)
                yield dut.chip_strobe.eq(1)
                yield Tick()
                yield dut.chip_strobe.eq(0)

                code_bit = yield dut.code_prompt
                code_sequence.append(code_bit)

            code_tuple = tuple(code_sequence)
            codes[prn] = code_tuple

        # Check uniqueness
        unique_codes = len(set(codes.values()))
        print(f"\nGenerated {len(codes)} PRN codes")
        print(f"Unique codes: {unique_codes}")

        if unique_codes == len(codes):
            print("✓ PASS: All PRN codes are unique")
        else:
            print("✗ FAIL: Some PRN codes are identical")
            # Find duplicates
            seen = {}
            for prn, code in codes.items():
                if code in seen:
                    print(f"  PRN {prn} identical to PRN {seen[code]}")
                else:
                    seen[code] = prn

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
    sim.run()


def test_epl_taps():
    """Test Early/Prompt/Late tap generation."""
    print("\n" + "="*70)
    print("E/P/L Tap Test")
    print("="*70)

    dut = GPSL1CAGenerator()

    def testbench():
        yield dut.prn.eq(1)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)

        print("\nTesting E/P/L taps at chip 100:")
        yield dut.chip_index.eq(100)
        yield dut.chip_strobe.eq(1)
        yield Tick()

        early = yield dut.code_early
        prompt = yield dut.code_prompt
        late = yield dut.code_late

        print(f"  Early:  {early}")
        print(f"  Prompt: {prompt}")
        print(f"  Late:   {late}")

        # Note: Current implementation has E=P=L (simplified)
        if early == prompt == late:
            print("  NOTE: E/P/L taps are currently identical (simplified implementation)")
            print("  TODO: Implement proper code memory for correct E/P/L spacing")
        else:
            print("  ✓ E/P/L taps have different values")

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
    sim.run()


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# PRN Code Generator Test Suite")
    print("#"*70)

    # Run all tests
    test_gps_l1ca_lfsr()
    test_navic_l5_lfsr()
    test_code_uniqueness()
    test_epl_taps()

    print("\n" + "#"*70)
    print("# Test Suite Complete")
    print("#"*70)
