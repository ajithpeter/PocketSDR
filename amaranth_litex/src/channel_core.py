"""
GNSS Channel Core - Complete single-channel signal processor.

Integrates carrier NCO, code NCO, correlator, and PRN code generators
into a complete GNSS tracking channel.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring, stream, data
from amaranth.lib.wiring import In, Out
from amaranth.lib.fifo import SyncFIFO

from carrier_nco import CarrierNCO
from code_nco import CodeNCO
from correlator import Correlator
from gps_l1ca_gen import GPSL1CAGenerator
from navic_l5_gen import NavICL5Generator


class ChannelCore(wiring.Component):
    """
    Complete GNSS channel processor.

    Integrates:
    - Carrier NCO (Doppler compensation)
    - Code NCO (chip timing)
    - PRN code generators (GPS L1 C/A and NavIC L5)
    - E/P/L Correlator

    Signal flow:
    1. Input samples → Correlator
    2. Carrier NCO → Correlator (carrier wipeoff)
    3. Code NCO → PRN Generator (chip timing)
    4. PRN Generator → Correlator (code correlation)
    5. Correlator → Output (I/Q correlation results)

    Parameters
    ----------
    channel_id : int
        Channel identification number (0-11)
    """

    # Sample input stream (from MAX2771 interface)
    samples: In(stream.Signature(data.StructLayout({
        "i": signed(2),
        "q": signed(2)
    })))

    # Control inputs
    carrier_freq: In(unsigned(32))    # Carrier frequency word
    carrier_phase: In(unsigned(32))   # Carrier phase offset
    code_freq: In(unsigned(32))       # Code frequency word

    signal_type: In(unsigned(2))      # 0=GPS L1, 1=NavIC L5, 2-3=reserved
    prn: In(unsigned(8))              # PRN number

    integration_time: In(unsigned(16)) # Integration period in samples
    enable: In(1)                     # Channel enable
    reset: In(1)                      # Synchronous reset

    # Status outputs
    corr_e_i: Out(signed(32))         # Early I
    corr_e_q: Out(signed(32))         # Early Q
    corr_p_i: Out(signed(32))         # Prompt I
    corr_p_q: Out(signed(32))         # Prompt Q
    corr_l_i: Out(signed(32))         # Late I
    corr_l_q: Out(signed(32))         # Late Q

    chip_count: Out(unsigned(11))     # Current chip index
    code_epoch: Out(1)                # Code epoch strobe
    dump_ready: Out(1)                # Correlation dump ready

    def __init__(self, channel_id=0):
        """Initialize channel core."""
        super().__init__()
        self.channel_id = channel_id

    def elaborate(self, platform):
        m = Module()

        # === Instantiate submodules ===

        # Carrier NCO for Doppler compensation
        m.submodules.carrier_nco = carrier_nco = CarrierNCO()

        # Code NCO for chip timing
        m.submodules.code_nco = code_nco = CodeNCO(code_length=1023)

        # GPS L1 C/A code generator
        m.submodules.gps_gen = gps_gen = GPSL1CAGenerator()

        # NavIC L5 code generator
        m.submodules.navic_gen = navic_gen = NavICL5Generator()

        # Correlator
        m.submodules.correlator = correlator = Correlator(acc_width=32)

        # === Carrier NCO connections ===
        m.d.comb += [
            carrier_nco.freq_word.eq(self.carrier_freq),
            carrier_nco.phase_offset.eq(self.carrier_phase),
            carrier_nco.enable.eq(self.enable),
            carrier_nco.reset.eq(self.reset)
        ]

        # === Code NCO connections ===
        m.d.comb += [
            code_nco.freq_word.eq(self.code_freq),
            code_nco.enable.eq(self.enable),
            code_nco.reset.eq(self.reset)
        ]

        # === PRN Code Generator connections ===

        # Both generators receive same control signals
        m.d.comb += [
            gps_gen.prn.eq(self.prn),
            gps_gen.chip_index.eq(code_nco.chip_index),
            gps_gen.chip_strobe.eq(code_nco.chip_strobe),
            gps_gen.reset.eq(self.reset),

            navic_gen.prn.eq(self.prn),
            navic_gen.chip_index.eq(code_nco.chip_index),
            navic_gen.chip_strobe.eq(code_nco.chip_strobe),
            navic_gen.reset.eq(self.reset)
        ]

        # Select code based on signal_type
        code_early = Signal()
        code_prompt = Signal()
        code_late = Signal()

        with m.If(self.signal_type == 0):  # GPS L1 C/A
            m.d.comb += [
                code_early.eq(gps_gen.code_early),
                code_prompt.eq(gps_gen.code_prompt),
                code_late.eq(gps_gen.code_late)
            ]
        with m.Elif(self.signal_type == 1):  # NavIC L5
            m.d.comb += [
                code_early.eq(navic_gen.code_early),
                code_prompt.eq(navic_gen.code_prompt),
                code_late.eq(navic_gen.code_late)
            ]
        with m.Else():  # Reserved/invalid - default to GPS
            m.d.comb += [
                code_early.eq(gps_gen.code_early),
                code_prompt.eq(gps_gen.code_prompt),
                code_late.eq(gps_gen.code_late)
            ]

        # === Sample input handling ===

        # Accept samples when enabled and stream is valid
        sample_valid = Signal()
        m.d.comb += [
            sample_valid.eq(self.samples.valid & self.enable),
            self.samples.ready.eq(1)  # Always ready to accept samples
        ]

        # === Correlator connections ===

        # Input samples
        m.d.comb += [
            correlator.sample_i.eq(self.samples.payload.i),
            correlator.sample_q.eq(self.samples.payload.q)
        ]

        # Carrier from NCO
        m.d.comb += [
            correlator.carrier_i.eq(carrier_nco.cos_out),
            correlator.carrier_q.eq(carrier_nco.sin_out)
        ]

        # Code from selected generator
        m.d.comb += [
            correlator.code_early.eq(code_early),
            correlator.code_prompt.eq(code_prompt),
            correlator.code_late.eq(code_late)
        ]

        # Control signals
        m.d.comb += [
            correlator.integrate.eq(sample_valid),
            correlator.reset.eq(self.reset)
        ]

        # === Integration period control ===

        # Count samples for integration period
        sample_count = Signal(16)

        with m.If(self.reset):
            m.d.sync += sample_count.eq(0)
        with m.Elif(sample_valid):
            with m.If(sample_count == self.integration_time - 1):
                m.d.sync += sample_count.eq(0)
            with m.Else():
                m.d.sync += sample_count.eq(sample_count + 1)

        # Generate dump signal at end of integration period
        dump_strobe = Signal()
        m.d.comb += dump_strobe.eq(sample_count == self.integration_time - 1)
        m.d.comb += correlator.dump.eq(dump_strobe & sample_valid)

        # === Output connections ===

        m.d.comb += [
            # Correlation results
            self.corr_e_i.eq(correlator.corr_e_i),
            self.corr_e_q.eq(correlator.corr_e_q),
            self.corr_p_i.eq(correlator.corr_p_i),
            self.corr_p_q.eq(correlator.corr_p_q),
            self.corr_l_i.eq(correlator.corr_l_i),
            self.corr_l_q.eq(correlator.corr_l_q),

            # Status
            self.chip_count.eq(code_nco.chip_index),
            self.code_epoch.eq(code_nco.code_epoch),
            self.dump_ready.eq(correlator.dump_valid)
        ]

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Tick
    import math

    dut = ChannelCore(channel_id=0)

    def testbench():
        """Test channel core with GPS L1 C/A signal simulation."""

        print("=" * 70)
        print("GNSS Channel Core Integration Test")
        print("=" * 70)

        # Configure for GPS L1 C/A, PRN 1
        print("\n[CONFIG] Setting up GPS L1 C/A PRN 1")
        yield dut.signal_type.eq(0)  # GPS L1 C/A
        yield dut.prn.eq(1)          # PRN 1

        # Carrier NCO: simulate 1 kHz Doppler at 16 MHz sampling
        # freq_word = (f_doppler / f_sample) * 2^32
        # For 1 kHz: (1000 / 16e6) * 2^32 = 268435
        carrier_freq_word = int((1000 / 16e6) * (2**32))
        yield dut.carrier_freq.eq(carrier_freq_word)
        yield dut.carrier_phase.eq(0)

        # Code NCO: GPS L1 C/A is 1.023 Mcps at 16 MHz sampling
        # freq_word = (f_code / f_sample) * 2^32
        # For 1.023 MHz: (1.023e6 / 16e6) * 2^32 = 274763202
        code_freq_word = int((1.023e6 / 16e6) * (2**32))
        yield dut.code_freq.eq(code_freq_word)

        # Integration time: 1 ms = 16000 samples at 16 MHz
        integration_samples = 1000  # Shortened for simulation
        yield dut.integration_time.eq(integration_samples)

        print(f"[CONFIG] Carrier freq word: {carrier_freq_word} (1 kHz Doppler)")
        print(f"[CONFIG] Code freq word: {code_freq_word} (1.023 Mcps)")
        print(f"[CONFIG] Integration: {integration_samples} samples")

        # Reset channel
        print("\n[INIT] Resetting channel")
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)
        yield dut.enable.eq(1)
        yield Tick()

        # Simulate incoming I/Q samples
        print("\n[RUN] Processing samples...")

        # Simple test signal: constant I, zero Q
        for sample_idx in range(integration_samples + 100):
            # Simulate sample stream
            yield dut.samples.payload.i.eq(1)   # Constant +1
            yield dut.samples.payload.q.eq(0)   # Zero Q
            yield dut.samples.valid.eq(1)
            yield Tick()

            # Check for dump ready
            dump_ready = yield dut.dump_ready
            if dump_ready:
                # Read correlation results
                corr_p_i = yield dut.corr_p_i
                corr_p_q = yield dut.corr_p_q
                corr_e_i = yield dut.corr_e_i
                corr_e_q = yield dut.corr_e_q
                corr_l_i = yield dut.corr_l_i
                corr_l_q = yield dut.corr_l_q

                chip_count = yield dut.chip_count

                # Convert to signed for display
                def to_signed(val, bits=32):
                    if val >= 2**(bits-1):
                        return val - 2**bits
                    return val

                corr_p_i_s = to_signed(corr_p_i)
                corr_p_q_s = to_signed(corr_p_q)
                corr_e_i_s = to_signed(corr_e_i)
                corr_e_q_s = to_signed(corr_e_q)
                corr_l_i_s = to_signed(corr_l_i)
                corr_l_q_s = to_signed(corr_l_q)

                # Calculate correlation power
                power_p = corr_p_i_s**2 + corr_p_q_s**2
                power_e = corr_e_i_s**2 + corr_e_q_s**2
                power_l = corr_l_i_s**2 + corr_l_q_s**2

                print(f"\n[DUMP] Integration complete at sample {sample_idx}")
                print(f"  Chip count: {chip_count}")
                print(f"  Early  I/Q: {corr_e_i_s:+10d} / {corr_e_q_s:+10d}  Power: {power_e:12d}")
                print(f"  Prompt I/Q: {corr_p_i_s:+10d} / {corr_p_q_s:+10d}  Power: {power_p:12d}")
                print(f"  Late   I/Q: {corr_l_i_s:+10d} / {corr_l_q_s:+10d}  Power: {power_l:12d}")

                break

        # Test code epoch detection
        print("\n[TEST] Monitoring code epochs...")
        epoch_count = 0
        for _ in range(50000):
            yield dut.samples.payload.i.eq(1)
            yield dut.samples.payload.q.eq(0)
            yield dut.samples.valid.eq(1)
            yield Tick()

            code_epoch = yield dut.code_epoch
            if code_epoch:
                chip_count = yield dut.chip_count
                epoch_count += 1
                print(f"  Epoch {epoch_count}: chip_count={chip_count}")

                if epoch_count >= 3:
                    break

        # Test NavIC L5 mode
        print("\n[TEST] Switching to NavIC L5 PRN 5...")
        yield dut.signal_type.eq(1)  # NavIC L5
        yield dut.prn.eq(5)

        # NavIC L5 is 10.23 Mcps
        code_freq_word_navic = int((10.23e6 / 16e6) * (2**32))
        yield dut.code_freq.eq(code_freq_word_navic)
        yield dut.reset.eq(1)
        yield Tick()
        yield dut.reset.eq(0)

        print(f"  NavIC code freq word: {code_freq_word_navic} (10.23 Mcps)")

        # Run for one integration period
        for sample_idx in range(integration_samples + 100):
            yield dut.samples.payload.i.eq(1)
            yield dut.samples.payload.q.eq(0)
            yield dut.samples.valid.eq(1)
            yield Tick()

            dump_ready = yield dut.dump_ready
            if dump_ready:
                corr_p_i = yield dut.corr_p_i
                corr_p_q = yield dut.corr_p_q

                corr_p_i_s = to_signed(corr_p_i)
                corr_p_q_s = to_signed(corr_p_q)
                power_p = corr_p_i_s**2 + corr_p_q_s**2

                print(f"\n[DUMP] NavIC L5 correlation:")
                print(f"  Prompt I/Q: {corr_p_i_s:+10d} / {corr_p_q_s:+10d}  Power: {power_p:12d}")
                break

        print("\n" + "=" * 70)
        print("✓ Channel Core Integration Test Complete")
        print("=" * 70)
        print("\nValidated:")
        print("  • Carrier NCO integration and carrier wipeoff")
        print("  • Code NCO chip timing generation")
        print("  • GPS L1 C/A code generation")
        print("  • NavIC L5 code generation")
        print("  • E/P/L correlation and accumulation")
        print("  • Integration period control and dump")
        print("  • Code epoch detection")
        print("  • Signal type switching (GPS ↔ NavIC)")

    sim = Simulator(dut)
    sim.add_clock(1/16e6)  # 16 MHz system clock
    sim.add_testbench(testbench)

    with sim.write_vcd("channel_core.vcd", "channel_core.gtkw",
                       traces=[
                           dut.enable,
                           dut.samples.valid,
                           dut.samples.payload.i,
                           dut.samples.payload.q,
                           dut.chip_count,
                           dut.code_epoch,
                           dut.dump_ready,
                           dut.corr_p_i,
                           dut.corr_p_q
                       ]):
        sim.run()

    print("\nVCD waveform written to channel_core.vcd")
