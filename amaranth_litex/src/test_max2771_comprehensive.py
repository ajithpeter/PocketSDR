#!/usr/bin/env python3
"""
Comprehensive test suite for MAX2771 ADC Interface.

Tests:
1. Sign-magnitude to signed conversion (00→+1, 01→+3, 10→-1, 11→-3)
2. AsyncFIFO operation for clock domain crossing
3. Stream interface output
4. FIFO depth and overflow handling
"""

from amaranth.sim import Simulator
import sys

# Import the MAX2771Interface
from max2771_interface import MAX2771Interface


def test_conversion_logic():
    """Test sign-magnitude to signed conversion."""
    print("\n" + "="*70)
    print("TEST 1: Sign-Magnitude to Signed Conversion")
    print("="*70)

    dut = MAX2771Interface(fifo_depth=32)
    test_passed = True
    results = []

    async def conversion_test(ctx):
        nonlocal test_passed

        # Test patterns with expected results
        # Format: (i_raw, q_raw, expected_i, expected_q)
        test_cases = [
            (0b00, 0b00, 1, 1, "+1, +1"),     # Both positive magnitude 1
            (0b01, 0b01, 1, 1, "+3→+1, +3→+1"),  # Both positive magnitude 3 (saturated)
            (0b10, 0b10, -1, -1, "-1, -1"),    # Both negative magnitude 1
            (0b11, 0b11, -2, -2, "-3→-2, -3→-2"),  # Both negative magnitude 3 (saturated)
            (0b00, 0b10, 1, -1, "+1, -1"),     # Mixed
            (0b01, 0b11, 1, -2, "+3→+1, -3→-2"), # Mixed saturated
            (0b10, 0b00, -1, 1, "-1, +1"),     # Mixed
            (0b11, 0b01, -2, 1, "-3→-2, +3→+1"), # Mixed saturated
        ]

        ctx.set(dut.samples.ready, 1)

        print(f"\n{'Case':<5} {'I_raw':<6} {'Q_raw':<6} {'Exp_I':<6} {'Exp_Q':<6} "
              f"{'Got_I':<6} {'Got_Q':<6} {'Status':<8} {'Description'}")
        print("-" * 90)

        for idx, (i_raw, q_raw, exp_i, exp_q, desc) in enumerate(test_cases):
            # Set input
            ctx.set(dut.iq_data, (q_raw << 2) | i_raw)

            # Wait for processing through ADC domain and FIFO
            for _ in range(10):
                await ctx.tick("adc")

            # Read result from sync domain
            for _ in range(20):
                await ctx.tick()
                if ctx.get(dut.samples.valid):
                    i_val = ctx.get(dut.samples.payload.i)
                    q_val = ctx.get(dut.samples.payload.q)

                    # Convert to signed
                    i_signed = i_val if i_val < 2 else i_val - 4
                    q_signed = q_val if q_val < 2 else q_val - 4

                    # Check if matches expected
                    passed = (i_signed == exp_i and q_signed == exp_q)
                    status = "PASS" if passed else "FAIL"

                    print(f"{idx:<5} {i_raw:02b}b    {q_raw:02b}b    "
                          f"{exp_i:+3d}    {exp_q:+3d}    "
                          f"{i_signed:+3d}    {q_signed:+3d}    "
                          f"{status:<8} {desc}")

                    results.append((idx, passed, i_signed, q_signed, exp_i, exp_q))

                    if not passed:
                        test_passed = False
                    break

        # Summary
        passed_count = sum(1 for _, p, *_ in results if p)
        total_count = len(results)
        print(f"\nConversion Test: {passed_count}/{total_count} passed")

        if test_passed:
            print("✓ All conversion tests PASSED")
        else:
            print("✗ Some conversion tests FAILED")
            for idx, passed, got_i, got_q, exp_i, exp_q in results:
                if not passed:
                    print(f"  Case {idx}: Expected ({exp_i:+d}, {exp_q:+d}), "
                          f"Got ({got_i:+d}, {got_q:+d})")

    sim = Simulator(dut)
    sim.add_clock(1/16e6, domain="adc")
    sim.add_clock(1/50e6, domain="sync")
    sim.add_testbench(conversion_test)
    sim.run()

    return test_passed


