"""
Code NCO (Numerically Controlled Oscillator) for GNSS PRN code timing.

Generates code chip boundaries and fractional chip phase for correlation.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class CodeNCO(wiring.Component):
    """
    Code phase NCO for PRN code generation timing.

    Generates chip clock and chip index for code generators.
    Supports fractional chip phase for early/late tap generation.

    For GPS L1 C/A @ fs=16 MHz:
    - Code rate: 1.023 Mcps
    - Samples/chip: 16/1.023 ≈ 15.64
    - Phase increment: (1.023e6 / 16e6) * 2^32 ≈ 0x0A2C2A2C

    For NavIC L5 @ fs=16 MHz:
    - Code rate: 10.23 Mcps
    - Samples/chip: 16/10.23 ≈ 1.56
    - Phase increment: (10.23e6 / 16e6) * 2^32 ≈ 0x655C28F6

    Parameters
    ----------
    phase_width : int
        Phase accumulator width (default: 32)
    code_length : int
        Maximum code length in chips (default: 1023 for GPS/NavIC)
    """

    freq_word: In(32)           # Code rate control word
    phase_offset: In(32)        # Phase offset
    enable: In(1)               # Enable accumulation
    reset: In(1)                # Synchronous reset

    chip_index: Out(unsigned(11))  # Current chip index (0-2046 for BeiDou max)
    chip_phase: Out(unsigned(32))  # Fractional chip phase (full accumulator)
    chip_strobe: Out(1)            # Strobes high for one cycle on chip edge
    code_epoch: Out(1)             # Strobes high on code epoch (wraparound)

    def __init__(self, phase_width=32, code_length=1023):
        """Initialize CodeNCO."""
        super().__init__()
        self.phase_width = phase_width
        self.code_length = code_length

    def elaborate(self, platform):
        m = Module()

        # Phase accumulator
        phase_acc = Signal(self.phase_width)
        prev_phase_msb = Signal()

        # Chip counter with configurable wraparound
        chip_count = Signal(range(self.code_length))

        # Stage 1: Phase accumulation
        with m.If(self.reset):
            m.d.sync += [
                phase_acc.eq(0),
                chip_count.eq(0),
                prev_phase_msb.eq(0)
            ]
        with m.Elif(self.enable):
            # Advance phase
            new_phase = Signal(self.phase_width)
            m.d.comb += new_phase.eq(phase_acc + self.freq_word)
            m.d.sync += phase_acc.eq(new_phase)

            # Detect chip edge (MSB 0→1 transition indicates new chip)
            chip_edge = Signal()
            m.d.comb += chip_edge.eq(~prev_phase_msb & new_phase[self.phase_width-1])

            with m.If(chip_edge):
                # Increment chip counter
                with m.If(chip_count == self.code_length - 1):
                    m.d.sync += [
                        chip_count.eq(0),
                        self.code_epoch.eq(1)  # Code epoch wraparound
                    ]
                with m.Else():
                    m.d.sync += [
                        chip_count.eq(chip_count + 1),
                        self.code_epoch.eq(0)
                    ]

                m.d.sync += self.chip_strobe.eq(1)
            with m.Else():
                m.d.sync += [
                    self.chip_strobe.eq(0),
                    self.code_epoch.eq(0)
                ]

            # Update MSB history
            m.d.sync += prev_phase_msb.eq(new_phase[self.phase_width-1])

        # Output assignments
        total_phase = Signal(self.phase_width)
        m.d.comb += total_phase.eq(phase_acc + self.phase_offset)

        m.d.comb += [
            self.chip_index.eq(chip_count),
            self.chip_phase.eq(total_phase)
        ]

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Tick

    dut = CodeNCO(code_length=1023)

    def testbench():
        # GPS L1 C/A code rate @ 16 MHz sampling
        # freq_word = (1.023e6 / 16e6) * 2^32
        freq_word_gps = int((1.023e6 / 16e6) * (2**32))
        print(f"GPS L1 C/A freq_word: 0x{freq_word_gps:08X}")

        yield dut.freq_word.eq(freq_word_gps)
        yield dut.phase_offset.eq(0)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)
        yield dut.enable.eq(1)

        chip_edges = 0
        epochs = 0

        # Run for enough samples to see chip edges and epoch
        for cycle in range(20000):  # ~1.25 ms @ 16 MHz
            yield Tick()

            if (yield dut.chip_strobe):
                chip_edges += 1
                chip_idx = yield dut.chip_index
                if chip_idx % 100 == 0:
                    print(f"Cycle {cycle}: Chip edge, index={chip_idx}")

            if (yield dut.code_epoch):
                epochs += 1
                print(f"Cycle {cycle}: CODE EPOCH (wraparound)")

        print(f"\nTotal chip edges: {chip_edges}")
        print(f"Total epochs: {epochs}")
        print(f"Expected chips: ~{1.023e6 / 16e6 * 20000:.1f}")

        # Verify results
        assert chip_edges > 0, "ERROR: No chip edges detected!"
        assert epochs > 0, "ERROR: No code epochs detected!"
        expected_chips = int(1.023e6 / 16e6 * 20000)
        assert abs(chip_edges - expected_chips) < 5, f"ERROR: Chip count mismatch! Got {chip_edges}, expected ~{expected_chips}"
        print("\nTEST PASSED: Code NCO testbench completed successfully")

    sim = Simulator(dut)
    sim.add_clock(1/16e6)
    sim.add_testbench(testbench)

    with sim.write_vcd("code_nco.vcd", "code_nco.gtkw"):
        sim.run()

    print("\nVCD waveform written to code_nco.vcd")
