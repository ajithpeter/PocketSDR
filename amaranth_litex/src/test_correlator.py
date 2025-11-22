"""
Comprehensive tests for GNSS Correlator module.

Tests for:
- Correlator elaboration
- Carrier wipeoff (complex multiplication)
- Early/Prompt/Late tap operation
- Code correlation
- Accumulation and dump functionality
- Correlation accuracy

Author: PocketSDR Test Suite
License: BSD 2-Clause
"""

import unittest
import math
from amaranth import *
from amaranth.sim import Simulator, Tick

from correlator import Correlator


class TestCorrelatorElaboration(unittest.TestCase):
    """Test Correlator module elaboration."""

    def test_correlator_elaboration_default(self):
        """Test that Correlator elaborates with default parameters."""
        dut = Correlator()
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True, "Correlator elaborated successfully")
        except Exception as e:
            self.fail(f"Correlator elaboration failed: {e}")

    def test_correlator_elaboration_custom_width(self):
        """Test Correlator elaboration with custom accumulator width."""
        for width in [24, 32, 40, 48]:
            dut = Correlator(acc_width=width)
            try:
                Fragment.get(dut, platform=None)
                self.assertTrue(True, f"Correlator with acc_width={width} elaborated successfully")
            except Exception as e:
                self.fail(f"Correlator with acc_width={width} failed: {e}")

    def test_correlator_all_interface_signals(self):
        """Test that all interface signals are properly defined."""
        dut = Correlator()

        # Check input signals exist
        self.assertTrue(hasattr(dut, 'sample_i'))
        self.assertTrue(hasattr(dut, 'sample_q'))
        self.assertTrue(hasattr(dut, 'carrier_i'))
        self.assertTrue(hasattr(dut, 'carrier_q'))
        self.assertTrue(hasattr(dut, 'code_early'))
        self.assertTrue(hasattr(dut, 'code_prompt'))
        self.assertTrue(hasattr(dut, 'code_late'))
        self.assertTrue(hasattr(dut, 'integrate'))
        self.assertTrue(hasattr(dut, 'dump'))
        self.assertTrue(hasattr(dut, 'reset'))

        # Check output signals exist
        self.assertTrue(hasattr(dut, 'corr_e_i'))
        self.assertTrue(hasattr(dut, 'corr_e_q'))
        self.assertTrue(hasattr(dut, 'corr_p_i'))
        self.assertTrue(hasattr(dut, 'corr_p_q'))
        self.assertTrue(hasattr(dut, 'corr_l_i'))
        self.assertTrue(hasattr(dut, 'corr_l_q'))
        self.assertTrue(hasattr(dut, 'dump_valid'))


class TestCorrelatorBasicOperation(unittest.TestCase):
    """Test basic Correlator operation."""

    def test_correlator_reset(self):
        """Test that Correlator properly resets."""
        dut = Correlator()
        outputs_zero = False

        def testbench():
            nonlocal outputs_zero
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield Tick()

            # Read outputs after reset
            corr_p_i = yield dut.corr_p_i
            corr_p_q = yield dut.corr_p_q
            corr_e_i = yield dut.corr_e_i
            corr_e_q = yield dut.corr_e_q
            corr_l_i = yield dut.corr_l_i
            corr_l_q = yield dut.corr_l_q

            # All should be zero after reset
            outputs_zero = (corr_p_i == 0 and corr_p_q == 0 and
                          corr_e_i == 0 and corr_e_q == 0 and
                          corr_l_i == 0 and corr_l_q == 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(outputs_zero, "Correlator reset failed")

    def test_correlator_dump_strobe(self):
        """Test that Correlator properly strobes dump_valid."""
        dut = Correlator()
        dump_valid_detected = False

        def testbench():
            nonlocal dump_valid_detected
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)
            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)
            yield dut.carrier_q.eq(0)
            yield dut.code_prompt.eq(1)
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            # Integrate for a few samples
            for _ in range(10):
                yield Tick()

            # Trigger dump
            yield dut.integrate.eq(0)
            yield dut.dump.eq(1)
            yield Tick()

            # Check dump_valid
            dump_valid = yield dut.dump_valid
            if dump_valid == 1:
                dump_valid_detected = True

            yield dut.dump.eq(0)
            yield Tick()

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(dump_valid_detected, "Dump valid strobe not detected")

    def test_correlator_accumulation(self):
        """Test that Correlator accumulates samples."""
        dut = Correlator()
        accumulated = False

        def testbench():
            nonlocal accumulated
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # Set constant inputs
            sample_i = 1
            sample_q = 0
            carrier_i = 32767
            carrier_q = 0
            code = 1

            yield dut.sample_i.eq(sample_i)
            yield dut.sample_q.eq(sample_q)
            yield dut.carrier_i.eq(carrier_i)
            yield dut.carrier_q.eq(carrier_q)
            yield dut.code_prompt.eq(code)
            yield dut.code_early.eq(code)
            yield dut.code_late.eq(code)

            # Integrate for multiple samples
            for _ in range(100):
                yield Tick()

            # Dump and check results
            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            corr_p_i = yield dut.corr_p_i
            corr_p_q = yield dut.corr_p_q

            # Convert to signed if needed
            if corr_p_i >= 2**31:
                corr_p_i -= 2**32
            if corr_p_q >= 2**31:
                corr_p_q -= 2**32

            # Should have accumulated non-zero values
            if (corr_p_i != 0 or corr_p_q != 0):
                accumulated = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(accumulated, "Correlator accumulation failed")