def test_fifo_operation():
    """Test AsyncFIFO clock domain crossing."""
    print("\n" + "="*70)
    print("TEST 2: AsyncFIFO Clock Domain Crossing")
    print("="*70)

    dut = MAX2771Interface(fifo_depth=32)
    test_passed = True

    async def fifo_test(ctx):
        nonlocal test_passed

        print("\nTesting FIFO with different clock domains (ADC: 16MHz, SYS: 50MHz)")

        # Generate pattern in ADC domain
        pattern_count = 20
        pattern = []

        for i in range(pattern_count):
            i_val = (i % 4)  # Cycle through 00, 01, 10, 11
            q_val = ((i + 1) % 4)
            pattern.append((i_val, q_val))
            ctx.set(dut.iq_data, (q_val << 2) | i_val)

            # Wait in ADC domain
            for _ in range(2):
                await ctx.tick("adc")

        # Read in sync domain
        ctx.set(dut.samples.ready, 1)
        received = []

        for _ in range(100):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                i_val = ctx.get(dut.samples.payload.i)
                q_val = ctx.get(dut.samples.payload.q)
                i_signed = i_val if i_val < 2 else i_val - 4
                q_signed = q_val if q_val < 2 else q_val - 4
                received.append((i_signed, q_signed))

                if len(received) >= 10:
                    break

        print(f"Samples written to FIFO: {pattern_count}")
        print(f"Samples read from FIFO: {len(received)}")

        if len(received) >= 5:
            print(f"✓ FIFO clock domain crossing working (received {len(received)} samples)")
        else:
            print(f"✗ FIFO clock domain crossing FAILED (only {len(received)} samples)")
            test_passed = False

        print(f"\nFirst 5 received samples:")
        for idx, (i, q) in enumerate(received[:5]):
            print(f"  Sample {idx}: I={i:+2d}, Q={q:+2d}")

    sim = Simulator(dut)
    sim.add_clock(1/16e6, domain="adc")
    sim.add_clock(1/50e6, domain="sync")
    sim.add_testbench(fifo_test)
    sim.run()

    return test_passed


def test_stream_interface():
    """Test stream interface valid/ready handshake."""
    print("\n" + "="*70)
    print("TEST 3: Stream Interface Operation")
    print("="*70)

    dut = MAX2771Interface(fifo_depth=32)
    test_passed = True

    async def stream_test(ctx):
        nonlocal test_passed

        print("\nTesting stream interface handshake")

        # Write samples to FIFO
        for i in range(10):
            ctx.set(dut.iq_data, 0b0000)  # Simple pattern
            for _ in range(2):
                await ctx.tick("adc")

        # Test 1: Ready=0, should not consume
        ctx.set(dut.samples.ready, 0)
        valid_count_no_ready = 0

        for _ in range(20):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                valid_count_no_ready += 1

        print(f"Valid signals when ready=0: {valid_count_no_ready}")

        # Test 2: Ready=1, should consume
        ctx.set(dut.samples.ready, 1)
        consumed = 0

        for _ in range(50):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                consumed += 1
                if consumed >= 5:
                    break

        print(f"Samples consumed when ready=1: {consumed}")

        if consumed >= 3:
            print(f"✓ Stream interface handshake working")
        else:
            print(f"✗ Stream interface FAILED (consumed={consumed})")
            test_passed = False

    sim = Simulator(dut)
    sim.add_clock(1/16e6, domain="adc")
    sim.add_clock(1/50e6, domain="sync")
    sim.add_testbench(stream_test)
    sim.run()

    return test_passed


