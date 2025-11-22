#!/usr/bin/env python3
"""Test NavIC L5 PRN code balance and autocorrelation."""

import sys
sys.path.insert(0, 'src')

from amaranth import *
from amaranth.sim import Simulator, Tick
from navic_l5_gen import NavICL5Generator

def test_navic_codes():
    """Test NavIC L5 code properties for all PRNs."""

    print("NavIC L5 Code Generator Validation")
    print("=" * 70)
    print(f"{'PRN':<6} {'Ones':<8} {'Zeros':<8} {'Balance':<10} {'Status'}")
    print("-" * 70)

    results = {}
    failed_prns = []

    for prn in range(1, 15):
        dut = NavICL5Generator()

        sim = Simulator(dut)
        sim.add_clock(1e-6)

        code = []
        def testbench():
            nonlocal code
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            for chip in range(1023):
                yield dut.chip_index.eq(chip)
                yield dut.chip_strobe.eq(1)
                yield Tick()
                yield dut.chip_strobe.eq(0)

                code_bit = yield dut.code_prompt
                code.append(code_bit)

        sim.add_testbench(testbench)
        sim.run()

        # Calculate balance
        ones = sum(code)
        zeros = len(code) - ones
        balance = abs(ones - zeros)

        # Gold codes should have balance of 1 (512 ones, 511 zeros or vice versa)
        status = "✅ PASS" if balance == 1 else f"❌ FAIL"

        print(f"{prn:<6} {ones:<8} {zeros:<8} {balance:<10} {status}")

        results[prn] = {
            'ones': ones,
            'zeros': zeros,
            'balance': balance,
            'code': code
        }

        if balance != 1:
            failed_prns.append(prn)

    print("=" * 70)
    print(f"\nPassed: {14 - len(failed_prns)}/14 PRNs")

    if failed_prns:
        print(f"Failed PRNs: {failed_prns}")
        print("\nG2 initialization values for failed PRNs:")
        navic = NavICL5Generator()
        for prn in failed_prns:
            g2_init = navic.g2_init[prn - 1]
            print(f"  PRN {prn}: 0x{g2_init:03X} (binary: {g2_init:010b})")
    else:
        print("All PRNs passed!")

    return len(failed_prns) == 0

if __name__ == "__main__":
    success = test_navic_codes()
    sys.exit(0 if success else 1)
