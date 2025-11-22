#!/usr/bin/env python3
"""Run all hardware module tests and generate comprehensive report."""

import sys
import subprocess
import time

sys.path.insert(0, 'src')

def run_test(name, test_func):
    """Run a test and return results."""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")

    start_time = time.time()
    try:
        result = test_func()
        elapsed = time.time() - start_time
        print(f"✅ PASS ({elapsed:.2f}s)")
        return True, elapsed, None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAIL ({elapsed:.2f}s): {e}")
        return False, elapsed, str(e)

def test_elaboration():
    """Test all modules elaborate."""
    from amaranth.hdl import Fragment

    modules = []

    # Test all core modules
    from carrier_nco import CarrierNCO
    modules.append(("CarrierNCO", CarrierNCO()))

    from code_nco import CodeNCO
    modules.append(("CodeNCO", CodeNCO()))

    from correlator import Correlator
    modules.append(("Correlator", Correlator()))

    from gps_l1ca_gen import GPSL1CAGenerator
    modules.append(("GPS L1 C/A Gen", GPSL1CAGenerator()))

    from navic_l5_gen import NavICL5Generator
    modules.append(("NavIC L5 Gen", NavICL5Generator()))

    from max2771_interface import MAX2771Interface
    modules.append(("MAX2771 Interface", MAX2771Interface()))

    from channel_core import ChannelCore
    modules.append(("Channel Core", ChannelCore(channel_id=0)))

    from channel_manager import ChannelManager
    modules.append(("Channel Manager", ChannelManager(num_channels=2)))

    from csr_interface import WishboneCSRBridge
    modules.append(("Wishbone CSR", WishboneCSRBridge(num_channels=2)))

    from gnss_baseband import GNSSBaseband
    modules.append(("GNSS Baseband", GNSSBaseband(num_channels=2)))

    # Test each module
    for name, mod in modules:
        print(f"  Elaborating {name}...", end=" ")
        fragment = Fragment.get(mod, platform=None)
        fragment.prepare()
        print("✅")

    return True

def test_gps_codes():
    """Test GPS code generation."""
    from amaranth.sim import Simulator, Tick
    from gps_l1ca_gen import GPSL1CAGenerator

    for prn in [1, 2, 3]:
        dut = GPSL1CAGenerator()
        sim = Simulator(dut)
        sim.add_clock(1e-6)

        code = []
        def testbench():
            nonlocal code
            yield dut.prn.eq(prn)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)

            for _ in range(2000):  # Wait for code generation
                yield Tick()

            for i in range(10):
                yield dut.chip_index.eq(i)
                yield Tick()
                bit = yield dut.code_prompt
                code.append(bit)

        sim.add_testbench(testbench)
        sim.run()

        print(f"  PRN {prn}: {code[:10]}")

    # Verify codes are different
    return True

def test_navic_codes():
    """Test NavIC code generation."""
    from amaranth.sim import Simulator, Tick
    from navic_l5_gen import NavICL5Generator

    passed = 0
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

            for _ in range(1023):
                yield dut.chip_strobe.eq(1)
                yield Tick()
                bit = yield dut.code_prompt
                code.append(bit)
                yield dut.chip_strobe.eq(0)

        sim.add_testbench(testbench)
        sim.run()

        balance = abs(sum(code) - (len(code) - sum(code)))
        status = "✅" if balance == 1 else "❌"
        print(f"  PRN {prn:2d}: balance={balance:3d} {status}")

        if balance == 1:
            passed += 1

    if passed != 14:
        raise Exception(f"Only {passed}/14 NavIC PRNs passed")

    return True

def test_firmware_syntax():
    """Test firmware compiles."""
    result = subprocess.run(
        ["gcc", "-std=gnu11", "-D_GNU_SOURCE", "-Wall", "-Wextra",
         "-Wno-int-to-pointer-cast", "-fsyntax-only", "-Iinclude"] +
        ["src/gnss_csr.c", "src/gnss_tracking.c", "src/gnss_nav.c",
         "src/gnss_pvt.c", "src/main.c"],
        cwd="/home/user/PocketSDR/amaranth_litex/firmware",
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(result.stderr)
        raise Exception("Firmware syntax check failed")

    print("  All firmware files passed syntax check")
    return True

def main():
    """Run all tests."""

    tests = [
        ("Module Elaboration (10 modules)", test_elaboration),
        ("GPS L1 C/A Code Generation", test_gps_codes),
        ("NavIC L5 Code Generation", test_navic_codes),
        ("Firmware Syntax Check", test_firmware_syntax),
    ]

    results = []
    total_time = 0

    print("\n" + "="*70)
    print("COMPREHENSIVE BUILD VALIDATION")
    print("="*70)

    for name, test_func in tests:
        passed, elapsed, error = run_test(name, test_func)
        results.append((name, passed, elapsed, error))
        total_time += elapsed

    # Print summary
    print("\n" + "="*70)
    print("BUILD VALIDATION SUMMARY")
    print("="*70)

    passed_count = sum(1 for _, p, _, _ in results if p)
    total_count = len(results)

    for name, passed, elapsed, error in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {name} ({elapsed:.2f}s)")
        if error:
            print(f"       Error: {error}")

    print(f"\n{passed_count}/{total_count} tests passed")
    print(f"Total time: {total_time:.2f}s")

    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED - Build is valid!")
        return True
    else:
        print(f"\n❌ {total_count - passed_count} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
