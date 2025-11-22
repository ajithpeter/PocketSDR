#!/usr/bin/env python3
"""Test all 32 GPS L1 C/A PRNs."""

from amaranth.sim import Simulator, Tick
from gps_l1ca_gen import GPSL1CAGenerator

dut = GPSL1CAGenerator()

def testbench():
    """Test all 32 GPS PRNs."""
    pass_count = 0
    fail_count = 0

    for prn in range(1, 33):
        # Reset with new PRN
        yield dut.prn.eq(prn)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)
        yield Tick()

        # Generate full code sequence
        code_sequence = []
        for chip in range(1023):
            yield dut.chip_strobe.eq(1)
            yield Tick()
            code_sequence.append((yield dut.code_prompt))

        # Verify code properties
        ones = sum(code_sequence)
        zeros = len(code_sequence) - ones
        balance = abs(ones - zeros)

        if balance == 1:
            print(f"PRN {prn:2d}: ✅ PASS (ones={ones}, zeros={zeros}, balance={balance})")
            pass_count += 1
        else:
            print(f"PRN {prn:2d}: ❌ FAIL (ones={ones}, zeros={zeros}, balance={balance})")
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Test Results: {pass_count}/32 PASS, {fail_count}/32 FAIL")
    if fail_count == 0:
        print("✅ ALL GPS L1 C/A PRNS PASS!")
    else:
        print(f"❌ {fail_count} PRNs FAILED")
    print(f"{'='*60}")

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(testbench)
sim.run()
