#!/usr/bin/env python3
"""Find correct G2 init value for NavIC PRN 3."""

import sys
sys.path.insert(0, 'src')

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator, Tick

def test_g2_init(g2_init_value):
    """Test a specific G2 init value for PRN 3."""

    class NavICTestGen(wiring.Component):
        prn: In(unsigned(4))
        chip_strobe: In(1)
        reset: In(1)
        code_prompt: Out(1)

        def __init__(self, g2_init):
            super().__init__()
            self.g2_init_val = g2_init

        def elaborate(self, platform):
            m = Module()

            g1 = Signal(10, reset=0x3FF)
            g2 = Signal(10)

            with m.If(self.reset):
                m.d.sync += [
                    g1.eq(0x3FF),
                    g2.eq(self.g2_init_val)
                ]
            with m.Elif(self.chip_strobe):
                g1_fb = g1[2] ^ g1[9]
                m.d.sync += g1.eq(Cat(g1_fb, g1[0:9]))

                g2_fb = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
                m.d.sync += g2.eq(Cat(g2_fb, g2[0:9]))

            m.d.comb += self.code_prompt.eq(g1[9] ^ g2[9])

            return m

    dut = NavICTestGen(g2_init_value)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    code = []
    def testbench():
        nonlocal code
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)

        for _ in range(1023):
            yield dut.chip_strobe.eq(1)
            yield Tick()
            code_bit = yield dut.code_prompt
            code.append(code_bit)
            yield dut.chip_strobe.eq(0)

    sim.add_testbench(testbench)
    sim.run()

    ones = sum(code)
    zeros = len(code) - ones
    balance = abs(ones - zeros)

    return ones, zeros, balance

# Test candidate values
print("Testing G2 init values for NavIC PRN 3")
print("=" * 70)
print(f"{'G2 Init':<12} {'Hex':<8} {'Ones':<8} {'Zeros':<8} {'Balance':<10} {'Status'}")
print("-" * 70)

candidates = [
    0x040,  # Current (wrong)
    0x140,  # Try with high bit
    0x0C0,  # Two adjacent bits
    0x041,  # Two bits (6,0)
    0x048,  # Two bits (6,3)
    0x050,  # Two bits (6,4)
    0x060,  # Two bits (6,5)
    0x0C1,  # Similar to PRN 1 pattern
    0x1C0,  # High bits
    0x240,  # Different bit
]

best_candidate = None
best_balance = 1023

for g2_init in candidates:
    ones, zeros, balance = test_g2_init(g2_init)
    status = "✅ PASS" if balance == 1 else "  "
    print(f"{g2_init:<12} {g2_init:03X}    {ones:<8} {zeros:<8} {balance:<10} {status}")

    if balance < best_balance:
        best_balance = balance
        best_candidate = g2_init

print("=" * 70)

if best_balance == 1:
    print(f"\n✅ Found correct value: 0x{best_candidate:03X}")
else:
    print(f"\n⚠️  Best candidate: 0x{best_candidate:03X} (balance={best_balance})")
    print("\nTrying extended search...")

    # Extended search through all 10-bit values with 2-4 bits set
    for g2_init in range(1, 0x3FF):
        # Only test values with reasonable number of bits set
        bits_set = bin(g2_init).count('1')
        if bits_set < 2 or bits_set > 8:
            continue

        ones, zeros, balance = test_g2_init(g2_init)
        if balance == 1:
            print(f"  Found: 0x{g2_init:03X} (binary: {g2_init:010b})")
            best_candidate = g2_init
            break

    if balance == 1:
        print(f"\n✅ Correct G2 init for PRN 3: 0x{best_candidate:03X}")
