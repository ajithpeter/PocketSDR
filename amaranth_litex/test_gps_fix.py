#!/usr/bin/env python3
"""Quick test to verify GPS L1 C/A generator produces unique codes."""

import sys
sys.path.insert(0, 'src')

from amaranth import *
from amaranth.sim import Simulator, Tick
from gps_l1ca_gen import GPSL1CAGenerator

def test_unique_codes():
    """Test that different PRNs produce different codes."""

    results = {}

    for prn in [1, 2, 3]:
        dut = GPSL1CAGenerator()

        sim = Simulator(dut)
        sim.add_clock(1e-6)  # 1 MHz clock

        code = []
        def wrapped_testbench():
            nonlocal code
            # Reset and set PRN
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            # Wait for code generation (IDLE->INIT_G2->GENERATING->READY)
            # Max delay is 862 chips + 1023 generation + margin
            for _ in range(2000):
                yield Tick()

            # Read first 10 chips
            for i in range(10):
                yield dut.chip_index.eq(i)
                yield Tick()
                bit = yield dut.code_prompt
                code.append(bit)

        sim.add_testbench(wrapped_testbench)

        with sim.write_vcd(f"gps_prn{prn}.vcd"):
            sim.run()
            results[prn] = code

    print("\nGPS L1 C/A Code Generation Test")
    print("=" * 50)

    for prn in [1, 2, 3]:
        code = results[prn]
        balance = sum(code) - (len(code) - sum(code))
        print(f"PRN {prn}: First 10 chips = {code}")
        print(f"         Balance = {balance}")

    # Check if codes are different
    if results[1] == results[2]:
        print("\n❌ FAIL: PRN 1 and PRN 2 generate identical codes!")
        return False
    elif results[2] == results[3]:
        print("\n❌ FAIL: PRN 2 and PRN 3 generate identical codes!")
        return False
    elif results[1] == results[3]:
        print("\n❌ FAIL: PRN 1 and PRN 3 generate identical codes!")
        return False
    else:
        print("\n✅ PASS: All PRNs generate unique codes!")
        return True

if __name__ == "__main__":
    success = test_unique_codes()
    sys.exit(0 if success else 1)
