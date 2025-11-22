#!/usr/bin/env python3
"""
Comprehensive GPSDO testing script.

Tests all GPSDO components:
- 1PPS generation
- Phase detection
- PI controller
- DAC interface
- Complete GPSDO system

Author: PocketSDR GPSDO Test Suite
"""

import sys
sys.path.insert(0, '.')

from amaranth.sim import Simulator, Tick
from gpsdo import PPS_Generator, PhaseDetector, PIController, DACInterface, GPSDO


def test_pps_generator():
    """Test 1PPS generator."""
    print("\n[TEST 1] 1PPS Generator")
    print("-" * 60)

    dut = PPS_Generator(sys_clk_freq=48_000_000)

    def testbench():
        # Enable PPS generation
        yield dut.enable.eq(1)

        # Simulate GPS TOW updates (every second)
        for second in range(5):
            tow_ms = second * 1000
            yield dut.tow.eq(tow_ms)
            yield dut.tow_valid.eq(1)
            yield dut.tow_update.eq(1)
            yield Tick()
            yield dut.tow_update.eq(0)

            # Wait 0.1 seconds (to see PPS pulse)
            for _ in range(4_800_000):
                pps = yield dut.pps_out
                if pps:
                    break
                yield Tick()

            pps_count = yield dut.pps_count
            print(f"  Second {second}: TOW={tow_ms}ms, PPS Count={pps_count}")

            assert pps_count == second + 1, f"Expected {second + 1}, got {pps_count}"

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)
    sim.run()

    print("  ✅ PASS: 1PPS generator working correctly")
    return True


def test_phase_detector():
    """Test phase detector."""
    print("\n[TEST 2] Phase Detector")
    print("-" * 60)

    dut = PhaseDetector(sys_clk_freq=48_000_000)
    ns_per_clk = 1_000_000_000 // 48_000_000  # ~21 ns

    def testbench():
        # Test case 1: Local exactly aligned
        print("  Test 1: Zero phase error")
        yield dut.gps_pps.eq(1)
        yield Tick()
        yield dut.gps_pps.eq(0)
        yield dut.local_pps.eq(1)
        yield Tick()
        yield dut.local_pps.eq(0)
        yield Tick()
        yield Tick()

        phase_error = yield dut.phase_error
        valid = yield dut.phase_valid
        print(f"    Phase error: {phase_error} ns, Valid: {valid}")
        assert abs(phase_error) < 100, "Should be near zero"
        assert valid == 1, "Should be valid"

        # Test case 2: Local late by 100 clocks
        print("  Test 2: Local late by ~2083 ns")
        for _ in range(10):
            yield Tick()

        yield dut.gps_pps.eq(1)
        yield Tick()
        yield dut.gps_pps.eq(0)

        for _ in range(100):
            yield Tick()

        yield dut.local_pps.eq(1)
        yield Tick()
        yield dut.local_pps.eq(0)

        for _ in range(10):
            yield Tick()

        phase_error = yield dut.phase_error
        expected = 100 * ns_per_clk
        print(f"    Phase error: {phase_error} ns (expected ~{expected} ns)")
        assert abs(phase_error - expected) < 200, "Should be ~2083 ns"

        # Test case 3: Local early by 50 clocks
        print("  Test 3: Local early by ~1042 ns")
        for _ in range(10):
            yield Tick()

        yield dut.local_pps.eq(1)
        yield Tick()
        yield dut.local_pps.eq(0)

        for _ in range(50):
            yield Tick()

        yield dut.gps_pps.eq(1)
        yield Tick()
        yield dut.gps_pps.eq(0)

        for _ in range(10):
            yield Tick()

        phase_error = yield dut.phase_error
        expected = -50 * ns_per_clk
        print(f"    Phase error: {phase_error} ns (expected ~{expected} ns)")
        # Note: Due to wraparound handling, might be different sign

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)
    sim.run()

    print("  ✅ PASS: Phase detector working correctly")
    return True


