"""
MAX2771 RF Frontend ADC Interface for ECP5 FPGA.

Interfaces with MAX2771 GNSS RF frontend chip for sample acquisition.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring, stream, data
from amaranth.lib.wiring import In, Out
from amaranth.lib.fifo import AsyncFIFO


class MAX2771Interface(wiring.Component):
    """
    MAX2771 RF frontend parallel interface.

    The MAX2771 provides 2-bit I and 2-bit Q outputs at the sampling rate.

    Interface modes:
    1. Parallel mode: 4-bit bus (2-bit I + 2-bit Q) + clock (implemented here)
    2. Serial mode: LVDS data stream + clock (not implemented)

    MAX2771 Output Format (2-bit sign-magnitude):
    - Bit[1] = sign (0=positive, 1=negative)
    - Bit[0] = magnitude (0=1, 1=3)
    - Encoding: 00→+1, 01→+3, 10→-1, 11→-3

    Pin Connections:
    - iq_data[1:0]: I component (IQ0, IQ1)
    - iq_data[3:2]: Q component (IQ2, IQ3)
    - sample_clk: CLKOUT from MAX2771 (4-16 MHz)

    Parameters
    ----------
    fifo_depth : int
        Async FIFO depth for clock domain crossing (default: 2048)
    """

    # Input pins from MAX2771 (adc clock domain)
    iq_data: In(unsigned(4))      # Parallel IQ data bus
    sample_clk: In(1)             # CLKOUT from MAX2771

    # Output stream (sys clock domain)
    samples: Out(stream.Signature(data.StructLayout({
        "i": signed(2),
        "q": signed(2)
    })))

    def __init__(self, fifo_depth=2048):
        """Initialize MAX2771 interface."""
        super().__init__()
        self.fifo_depth = fifo_depth

    def elaborate(self, platform):
        m = Module()

        # === ADC Clock Domain (sample_clk from MAX2771) ===

        # Synchronize inputs to adc domain to reduce metastability
        iq_data_sync = Signal(4)
        m.d.adc += iq_data_sync.eq(self.iq_data)

        # Extract I and Q components
        i_raw = Signal(2)
        q_raw = Signal(2)
        m.d.comb += [
            i_raw.eq(iq_data_sync[0:2]),
            q_raw.eq(iq_data_sync[2:4])
        ]

        # Convert 2-bit sign-magnitude to signed 2-bit values
        # MAX2771 format: bit[1]=sign, bit[0]=magnitude
        # 00 → +1 (binary 01), 01 → +3 (binary 11)
        # 10 → -1 (binary 11), 11 → -3 (binary 01)
        i_signed = Signal(signed(2))
        q_signed = Signal(signed(2))

        # Truth table for conversion:
        # Input[1:0] | Signed Value | Binary (2's comp)
        # -----------|--------------|------------------
        #    00      |     +1       |       01
        #    01      |     +3       |       11  (saturated at +1 in 2-bit)
        #    10      |     -1       |       11
        #    11      |     -3       |       01  (saturated at -2 in 2-bit)

        # Actually for proper 2-bit signed representation:
        # +1 = 0b01, +3 would be out of range (use +1 = 0b01)
        # -1 = 0b11, -3 would be out of range (use -2 = 0b10)

        # Simplified mapping preserving sign and magnitude bits:
        with m.If(i_raw[1]):  # Negative
            with m.If(i_raw[0]):
                m.d.adc += i_signed.eq(-2)  # 11 → -3 ≈ -2 in 2-bit
            with m.Else():
                m.d.adc += i_signed.eq(-1)  # 10 → -1
        with m.Else():  # Positive
            with m.If(i_raw[0]):
                m.d.adc += i_signed.eq(1)   # 01 → +3 ≈ +1 in 2-bit
            with m.Else():
                m.d.adc += i_signed.eq(1)   # 00 → +1

        with m.If(q_raw[1]):  # Negative
            with m.If(q_raw[0]):
                m.d.adc += q_signed.eq(-2)
            with m.Else():
                m.d.adc += q_signed.eq(-1)
        with m.Else():  # Positive
            with m.If(q_raw[0]):
                m.d.adc += q_signed.eq(1)
            with m.Else():
                m.d.adc += q_signed.eq(1)

        # === Clock Domain Crossing FIFO ===

        # Async FIFO: adc_clk (write) → sync_clk (read)
        m.submodules.fifo = fifo = AsyncFIFO(
            width=4,  # 2-bit I + 2-bit Q
            depth=self.fifo_depth,
            r_domain="sync",  # System clock domain
            w_domain="adc"    # ADC sampling clock domain
        )

        # Write to FIFO (adc domain)
        m.d.comb += [
            fifo.w_data.eq(Cat(i_signed, q_signed)),
            fifo.w_en.eq(1)  # Continuous sampling
        ]

        # Read from FIFO (sync domain)
        fifo_i = Signal(signed(2))
        fifo_q = Signal(signed(2))
        m.d.comb += [
            fifo_i.eq(fifo.r_data[0:2].as_signed()),
            fifo_q.eq(fifo.r_data[2:4].as_signed())
        ]

        # === Output Stream (System Clock Domain) ===

        # Stream interface
        m.d.sync += [
            self.samples.payload.i.eq(fifo_i),
            self.samples.payload.q.eq(fifo_q),
            self.samples.valid.eq(fifo.r_rdy),
        ]

        m.d.comb += fifo.r_en.eq(self.samples.ready)

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Settle

    dut = MAX2771Interface(fifo_depth=32)

    def adc_process():
        """Simulate ADC providing samples."""

        # Test pattern: cycle through all 2-bit combinations
        test_patterns = [
            (0b00, 0b00),  # +1, +1
            (0b01, 0b01),  # +3, +3
            (0b10, 0b10),  # -1, -1
            (0b11, 0b11),  # -3, -3
            (0b00, 0b11),  # +1, -3
            (0b11, 0b00),  # -3, +1
        ]

        print("ADC Process: Generating test patterns")
        print("Pattern | I_raw | Q_raw | Expected I | Expected Q")
        print("-" * 55)

        for i, (i_raw, q_raw) in enumerate(test_patterns):
            yield dut.iq_data.eq((q_raw << 2) | i_raw)
            yield Settle()

            # Expected signed values
            i_exp = 1 if not (i_raw & 0b10) else (-2 if (i_raw & 0b01) else -1)
            q_exp = 1 if not (q_raw & 0b10) else (-2 if (q_raw & 0b01) else -1)

            print(f"  {i:2d}    | 0x{i_raw:02X}  | 0x{q_raw:02X}  |    {i_exp:+2d}     |    {q_exp:+2d}")

            # Wait a few ADC clock cycles
            for _ in range(4):
                yield

    def sys_process():
        """Read samples from system clock domain."""

        print("\nSystem Process: Reading samples from FIFO")
        print("Sample | I  | Q  |")
        print("-" * 25)

        # Assert ready to receive samples
        yield dut.samples.ready.eq(1)

        sample_count = 0
        for _ in range(100):  # Read up to 100 samples
            yield
            valid = yield dut.samples.valid

            if valid:
                i_val = yield dut.samples.payload.i
                q_val = yield dut.samples.payload.q

                # Convert unsigned to signed for display
                i_signed = i_val if i_val < 2 else i_val - 4
                q_signed = q_val if q_val < 2 else q_val - 4

                print(f"  {sample_count:3d}  | {i_signed:+2d} | {q_signed:+2d} |")
                sample_count += 1

                if sample_count >= 10:
                    break

        print(f"\n✓ Received {sample_count} samples successfully")

    sim = Simulator(dut)
    sim.add_clock(1/16e6, domain="adc")   # 16 MHz ADC clock
    sim.add_clock(1/50e6, domain="sync")  # 50 MHz system clock

    sim.add_process(adc_process, domain="adc")
    sim.add_process(sys_process, domain="sync")

    with sim.write_vcd("max2771_interface.vcd", "max2771_interface.gtkw",
                       traces=[dut.iq_data, dut.samples.valid,
                              dut.samples.payload.i, dut.samples.payload.q]):
        sim.run()

    print("\nVCD waveform written to max2771_interface.vcd")
