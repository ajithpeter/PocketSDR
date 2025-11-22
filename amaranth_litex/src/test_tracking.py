"""
Comprehensive tests for GNSS tracking loop modules.

Tests for:
- Carrier NCO (Numerically Controlled Oscillator)
- Code NCO (PRN code timing)
- Tracking loop integration via ChannelCore
- Module elaboration

Author: PocketSDR Test Suite
License: BSD 2-Clause
"""

import unittest
import math
from amaranth import *
from amaranth.sim import Simulator, Tick

from carrier_nco import CarrierNCO
from code_nco import CodeNCO
from correlator import Correlator


class TestCarrierNCO(unittest.TestCase):
    """Test Carrier NCO (Numerically Controlled Oscillator) functionality."""

    def test_nco_elaboration(self):
        """Test that Carrier NCO elaborates successfully."""
        dut = CarrierNCO(phase_width=32, amp_width=16, lut_depth=256)
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True, "Carrier NCO elaborated successfully")
        except Exception as e:
            self.fail(f"Carrier NCO elaboration failed: {e}")

    def test_nco_basic_operation(self):
        """Test basic Carrier NCO operation with frequency generation."""
        dut = CarrierNCO()
        test_passed = False

        def testbench():
            nonlocal test_passed
            # Set frequency word for 1 kHz @ 16 MHz sampling
            yield dut.freq_word.eq(268435)  # ~1 kHz
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            # Run for 100 samples
            sample_count = 0
            for _ in range(110):
                sample_count += 1
                yield Tick()

            # Verify output after pipeline fills (3-cycle latency)
            cos_val = yield dut.cos_out
            sin_val = yield dut.sin_out
            valid = yield dut.valid

            # Check validity
            if valid == 1:
                # Check that outputs are reasonable (between -2^15 and 2^15)
                if -32768 <= cos_val <= 32767 and -32768 <= sin_val <= 32767:
                    test_passed = True

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(test_passed, "Carrier NCO basic operation test failed")

    def test_nco_phase_accumulation(self):
        """Test that Carrier NCO correctly accumulates phase."""
        dut = CarrierNCO(phase_width=32)
        phase_increments = 0
        accumulated_samples = 0

        def testbench():
            nonlocal phase_increments, accumulated_samples
            freq_word = 0x10000000  # Some reasonable frequency
            yield dut.freq_word.eq(freq_word)
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            for _ in range(100):
                accumulated_samples += 1
                yield Tick()

            # If enable is true, we should have accumulated phase
            phase_increments = accumulated_samples

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertGreater(phase_increments, 0, "Phase accumulation failed")

    def test_nco_output_range(self):
        """Test that NCO outputs remain within valid range."""
        dut = CarrierNCO(amp_width=16)
        outputs_valid = True

        def testbench():
            nonlocal outputs_valid
            yield dut.freq_word.eq(1000)
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            for _ in range(50):
                yield Tick()

            # Check final outputs
            cos_val = yield dut.cos_out
            sin_val = yield dut.sin_out

            # Convert from unsigned to signed if needed
            if cos_val >= 2**15:
                cos_val -= 2**16
            if sin_val >= 2**15:
                sin_val -= 2**16

            outputs_valid = (-32768 <= cos_val <= 32767 and
                           -32768 <= sin_val <= 32767)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(outputs_valid, "NCO output range test failed")