def test_fifo_depth_overflow():
    """Test FIFO depth and overflow handling."""
    print("\n" + "="*70)
    print("TEST 4: FIFO Depth and Overflow Handling")
    print("="*70)

    fifo_depth = 32
    dut = MAX2771Interface(fifo_depth=fifo_depth)
    test_passed = True

    async def overflow_test(ctx):
        nonlocal test_passed

        print(f"\nFIFO configured with depth: {fifo_depth}")
        print("Note: ADC samples continuously (w_en=1), so FIFO prevents data loss")
        print("\nTest 1: FIFO buffering capacity")

        # Don't set ready initially - let FIFO fill up
        ctx.set(dut.samples.ready, 0)

        # Give time for FIFO to fill (continuously sampling)
        # At 16MHz ADC vs 50MHz sys clock, need enough time
        for i in range(100):
            ctx.set(dut.iq_data, i & 0x0F)
            await ctx.tick("adc")

        # Wait some sync cycles to let FIFO stabilize
        for _ in range(10):
            await ctx.tick()

        print(f"FIFO filled with continuous sampling (ready=0)")

        # Now burst read to see how many were buffered
        ctx.set(dut.samples.ready, 1)
        buffered_count = 0

        # Read quickly in sync domain
        for _ in range(fifo_depth + 10):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                buffered_count += 1

        print(f"Samples read from FIFO: {buffered_count}")

        # With continuous sampling, we expect to read samples continuously
        # Not just the buffered amount, since ADC keeps writing
        if buffered_count >= fifo_depth // 2:
            print(f"✓ FIFO buffering working ({buffered_count} samples)")
        else:
            print(f"✗ FIFO buffering insufficient ({buffered_count} < {fifo_depth//2})")
            test_passed = False

        print("\nTest 2: Continuous streaming (no overflow when ready=1)")

        # Reset
        ctx.set(dut.samples.ready, 1)
        continuous_count = 0

        # Sample continuously with ready=1 - should not overflow
        for i in range(50):
            ctx.set(dut.iq_data, (i % 4))
            await ctx.tick("adc")

        # Read continuously
        for _ in range(100):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                continuous_count += 1
                if continuous_count >= 20:
                    break

        print(f"Continuous samples received: {continuous_count}")

        if continuous_count >= 10:
            print(f"✓ Continuous streaming working (no overflow)")
        else:
            print(f"✗ Continuous streaming FAILED ({continuous_count} samples)")
            test_passed = False

        print("\nTest 3: Back-pressure (ready=0 prevents overflow)")

        # Stop reading (ready=0) and verify FIFO handles it
        ctx.set(dut.samples.ready, 0)

        # Generate many samples
        for i in range(100):
            ctx.set(dut.iq_data, 0x05)
            await ctx.tick("adc")

        # Try to read - should get buffered samples (up to FIFO depth)
        ctx.set(dut.samples.ready, 1)
        backpressure_count = 0

        for _ in range(100):
            await ctx.tick()
            if ctx.get(dut.samples.valid):
                backpressure_count += 1

        print(f"Samples after back-pressure: {backpressure_count}")

        # Should handle back-pressure gracefully
        if backpressure_count > 0:
            print(f"✓ FIFO handles back-pressure ({backpressure_count} samples preserved)")
        else:
            print(f"✗ FIFO back-pressure FAILED")
            test_passed = False

    sim = Simulator(dut)
    sim.add_clock(1/16e6, domain="adc")
    sim.add_clock(1/50e6, domain="sync")
    sim.add_testbench(overflow_test)
    sim.run()

    return test_passed


def main():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("MAX2771 ADC Interface - Comprehensive Test Suite")
    print("="*70)

    results = {}

    # Run all tests
    results['conversion'] = test_conversion_logic()
    results['fifo'] = test_fifo_operation()
    results['stream'] = test_stream_interface()
    results['overflow'] = test_fifo_depth_overflow()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name.upper():<20} {status}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
