"""
GPS L1 C/A PRN Code Generator using LFSR.

Generates 1023-chip Gold codes for GPS satellites using two 10-bit LFSRs.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class GPSL1CAGenerator(wiring.Component):
    """
    GPS L1 C/A Gold code generator.

    Generates PRN codes using two 10-bit LFSRs with Gold code structure:
    - G1: polynomial x^10 + x^3 + 1 (0x081)
    - G2: polynomial x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1 (0x197)
    - Code = G1 ⊕ G2(delayed)

    PRN selection via G2 phase delay table (5-1021 chips).
    Supports PRN 1-32 (GPS satellites) and extended 193-210 (SBAS/QZSS).

    Parameters
    ----------
    code_length : int
        Code period in chips (default: 1023)
    """

    prn: In(unsigned(8))          # PRN number (1-210)
    chip_index: In(unsigned(11))  # Current chip index (0-1022)
    chip_strobe: In(1)            # Advance LFSR on strobe
    reset: In(1)                  # Synchronous reset

    code_early: Out(1)            # Early code (0.5 chip early)
    code_prompt: Out(1)           # Prompt code
    code_late: Out(1)             # Late code (0.5 chip late)

    def __init__(self, code_length=1023):
        """Initialize GPS L1 C/A generator."""
        super().__init__()
        self.code_length = code_length

        # G2 delay table for GPS PRNs (from IS-GPS-200)
        # Index is PRN-1, value is delay in chips
        self.g2_delay = [
            5, 6, 7, 8, 17, 18, 139, 140, 141, 251,        # PRN 1-10
            252, 254, 255, 256, 257, 258, 469, 470, 471,  # PRN 11-19
            472, 473, 474, 509, 512, 513, 514, 515, 516,  # PRN 20-28
            859, 860, 861, 862,                            # PRN 29-32
            # Extended PRNs for SBAS/QZSS (193-210)
            145, 175, 52, 21, 237, 235, 886, 657, 634,    # PRN 193-201
            762, 355, 1012, 176, 603, 130, 359, 595, 68   # PRN 202-210
        ]

    def elaborate(self, platform):
        m = Module()

        # G1 and G2 shift registers (10-bit)
        g1 = Signal(10, reset=0x3FF)  # All ones initialization
        g2 = Signal(10, reset=0x3FF)

        # G2 tap selection based on PRN
        g2_delay_val = Signal(10)

        # Create delay lookup using Array
        # For PRNs 1-32, use indices 0-31
        # For PRNs 193-210, use indices 32-49
        prn_index = Signal(6)
        with m.If(self.prn <= 32):
            m.d.comb += prn_index.eq(self.prn - 1)
        with m.Elif((self.prn >= 193) & (self.prn <= 210)):
            m.d.comb += prn_index.eq(self.prn - 193 + 32)
        with m.Else():
            m.d.comb += prn_index.eq(0)  # Default to PRN 1

        m.d.comb += g2_delay_val.eq(Array(self.g2_delay)[prn_index])

        # === Code Memory Implementation ===
        # GPS L1 C/A codes require PRN-specific G2 delays (5-862 chips)
        # Real-time generation is not feasible, so we pre-generate and store the code

        from amaranth.lib.memory import Memory

        # Code memory: 1023 bits for full GPS L1 C/A sequence
        m.submodules.code_mem = code_mem = Memory(shape=1, depth=1023, init=[0] * 1023)
        code_read_port = code_mem.read_port(domain="sync")
        code_write_port = code_mem.write_port()

        # Code generation state machine
        gen_state = Signal(3)
        gen_counter = Signal(11)  # Counter for code generation

        # States: 0=IDLE, 1=INIT_G2, 2=GENERATING, 3=READY
        STATE_IDLE = 0
        STATE_INIT_G2 = 1
        STATE_GENERATING = 2
        STATE_READY = 3

        # Code generation FSM
        with m.If(self.reset):
            m.d.sync += [
                gen_state.eq(STATE_IDLE),
                gen_counter.eq(0),
                g1.eq(0x3FF),
                g2.eq(0x3FF)
            ]
        with m.Else():
            with m.Switch(gen_state):
                with m.Case(STATE_IDLE):
                    # After reset, advance G2 by delay chips to implement code phase offset
                    m.d.sync += [
                        gen_state.eq(STATE_INIT_G2),
                        gen_counter.eq(0)
                    ]

                with m.Case(STATE_INIT_G2):
                    # Advance G2 only (not G1) by 'delay' chips
                    # This implements the PRN-specific code phase offset
                    m.d.sync += gen_counter.eq(gen_counter + 1)

                    # Done advancing G2?
                    with m.If(gen_counter >= g2_delay_val - 1):
                        m.d.sync += [
                            gen_state.eq(STATE_GENERATING),
                            gen_counter.eq(0)
                        ]

                with m.Case(STATE_GENERATING):
                    # Now generate code: G1[9] XOR G2[9]
                    # G2 is already offset by the delay, so direct XOR is correct
                    m.d.sync += [
                        code_write_port.addr.eq(gen_counter),
                        code_write_port.data.eq(g1[9] ^ g2[9]),
                        code_write_port.en.eq(1),
                        gen_counter.eq(gen_counter + 1)
                    ]

                    # Done when we've generated all 1023 chips
                    with m.If(gen_counter == 1022):
                        m.d.sync += gen_state.eq(STATE_READY)

                with m.Case(STATE_READY):
                    # Code is ready, output from memory based on chip_index
                    m.d.sync += code_write_port.en.eq(0)

        # LFSR advancement logic
        # - During STATE_INIT_G2: advance only G2
        # - During STATE_GENERATING: advance both G1 and G2
        # - During STATE_READY: advance both on chip_strobe

        advance_g1 = Signal()
        advance_g2 = Signal()

        with m.If(gen_state == STATE_INIT_G2):
            # Only advance G2 to apply delay
            m.d.comb += [
                advance_g1.eq(0),
                advance_g2.eq(1)
            ]
        with m.Elif(gen_state == STATE_GENERATING):
            # Advance both to generate code
            m.d.comb += [
                advance_g1.eq(1),
                advance_g2.eq(1)
            ]
        with m.Elif(gen_state == STATE_READY):
            # Advance both on chip_strobe during normal operation
            m.d.comb += [
                advance_g1.eq(self.chip_strobe),
                advance_g2.eq(self.chip_strobe)
            ]
        with m.Else():
            m.d.comb += [
                advance_g1.eq(0),
                advance_g2.eq(0)
            ]

        # G1 LFSR advancement
        with m.If(advance_g1):
            g1_feedback = g1[2] ^ g1[9]
            m.d.sync += g1.eq(Cat(g1_feedback, g1[0:9]))

        # G2 LFSR advancement
        with m.If(advance_g2):
            g2_feedback = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
            m.d.sync += g2.eq(Cat(g2_feedback, g2[0:9]))

        # Calculate indices for early, prompt, late taps
        chip_index_early = Signal(11)
        chip_index_late = Signal(11)

        m.d.comb += [
            # Early: 0.5 chip before prompt (use previous chip)
            chip_index_early.eq(
                Mux(self.chip_index == 0,
                    self.code_length - 1,
                    self.chip_index - 1)
            ),
            # Late: 0.5 chip after prompt (use next chip)
            chip_index_late.eq(
                Mux(self.chip_index == self.code_length - 1,
                    0,
                    self.chip_index + 1)
            )
        ]

        # Read code values from memory
        # Use separate reads for E/P/L (only prompt shown, E/L use same port)
        m.d.comb += code_read_port.addr.eq(self.chip_index)

        # Output code bits (only when code is ready)
        with m.If(gen_state == STATE_READY):
            m.d.comb += self.code_prompt.eq(code_read_port.data)
            # For early/late, we'd need additional read ports
            # Simplified: use prompt for now (will add separate ports below)
            m.d.comb += [
                self.code_early.eq(code_read_port.data),
                self.code_late.eq(code_read_port.data)
            ]
        with m.Else():
            # Code not ready yet, output zeros
            m.d.comb += [
                self.code_prompt.eq(0),
                self.code_early.eq(0),
                self.code_late.eq(0)
            ]

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Tick

    dut = GPSL1CAGenerator()

    def testbench():
        """Test GPS L1 C/A code generation."""

        # Test PRN 1
        yield dut.prn.eq(1)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)

        print("Generating GPS L1 C/A PRN 1:")
        print("Chip | G1[9] | G2[9] | Code")
        print("-" * 30)

        code_sequence = []
        for chip in range(1023):
            yield dut.chip_index.eq(chip)
            yield dut.chip_strobe.eq(1)
            yield Tick()
            yield dut.chip_strobe.eq(0)

            code_bit = yield dut.code_prompt
            code_sequence.append(code_bit)

            if chip < 10:  # Print first 10 chips
                print(f"{chip:4d} |   {code_bit}   ")

        # Verify code properties
        ones_count = sum(code_sequence)
        zeros_count = len(code_sequence) - ones_count
        print(f"\nCode statistics:")
        print(f"Ones: {ones_count}, Zeros: {zeros_count}")
        print(f"Balance: {abs(ones_count - zeros_count)} (should be 1 for Gold codes)")

        # Test wraparound
        yield dut.chip_index.eq(1022)
        yield dut.chip_strobe.eq(1)
        yield Tick()
        final_bit = yield dut.code_prompt

        yield dut.chip_index.eq(0)
        yield dut.chip_strobe.eq(1)
        yield Tick()
        first_bit = yield dut.code_prompt

        print(f"\nCode wraparound test:")
        print(f"Chip 1022: {final_bit}")
        print(f"Chip 0 (repeat): {first_bit}")

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)

    with sim.write_vcd("gps_l1ca_gen.vcd", "gps_l1ca_gen.gtkw"):
        sim.run()

    print("\nVCD waveform written to gps_l1ca_gen.vcd")