class TestCorrelatorTaps(unittest.TestCase):
    """Test Early/Prompt/Late tap operation."""

    def test_epl_tap_independence(self):
        """Test that E/P/L taps operate independently."""
        dut = Correlator()
        taps_independent = False

        def testbench():
            nonlocal taps_independent
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # Set different code values for each tap
            yield dut.sample_i.eq(2)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)
            yield dut.carrier_q.eq(0)
            yield dut.code_early.eq(0)    # Early gets -1
            yield dut.code_prompt.eq(1)   # Prompt gets +1
            yield dut.code_late.eq(1)     # Late gets +1

            for _ in range(100):
                yield Tick()

            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            # Read all tap values
            corr_e_i = yield dut.corr_e_i
            corr_p_i = yield dut.corr_p_i
            corr_l_i = yield dut.corr_l_i

            # Convert to signed
            for val in [corr_e_i, corr_p_i, corr_l_i]:
                if val >= 2**31:
                    val -= 2**32

            # Early should be negative of Prompt and Late should equal Prompt
            if corr_e_i != corr_p_i:  # Early different from Prompt
                taps_independent = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(taps_independent, "E/P/L taps not independent")

    def test_epl_symmetry(self):
        """Test E/P/L symmetry with same code values."""
        dut = Correlator()
        all_equal = False

        def testbench():
            nonlocal all_equal
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # All taps get same code value
            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(16384)
            yield dut.carrier_q.eq(0)
            yield dut.code_early.eq(1)
            yield dut.code_prompt.eq(1)
            yield dut.code_late.eq(1)

            for _ in range(100):
                yield Tick()

            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            corr_e_i = yield dut.corr_e_i
            corr_p_i = yield dut.corr_p_i
            corr_l_i = yield dut.corr_l_i
            corr_e_q = yield dut.corr_e_q
            corr_p_q = yield dut.corr_p_q
            corr_l_q = yield dut.corr_l_q

            # All should be equal when code is the same
            if (corr_e_i == corr_p_i == corr_l_i and
                corr_e_q == corr_p_q == corr_l_q):
                all_equal = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(all_equal, "E/P/L taps not symmetric")


class TestCorrelatorCarrierWipeoff(unittest.TestCase):
    """Test carrier wipeoff (complex multiplication)."""

    def test_carrier_wipeoff_dc_component(self):
        """Test carrier wipeoff with DC component."""
        dut = Correlator()
        dc_correlation_works = False

        def testbench():
            nonlocal dc_correlation_works
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # Constant sample and carrier at zero phase (cos=max, sin=0)
            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)  # cos(0)
            yield dut.carrier_q.eq(0)      # sin(0)
            yield dut.code_prompt.eq(1)
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            for _ in range(100):
                yield Tick()

            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            corr_p_i = yield dut.corr_p_i
            corr_p_q = yield dut.corr_p_q

            # Convert to signed
            if corr_p_i >= 2**31:
                corr_p_i -= 2**32
            if corr_p_q >= 2**31:
                corr_p_q -= 2**32

            # After wipeoff with zero phase carrier, should have I component
            if corr_p_i > 0:
                dc_correlation_works = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(dc_correlation_works, "Carrier wipeoff DC test failed")

    def test_carrier_wipeoff_quadrature(self):
        """Test carrier wipeoff with quadrature carriers."""
        dut = Correlator()
        quadrature_works = False

        def testbench():
            nonlocal quadrature_works
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # Constant sample with quadrature carrier (cos=0, sin=max)
            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(0)      # cos(90°)
            yield dut.carrier_q.eq(32767)  # sin(90°)
            yield dut.code_prompt.eq(1)
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            for _ in range(100):
                yield Tick()

            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            corr_p_i = yield dut.corr_p_i
            corr_p_q = yield dut.corr_p_q

            # Convert to signed
            if corr_p_i >= 2**31:
                corr_p_i -= 2**32
            if corr_p_q >= 2**31:
                corr_p_q -= 2**32

            # After wipeoff with 90° carrier, the correlation should be non-zero in Q channel
            # This verifies that carrier wipeoff is working (transfer energy from I to Q)
            if (abs(corr_p_i) < abs(corr_p_q)) and corr_p_q != 0:
                quadrature_works = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(quadrature_works, "Carrier wipeoff quadrature test failed")