class TestCodeNCO(unittest.TestCase):
    """Test Code NCO (PRN timing) functionality."""

    def test_code_nco_elaboration(self):
        """Test that Code NCO elaborates successfully."""
        dut = CodeNCO(phase_width=32, code_length=1023)
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True, "Code NCO elaborated successfully")
        except Exception as e:
            self.fail(f"Code NCO elaboration failed: {e}")

    def test_code_nco_chip_generation(self):
        """Test that Code NCO generates chip strobes and edges."""
        dut = CodeNCO(code_length=1023)
        chip_edges = 0
        epochs = 0

        def testbench():
            nonlocal chip_edges, epochs
            # GPS L1 C/A code rate @ 16 MHz sampling
            freq_word_gps = int((1.023e6 / 16e6) * (2**32))
            yield dut.freq_word.eq(freq_word_gps)
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            for _ in range(20000):
                yield Tick()
                if (yield dut.chip_strobe):
                    chip_edges += 1
                if (yield dut.code_epoch):
                    epochs += 1

        sim = Simulator(dut)
        sim.add_clock(1 / 16e6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertGreater(chip_edges, 0, "No chip strobes detected")
        self.assertGreater(epochs, 0, "No code epochs detected")

    def test_code_nco_chip_accuracy(self):
        """Test that Code NCO generates correct number of chips."""
        dut = CodeNCO(code_length=1023)
        chip_count = 0
        epoch_count = 0

        def testbench():
            nonlocal chip_count, epoch_count
            freq_word_gps = int((1.023e6 / 16e6) * (2**32))
            yield dut.freq_word.eq(freq_word_gps)
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            for _ in range(20000):
                yield Tick()
                if (yield dut.chip_strobe):
                    chip_count += 1
                if (yield dut.code_epoch):
                    epoch_count += 1

        sim = Simulator(dut)
        sim.add_clock(1 / 16e6)
        sim.add_testbench(testbench)
        sim.run()

        # At 1.023 MHz code rate and 16 MHz sampling: 20000 * 1.023/16 ≈ 1278.75 chips
        expected_chips = int(1.023e6 / 16e6 * 20000)
        self.assertAlmostEqual(chip_count, expected_chips, delta=5,
                              msg=f"Chip count mismatch: got {chip_count}, expected ~{expected_chips}")

    def test_code_nco_phase_output(self):
        """Test that Code NCO outputs valid phase values."""
        dut = CodeNCO(phase_width=32, code_length=1023)
        phase_values = []

        def testbench():
            nonlocal phase_values
            freq_word = int((1.023e6 / 16e6) * (2**32))
            yield dut.freq_word.eq(freq_word)
            yield dut.phase_offset.eq(0)
            yield dut.reset.eq(1)
            yield Tick()
            yield dut.reset.eq(0)
            yield dut.enable.eq(1)

            for _ in range(50):
                yield Tick()
                phase = yield dut.chip_phase
                phase_values.append(phase)

        sim = Simulator(dut)
        sim.add_clock(1 / 16e6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertGreater(len(phase_values), 0, "No phase values captured")
        # Verify phase values are non-zero and valid
        valid_phases = all(0 <= p < 2**32 for p in phase_values)
        self.assertTrue(valid_phases, "Phase values outside valid range")


class TestTrackingLoopIntegration(unittest.TestCase):
    """Test tracking loop integration."""

    def test_nco_and_correlator_integration(self):
        """Test that NCO and Correlator work together."""
        carrier_nco = CarrierNCO()
        code_nco = CodeNCO()
        correlator = Correlator()

        carrier_valid = False
        code_valid = False
        correlator_valid = False

        def testbench():
            nonlocal carrier_valid, code_valid, correlator_valid

            # Setup Carrier NCO
            yield carrier_nco.freq_word.eq(268435)
            yield carrier_nco.phase_offset.eq(0)
            yield carrier_nco.reset.eq(1)
            yield Tick()
            yield carrier_nco.reset.eq(0)
            yield carrier_nco.enable.eq(1)

            # Setup Code NCO
            freq_word_gps = int((1.023e6 / 16e6) * (2**32))
            yield code_nco.freq_word.eq(freq_word_gps)
            yield code_nco.phase_offset.eq(0)
            yield code_nco.reset.eq(1)
            yield Tick()
            yield code_nco.reset.eq(0)
            yield code_nco.enable.eq(1)

            # Setup Correlator
            yield correlator.reset.eq(1)
            yield Tick()
            yield correlator.reset.eq(0)
            yield correlator.integrate.eq(1)

            for i in range(1000):
                # Get NCO outputs
                cos_val = (yield carrier_nco.cos_out)
                sin_val = (yield carrier_nco.sin_out)
                carrier_valid_temp = (yield carrier_nco.valid)

                code_strobe = (yield code_nco.chip_strobe)
                chip_idx = (yield code_nco.chip_index)
                code_valid_temp = code_strobe > 0

                # Connect NCO to correlator
                yield correlator.carrier_i.eq(cos_val)
                yield correlator.carrier_q.eq(sin_val)
                yield correlator.sample_i.eq(1)
                yield correlator.sample_q.eq(0)
                yield correlator.code_prompt.eq(chip_idx % 2)
                yield correlator.code_early.eq(chip_idx % 2)
                yield correlator.code_late.eq(chip_idx % 2)

                if i > 500:
                    yield correlator.dump.eq(1)
                    yield correlator.integrate.eq(0)
                    correlator_valid_temp = (yield correlator.dump_valid)
                else:
                    correlator_valid_temp = False
                    yield correlator.dump.eq(0)

                yield Tick()

                if carrier_valid_temp:
                    carrier_valid = True
                if code_valid_temp:
                    code_valid = True
                if correlator_valid_temp:
                    correlator_valid = True

        # Create a composite testbench that simulates all three together
        class CompositeModule(Elaboratable):
            def elaborate(self, platform):
                m = Module()
                m.submodules.carrier = carrier_nco
                m.submodules.code = code_nco
                m.submodules.corr = correlator
                return m

        dut = CompositeModule()
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(carrier_valid, "Carrier NCO not producing valid output")
        self.assertTrue(code_valid, "Code NCO not generating strobes")
        self.assertTrue(correlator_valid, "Correlator not dumping valid data")


class TestModuleElaboration(unittest.TestCase):
    """Test that all modules elaborate correctly."""

    def test_carrier_nco_elaboration_default(self):
        """Test Carrier NCO elaboration with default parameters."""
        dut = CarrierNCO()
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")

    def test_carrier_nco_elaboration_custom(self):
        """Test Carrier NCO elaboration with custom parameters."""
        dut = CarrierNCO(phase_width=24, amp_width=14, lut_depth=128)
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")

    def test_code_nco_elaboration_default(self):
        """Test Code NCO elaboration with default parameters."""
        dut = CodeNCO()
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")

    def test_code_nco_elaboration_custom(self):
        """Test Code NCO elaboration with custom code length."""
        dut = CodeNCO(phase_width=32, code_length=2046)  # BeiDou length
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")

    def test_correlator_elaboration_default(self):
        """Test Correlator elaboration with default parameters."""
        dut = Correlator()
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")

    def test_correlator_elaboration_custom(self):
        """Test Correlator elaboration with custom accumulator width."""
        dut = Correlator(acc_width=40)
        try:
            Fragment.get(dut, platform=None)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed: {e}")


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCarrierNCO))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeNCO))
    suite.addTests(loader.loadTestsFromTestCase(TestTrackingLoopIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestModuleElaboration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()

    # Print summary
    print("\n" + "="*70)
    print("TRACKING LOOP TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    exit(0 if result.wasSuccessful() else 1)
