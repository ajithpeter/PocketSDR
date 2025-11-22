"""
Early/Prompt/Late Correlator for GNSS signal tracking.

Performs complex correlation: Σ (sample × code × carrier*)

Supports configurable integration periods and multiple correlation taps.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class Correlator(wiring.Component):
    """
    Multi-tap correlator for GNSS signal tracking.

    Performs carrier wipeoff and code correlation with E/P/L taps.

    Features:
    - Complex correlation (I and Q channels)
    - 3 taps: Early, Prompt, Late
    - Configurable integration period
    - Dump-on-epoch with automatic clear
    - Optional DSP48 inference for multiplication

    Integration flow:
    1. Carrier wipeoff: (I+jQ) × (cos-j·sin)
    2. Code multiplication: wiped × code (±1)
    3. Accumulation over integration period
    4. Dump and clear on epoch

    Parameters
    ----------
    acc_width : int
        Accumulator width in bits (default: 32)
    """

    # Input signals
    sample_i: In(signed(2))       # Input sample I (2-bit from ADC)
    sample_q: In(signed(2))       # Input sample Q (2-bit from ADC)
    carrier_i: In(signed(16))     # Carrier cos(θ)
    carrier_q: In(signed(16))     # Carrier sin(θ)
    code_early: In(1)             # Early code chip (±1 as 0/1)
    code_prompt: In(1)            # Prompt code chip
    code_late: In(1)              # Late code chip

    integrate: In(1)              # Enable integration
    dump: In(1)                   # Dump and clear accumulators
    reset: In(1)                  # Synchronous reset

    # Output signals (correlation results)
    corr_e_i: Out(signed(32))     # Early I accumulator
    corr_e_q: Out(signed(32))     # Early Q accumulator
    corr_p_i: Out(signed(32))     # Prompt I accumulator
    corr_p_q: Out(signed(32))     # Prompt Q accumulator
    corr_l_i: Out(signed(32))     # Late I accumulator
    corr_l_q: Out(signed(32))     # Late Q accumulator
    dump_valid: Out(1)            # Dump output valid flag

    def __init__(self, acc_width=32):
        """Initialize Correlator."""
        super().__init__()
        self.acc_width = acc_width

    def elaborate(self, platform):
        m = Module()

        # === Stage 1: Carrier Wipeoff (Complex Multiplication) ===
        # (I + jQ) × (cos - j·sin) = (I·cos + Q·sin) + j(Q·cos - I·sin)

        # Intermediate products (18-bit to accommodate 2-bit × 16-bit)
        wiped_i = Signal(signed(18))
        wiped_q = Signal(signed(18))

        m.d.sync += [
            wiped_i.eq(self.sample_i * self.carrier_i +
                      self.sample_q * self.carrier_q),
            wiped_q.eq(self.sample_q * self.carrier_i -
                      self.sample_i * self.carrier_q)
        ]

        # === Stage 2: Code Correlation ===
        # Code is represented as 0 or 1, where:
        # - 1 means multiply by +1 (keep value)
        # - 0 means multiply by -1 (negate value)

        # Accumulators for each tap
        acc_e_i = Signal(signed(self.acc_width))
        acc_e_q = Signal(signed(self.acc_width))
        acc_p_i = Signal(signed(self.acc_width))
        acc_p_q = Signal(signed(self.acc_width))
        acc_l_i = Signal(signed(self.acc_width))
        acc_l_q = Signal(signed(self.acc_width))

        with m.If(self.reset):
            m.d.sync += [
                acc_e_i.eq(0),
                acc_e_q.eq(0),
                acc_p_i.eq(0),
                acc_p_q.eq(0),
                acc_l_i.eq(0),
                acc_l_q.eq(0)
            ]
        with m.Elif(self.dump):
            # Output current values and clear
            m.d.sync += [
                self.corr_e_i.eq(acc_e_i),
                self.corr_e_q.eq(acc_e_q),
                self.corr_p_i.eq(acc_p_i),
                self.corr_p_q.eq(acc_p_q),
                self.corr_l_i.eq(acc_l_i),
                self.corr_l_q.eq(acc_l_q),
                self.dump_valid.eq(1),
                acc_e_i.eq(0),
                acc_e_q.eq(0),
                acc_p_i.eq(0),
                acc_p_q.eq(0),
                acc_l_i.eq(0),
                acc_l_q.eq(0)
            ]
        with m.Elif(self.integrate):
            m.d.sync += self.dump_valid.eq(0)

            # Early tap correlation
            with m.If(self.code_early):  # Code = +1
                m.d.sync += [
                    acc_e_i.eq(acc_e_i + wiped_i),
                    acc_e_q.eq(acc_e_q + wiped_q)
                ]
            with m.Else():  # Code = -1
                m.d.sync += [
                    acc_e_i.eq(acc_e_i - wiped_i),
                    acc_e_q.eq(acc_e_q - wiped_q)
                ]

            # Prompt tap correlation
            with m.If(self.code_prompt):
                m.d.sync += [
                    acc_p_i.eq(acc_p_i + wiped_i),
                    acc_p_q.eq(acc_p_q + wiped_q)
                ]
            with m.Else():
                m.d.sync += [
                    acc_p_i.eq(acc_p_i - wiped_i),
                    acc_p_q.eq(acc_p_q - wiped_q)
                ]

            # Late tap correlation
            with m.If(self.code_late):
                m.d.sync += [
                    acc_l_i.eq(acc_l_i + wiped_i),
                    acc_l_q.eq(acc_l_q + wiped_q)
                ]
            with m.Else():
                m.d.sync += [
                    acc_l_i.eq(acc_l_i - wiped_i),
                    acc_l_q.eq(acc_l_q - wiped_q)
                ]
        with m.Else():
            m.d.sync += self.dump_valid.eq(0)

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator
    import math

    dut = Correlator()

    def testbench():
        """Test correlator with synthetic signal."""

        # Simulate a simple signal: constant carrier and alternating code
        carrier_phase = 0
        carrier_freq = 0.1  # radians per sample

        yield dut.reset.eq(1)
        yield
        yield dut.reset.eq(0)
        yield dut.integrate.eq(1)

        integration_samples = 1000

        for sample in range(integration_samples):
            # Generate carrier (simulate NCO output)
            carrier_i_val = int(32767 * math.cos(carrier_phase))
            carrier_q_val = int(32767 * math.sin(carrier_phase))
            carrier_phase += carrier_freq

            # Simulate 2-bit I/Q samples (simplified: constant +1)
            sample_i_val = 1
            sample_q_val = 0

            # Simulate code (alternating for test)
            code_val = (sample // 10) % 2  # Change every 10 samples

            yield dut.sample_i.eq(sample_i_val)
            yield dut.sample_q.eq(sample_q_val)
            yield dut.carrier_i.eq(carrier_i_val)
            yield dut.carrier_q.eq(carrier_q_val)
            yield dut.code_early.eq(code_val)
            yield dut.code_prompt.eq(code_val)
            yield dut.code_late.eq(code_val)
            yield

        # Dump results
        yield dut.integrate.eq(0)
        yield dut.dump.eq(1)
        yield
        yield dut.dump.eq(0)
        yield

        # Read correlation results
        dump_valid = yield dut.dump_valid
        if dump_valid:
            corr_p_i = yield dut.corr_p_i
            corr_p_q = yield dut.corr_p_q
            print(f"Prompt I: {corr_p_i}")
            print(f"Prompt Q: {corr_p_q}")
            print(f"Correlation power: {corr_p_i**2 + corr_p_q**2}")

    sim = Simulator(dut)
    sim.add_clock(1e-6)  # 1 MHz for faster simulation
    sim.add_process(testbench)

    with sim.write_vcd("correlator.vcd", "correlator.gtkw"):
        sim.run()

    print("\nVCD waveform written to correlator.vcd")