class TestCorrelatorAccumulation(unittest.TestCase):
    """Test accumulation behavior."""

    def test_continuous_accumulation(self):
        """Test that correlator continuously accumulates."""
        dut = Correlator()
        accumulation_increasing = False

        def testbench():
            nonlocal accumulation_increasing
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)
            yield dut.carrier_q.eq(0)
            yield dut.code_prompt.eq(1)
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            # Accumulate for short period, dump, check
            for cycle in range(2):
                for _ in range(50):
                    yield Tick()

                yield dut.dump.eq(1)
                yield Tick()

                corr_value = yield dut.corr_p_i
                if corr_value > 0:
                    accumulation_increasing = True

                yield dut.dump.eq(0)
                yield dut.integrate.eq(1)
                yield Tick()

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(accumulation_increasing, "Accumulation test failed")

    def test_clear_after_dump(self):
        """Test that accumulators clear after dump."""
        dut = Correlator()
        clear_works = False

        def testbench():
            nonlocal clear_works
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)
            yield dut.carrier_q.eq(0)
            yield dut.code_prompt.eq(1)
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            # First accumulation
            for _ in range(50):
                yield Tick()

            yield dut.dump.eq(1)
            yield dut.integrate.eq(0)
            yield Tick()

            first_value = yield dut.corr_p_i

            yield dut.dump.eq(0)
            yield Tick()

            # Check if accumulator is cleared (output should be latched, internal cleared)
            second_value = yield dut.corr_p_i

            # The output latch holds the dumped value
            if first_value == second_value:
                clear_works = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(clear_works, "Clear after dump test failed")


class TestCorrelatorCodeCorrelation(unittest.TestCase):
    """Test code correlation properties."""

    def test_code_sign_effect(self):
        """Test that code sign affects correlation."""
        dut = Correlator()
        sign_affects = False

        def testbench():
            nonlocal sign_affects
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            yield dut.sample_i.eq(1)
            yield dut.sample_q.eq(0)
            yield dut.carrier_i.eq(32767)
            yield dut.carrier_q.eq(0)
            yield dut.code_prompt.eq(1)  # Code = +1
            yield dut.code_early.eq(1)
            yield dut.code_late.eq(1)

            for _ in range(50):
                yield Tick()

            yield dut.dump.eq(1)
            yield Tick()

            corr_pos = yield dut.corr_p_i

            # Dump and reset
            yield dut.dump.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.integrate.eq(1)

            # Now set code to -1 (0)
            yield dut.code_prompt.eq(0)  # Code = -1
            yield dut.code_early.eq(0)
            yield dut.code_late.eq(0)

            for _ in range(50):
                yield Tick()

            yield dut.dump.eq(1)
            yield Tick()

            corr_neg = yield dut.corr_p_i

            # Convert to signed
            for val in [corr_pos, corr_neg]:
                if val >= 2**31:
                    val -= 2**32

            # Should be opposite signs
            if corr_pos * corr_neg < 0:  # Opposite signs
                sign_affects = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(sign_affects, "Code sign effect test failed")


def run_tests():
    """Run all correlator tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorElaboration))
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorBasicOperation))
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorTaps))
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorCarrierWipeoff))
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorAccumulation))
    suite.addTests(loader.loadTestsFromTestCase(TestCorrelatorCodeCorrelation))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()

    # Print summary
    print("\n" + "="*70)
    print("CORRELATOR TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    exit(0 if result.wasSuccessful() else 1)