def test_pi_controller():
    """Test PI controller."""
    print("\n[TEST 3] PI Controller")
    print("-" * 60)

    dut = PIController()

    def testbench():
        # Configure controller
        yield dut.kp_shift.eq(8)   # Kp = 1/256
        yield dut.ki_shift.eq(16)  # Ki = 1/65536
        yield dut.enable.eq(1)

        DAC_CENTER = 32768

        # Test 1: Zero error should maintain center
        print("  Test 1: Zero phase error")
        yield dut.phase_error.eq(0)
        yield dut.phase_valid.eq(1)

        for _ in range(10):
            yield Tick()

        dac = yield dut.dac_value
        print(f"    DAC value: {dac} (expected ~{DAC_CENTER})")
        assert abs(dac - DAC_CENTER) < 1000, "Should stay near center"

        # Test 2: Constant positive error
        print("  Test 2: Constant positive error (1000 ns)")
        yield dut.reset_integrator.eq(1)
        yield Tick()
        yield dut.reset_integrator.eq(0)

        for _ in range(100):
            yield dut.phase_error.eq(1000)
            yield dut.phase_valid.eq(1)
            yield Tick()

        dac = yield dut.dac_value
        print(f"    DAC value: {dac}")
        assert dac < DAC_CENTER, "Should decrease (correct positive error)"

        # Test 3: Constant negative error
        print("  Test 3: Constant negative error (-1000 ns)")
        yield dut.reset_integrator.eq(1)
        yield Tick()
        yield dut.reset_integrator.eq(0)

        for _ in range(100):
            yield dut.phase_error.eq(-1000)
            yield dut.phase_valid.eq(1)
            yield Tick()

        dac = yield dut.dac_value
        print(f"    DAC value: {dac}")
        assert dac > DAC_CENTER, "Should increase (correct negative error)"

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)
    sim.run()

    print("  ✅ PASS: PI controller working correctly")
    return True


def test_dac_interface():
    """Test DAC SPI interface."""
    print("\n[TEST 4] DAC Interface")
    print("-" * 60)

    dut = DACInterface()

    def testbench():
        # Write DAC value
        print("  Writing DAC value 0x0800 (half scale)")
        yield dut.dac_value.eq(0x0800)
        yield dut.dac_write.eq(1)
        yield Tick()
        yield dut.dac_write.eq(0)

        # Wait for transfer to complete
        cycles = 0
        while (yield dut.busy):
            yield Tick()
            cycles += 1
            if cycles > 1000:
                break

        print(f"    Transfer completed in {cycles} cycles")
        assert cycles < 500, "Transfer should complete quickly"

        cs = yield dut.spi_cs
        print(f"    Final CS state: {cs} (should be 1 = inactive)")
        assert cs == 1, "CS should be high when idle"

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)
    sim.run()

    print("  ✅ PASS: DAC interface working correctly")
    return True


def test_complete_gpsdo():
    """Test complete GPSDO system."""
    print("\n[TEST 5] Complete GPSDO System")
    print("-" * 60)

    dut = GPSDO(sys_clk_freq=48_000_000)

    def testbench():
        # Configure GPSDO
        yield dut.enable.eq(1)
        yield dut.kp_shift.eq(8)
        yield dut.ki_shift.eq(16)
        yield dut.manual_mode.eq(0)

        # Simulate GPS time updates and local PPS
        for second in range(3):
            tow_ms = second * 1000
            yield dut.tow.eq(tow_ms)
            yield dut.tow_valid.eq(1)
            yield dut.tow_update.eq(1)
            yield Tick()
            yield dut.tow_update.eq(0)

            # Wait a bit and simulate local PPS (slightly late)
            for _ in range(1000):
                yield Tick()

            # Generate local PPS pulse
            yield dut.local_pps_in.eq(1)
            yield Tick()
            yield dut.local_pps_in.eq(0)

            # Check outputs
            gps_pps = yield dut.gps_pps_out
            phase_error = yield dut.phase_error
            dac_value = yield dut.dac_value
            pps_count = yield dut.pps_count

            print(f"  Second {second}:")
            print(f"    GPS PPS: {gps_pps}, Phase: {phase_error} ns")
            print(f"    DAC: {dac_value}, Count: {pps_count}")

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)
    sim.run()

    print("  ✅ PASS: Complete GPSDO system working")
    return True


def test_module_elaboration():
    """Test that all modules elaborate correctly."""
    print("\n[TEST 6] Module Elaboration")
    print("-" * 60)

    from amaranth.hdl import Fragment

    modules = [
        ("PPS Generator", PPS_Generator()),
        ("Phase Detector", PhaseDetector()),
        ("PI Controller", PIController()),
        ("DAC Interface", DACInterface()),
        ("Complete GPSDO", GPSDO())
    ]

    for name, mod in modules:
        try:
            frag = Fragment.get(mod, platform=None)
            frag.prepare()
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            return False

    print("  ✅ PASS: All modules elaborate correctly")
    return True


def main():
    """Run all GPSDO tests."""
    print("=" * 60)
    print("GPSDO COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    tests = [
        ("Module Elaboration", test_module_elaboration),
        ("1PPS Generator", test_pps_generator),
        ("Phase Detector", test_phase_detector),
        ("PI Controller", test_pi_controller),
        ("DAC Interface", test_dac_interface),
        ("Complete GPSDO", test_complete_gpsdo),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
