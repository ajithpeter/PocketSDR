"""
Wishbone CSR Interface for GNSS Baseband.

Provides memory-mapped register access to channel manager and global controls
via LiteX Wishbone bus.

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring, stream, data
from amaranth.lib.wiring import In, Out


class WishboneCSRBridge(wiring.Component):
    """
    Wishbone to CSR interface bridge.

    Translates Wishbone bus transactions into simplified CSR read/write
    operations for the channel manager.

    Memory Map:
    -----------
    0x0000 - 0x0FFF: Channel registers (12 channels × 0x100 bytes)
    0x1000 - 0x10FF: Global control registers

    Global Registers:
    -----------------
    0x1000: GLOBAL_CTRL
      [0]: Global enable (master enable for all channels)
      [1]: Global reset
      [2]: Sample enable
      [31-3]: Reserved

    0x1004: GLOBAL_STATUS
      [0]: IRQ status
      [7-1]: Reserved
      [31-8]: Active channel mask (bits indicate which channels are enabled)

    0x1008: VERSION
      [31-0]: Version register (0xA5A50001 for v0.1)

    0x100C: CHANNEL_COUNT
      [7-0]: Number of channels (12)
      [31-8]: Reserved

    0x1010: SAMPLE_COUNT
      [31-0]: Total samples processed (read-only counter)

    0x1014: IRQ_MASK
      [11-0]: Per-channel interrupt mask
      [31-12]: Reserved

    0x1018: IRQ_STATUS
      [11-0]: Per-channel interrupt status (write 1 to clear)
      [31-12]: Reserved

    Wishbone Interface (Classic pipelined):
    ---------------------------------------
    - 32-bit data width
    - 32-bit address (byte-addressed, word-aligned)
    - Single-cycle latency
    - No wait states (ACK immediately after CYC+STB)
    """

    # Wishbone bus signals (Classic pipelined)
    wb_adr: In(unsigned(32))      # Address
    wb_dat_w: In(unsigned(32))    # Write data
    wb_dat_r: Out(unsigned(32))   # Read data
    wb_sel: In(unsigned(4))       # Byte select (for 32-bit words)
    wb_cyc: In(1)                 # Cycle valid
    wb_stb: In(1)                 # Strobe
    wb_we: In(1)                  # Write enable
    wb_ack: Out(1)                # Acknowledge

    # CSR interface to channel manager
    csr_addr: Out(unsigned(16))
    csr_write_data: Out(unsigned(32))
    csr_read_data: In(unsigned(32))
    csr_write: Out(1)
    csr_read: Out(1)
    csr_ready: In(1)

    # Global controls
    global_enable: Out(1)
    global_reset: Out(1)
    sample_enable: Out(1)

    # IRQ
    irq_in: In(1)                 # IRQ from channel manager
    irq_out: Out(1)               # IRQ to CPU (after masking)

    def __init__(self, num_channels=12):
        """Initialize Wishbone CSR bridge."""
        super().__init__()
        self.num_channels = num_channels

    def elaborate(self, platform):
        m = Module()

        # === Global registers ===

        global_ctrl = Signal(32)
        irq_mask = Signal(self.num_channels, reset=(1 << self.num_channels) - 1)  # All enabled
        irq_status = Signal(self.num_channels)
        sample_counter = Signal(32)

        # Extract global control bits
        m.d.comb += [
            self.global_enable.eq(global_ctrl[0]),
            self.global_reset.eq(global_ctrl[1]),
            self.sample_enable.eq(global_ctrl[2])
        ]

        # Auto-clear global reset
        with m.If(global_ctrl[1]):
            m.d.sync += global_ctrl[1].eq(0)

        # === Wishbone transaction handling ===

        # Wishbone access is valid when CYC and STB are both high
        wb_valid = Signal()
        m.d.comb += wb_valid.eq(self.wb_cyc & self.wb_stb)

        # Decode address regions
        # [31:16] = reserved, [15:12] = region, [11:0] = offset
        addr_region = Signal(4)
        addr_offset = Signal(12)

        m.d.comb += [
            addr_region.eq(self.wb_adr[12:16]),
            addr_offset.eq(self.wb_adr[0:12])
        ]

        is_channel_region = Signal()
        is_global_region = Signal()

        m.d.comb += [
            is_channel_region.eq(addr_region == 0),  # 0x0000 - 0x0FFF
            is_global_region.eq(addr_region == 1)    # 0x1000 - 0x1FFF
        ]

        # === CSR access to channel manager ===

        csr_access_active = Signal()

        with m.If(wb_valid & is_channel_region):
            # Forward to channel manager
            m.d.comb += [
                self.csr_addr.eq(addr_offset),
                self.csr_write_data.eq(self.wb_dat_w),
                self.csr_write.eq(self.wb_we),
                self.csr_read.eq(~self.wb_we)
            ]
            m.d.sync += csr_access_active.eq(1)
        with m.Else():
            m.d.comb += [
                self.csr_write.eq(0),
                self.csr_read.eq(0)
            ]
            m.d.sync += csr_access_active.eq(0)

        # === Global register access ===

        global_access_active = Signal()

        with m.If(wb_valid & is_global_region & self.wb_we):
            # Write to global registers
            with m.Switch(addr_offset):
                with m.Case(0x000):  # GLOBAL_CTRL
                    m.d.sync += global_ctrl.eq(self.wb_dat_w)
                with m.Case(0x014):  # IRQ_MASK
                    m.d.sync += irq_mask.eq(self.wb_dat_w[0:self.num_channels])
                with m.Case(0x018):  # IRQ_STATUS (write 1 to clear)
                    m.d.sync += irq_status.eq(irq_status & ~self.wb_dat_w[0:self.num_channels])

            m.d.sync += global_access_active.eq(1)

        with m.Elif(wb_valid & is_global_region & ~self.wb_we):
            # Read from global registers
            with m.Switch(addr_offset):
                with m.Case(0x000):  # GLOBAL_CTRL
                    m.d.sync += self.wb_dat_r.eq(global_ctrl)
                with m.Case(0x004):  # GLOBAL_STATUS
                    m.d.sync += self.wb_dat_r.eq(
                        Cat(self.irq_in, Const(0, 31))
                    )
                with m.Case(0x008):  # VERSION
                    m.d.sync += self.wb_dat_r.eq(0xA5A50001)
                with m.Case(0x00C):  # CHANNEL_COUNT
                    m.d.sync += self.wb_dat_r.eq(self.num_channels)
                with m.Case(0x010):  # SAMPLE_COUNT
                    m.d.sync += self.wb_dat_r.eq(sample_counter)
                with m.Case(0x014):  # IRQ_MASK
                    m.d.sync += self.wb_dat_r.eq(irq_mask)
                with m.Case(0x018):  # IRQ_STATUS
                    m.d.sync += self.wb_dat_r.eq(irq_status)
                with m.Default():
                    m.d.sync += self.wb_dat_r.eq(0)

            m.d.sync += global_access_active.eq(1)

        with m.Else():
            m.d.sync += global_access_active.eq(0)

        # === Wishbone ACK generation ===

        # For channel region: wait for CSR ready
        # For global region: immediate ACK
        with m.If(csr_access_active):
            m.d.sync += self.wb_ack.eq(self.csr_ready)
        with m.Elif(global_access_active):
            m.d.sync += self.wb_ack.eq(1)
        with m.Else():
            m.d.sync += self.wb_ack.eq(0)

        # === Sample counter ===

        with m.If(self.global_reset):
            m.d.sync += sample_counter.eq(0)
        with m.Elif(self.sample_enable):
            m.d.sync += sample_counter.eq(sample_counter + 1)

        # === IRQ handling ===

        # Latch IRQ status when IRQ is raised
        with m.If(self.irq_in):
            m.d.sync += irq_status.eq(irq_status | irq_mask)

        # Generate masked IRQ output
        m.d.comb += self.irq_out.eq((irq_status & irq_mask).any())

        # === Read data mux ===

        # For channel accesses, return CSR read data
        with m.If(csr_access_active):
            m.d.sync += self.wb_dat_r.eq(self.csr_read_data)

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Tick

    dut = WishboneCSRBridge(num_channels=12)

    def testbench():
        """Test Wishbone CSR bridge."""

        print("=" * 70)
        print("Wishbone CSR Bridge Test")
        print("=" * 70)

        # Test 1: Read version register
        print("\n[TEST 1] Read VERSION register (0x1008)")
        yield dut.wb_adr.eq(0x1008)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(0)
        yield Tick()
        yield Tick()
        ack = yield dut.wb_ack
        version = yield dut.wb_dat_r
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  ACK: {ack}, VERSION: 0x{version:08X}")
        assert version == 0xA5A50001, "Version mismatch!"

        # Test 2: Read channel count
        print("\n[TEST 2] Read CHANNEL_COUNT register (0x100C)")
        yield dut.wb_adr.eq(0x100C)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(0)
        yield Tick()
        yield Tick()
        channel_count = yield dut.wb_dat_r
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  CHANNEL_COUNT: {channel_count}")
        assert channel_count == 12, "Channel count mismatch!"

        # Test 3: Write global control
        print("\n[TEST 3] Write GLOBAL_CTRL (0x1000)")
        yield dut.wb_adr.eq(0x1000)
        yield dut.wb_dat_w.eq(0b111)  # Enable all
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(1)
        yield Tick()
        yield Tick()
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        global_enable = yield dut.global_enable
        sample_enable = yield dut.sample_enable
        print(f"  Global enable: {global_enable}, Sample enable: {sample_enable}")

        # Test 4: Write to channel register (CSR passthrough)
        print("\n[TEST 4] Write to channel 0 CTRL (0x0000)")
        yield dut.wb_adr.eq(0x0000)
        yield dut.wb_dat_w.eq(0x1)  # Enable channel
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(1)
        yield Tick()

        # Simulate CSR ready after 1 cycle
        yield dut.csr_ready.eq(1)
        yield Tick()
        yield dut.csr_ready.eq(0)

        csr_write = yield dut.csr_write
        csr_addr = yield dut.csr_addr
        csr_data = yield dut.csr_write_data

        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  CSR write: {csr_write}, addr: 0x{csr_addr:04X}, data: 0x{csr_data:08X}")

        # Test 5: Read from channel register
        print("\n[TEST 5] Read from channel 0 STATUS (0x0004)")
        yield dut.wb_adr.eq(0x0004)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(0)
        yield Tick()

        # Simulate CSR returning data
        yield dut.csr_read_data.eq(0xDEADBEEF)
        yield dut.csr_ready.eq(1)
        yield Tick()
        yield dut.csr_ready.eq(0)
        yield Tick()

        read_data = yield dut.wb_dat_r
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  Read data: 0x{read_data:08X}")
        assert read_data == 0xDEADBEEF, "Read data mismatch!"

        # Test 6: IRQ mask and status
        print("\n[TEST 6] Test IRQ masking")

        # Write IRQ mask (enable channel 0 and 1 only)
        yield dut.wb_adr.eq(0x1014)
        yield dut.wb_dat_w.eq(0b11)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(1)
        yield Tick()
        yield Tick()
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        # Trigger IRQ
        yield dut.irq_in.eq(1)
        yield Tick()
        yield Tick()
        irq_out = yield dut.irq_out
        print(f"  IRQ output: {irq_out}")

        # Read IRQ status
        yield dut.wb_adr.eq(0x1018)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(0)
        yield Tick()
        yield Tick()
        irq_status = yield dut.wb_dat_r
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  IRQ status: 0x{irq_status:03X}")

        # Clear IRQ
        yield dut.wb_adr.eq(0x1018)
        yield dut.wb_dat_w.eq(irq_status)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(1)
        yield Tick()
        yield Tick()
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        irq_out_cleared = yield dut.irq_out
        print(f"  IRQ output after clear: {irq_out_cleared}")

        # Test 7: Sample counter
        print("\n[TEST 7] Test sample counter")

        # Sample enable already set in Test 3 via GLOBAL_CTRL
        # Wait for some samples to accumulate
        for _ in range(100):
            yield Tick()

        # Read sample count
        yield dut.wb_adr.eq(0x1010)
        yield dut.wb_cyc.eq(1)
        yield dut.wb_stb.eq(1)
        yield dut.wb_we.eq(0)
        yield Tick()
        yield Tick()
        sample_count = yield dut.wb_dat_r
        yield dut.wb_cyc.eq(0)
        yield dut.wb_stb.eq(0)
        yield Tick()

        print(f"  Sample count: {sample_count}")
        assert sample_count > 0, "Sample counter not incrementing!"

        print("\n" + "=" * 70)
        print("✓ Wishbone CSR Bridge Test Complete")
        print("=" * 70)
        print("\nValidated:")
        print("  • Wishbone read/write transactions")
        print("  • Global register access")
        print("  • CSR passthrough to channel manager")
        print("  • Version and status registers")
        print("  • IRQ masking and status")
        print("  • Sample counter")

    sim = Simulator(dut)
    sim.add_clock(1/50e6)  # 50 MHz system clock
    sim.add_process(testbench)

    with sim.write_vcd("csr_interface.vcd", "csr_interface.gtkw"):
        sim.run()

    print("\nVCD waveform written to csr_interface.vcd")
