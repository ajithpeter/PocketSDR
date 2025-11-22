"""
LiteX GPSDO Core Wrapper

Provides Wishbone interface to Amaranth-generated GPSDO Verilog module.

Memory Map (relative to base address):
-----------------------------------
0x00: Control Register
      [0]   - Enable GPSDO
      [1]   - Reset integrator
      [2]   - Manual mode

0x04: Status Register (read-only)
      [0]   - Locked
      [1]   - TOW valid
      [2]   - PPS active

0x08: GPS Time of Week (ms)

0x0C: Kp Shift (proportional gain)
      [7:0] - Kp shift value (8-16)

0x10: Ki Shift (integral gain)
      [7:0] - Ki shift value (16-24)

0x14: Phase Error (ns, signed)
      [31:0] - Current phase error

0x18: DAC Value (read-only)
      [15:0] - Current DAC control value

0x1C: PPS Count (read-only)
      [31:0] - Number of PPS pulses

0x20: Manual DAC Value
      [15:0] - Manual DAC setting (when manual mode enabled)

Author: PocketSDR GPSDO Integration
License: BSD 2-Clause
"""

from migen import *
from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *


class GPSDO_Core(Module, AutoCSR):
    """
    LiteX wrapper for GPSDO Verilog module.

    Provides CSR interface for configuration and monitoring.

    Parameters
    ----------
    platform : Platform
        LiteX platform object (for adding Verilog sources)
    sys_clk_freq : int
        System clock frequency in Hz
    """

    def __init__(self, platform, sys_clk_freq=48_000_000):
        """Initialize GPSDO core."""

        # === CSR Registers ===

        # Control register
        self.control = CSRStorage(3, fields=[
            CSRField("enable", size=1, description="Enable GPSDO"),
            CSRField("reset_int", size=1, description="Reset integrator", pulse=True),
            CSRField("manual_mode", size=1, description="Manual DAC mode"),
        ])

        # Status register
        self.status = CSRStatus(3, fields=[
            CSRField("locked", size=1, description="PLL locked"),
            CSRField("tow_valid", size=1, description="GPS TOW valid"),
            CSRField("pps_active", size=1, description="PPS pulse active"),
        ])

        # GPS Time of Week
        self.tow = CSRStorage(32, description="GPS Time of Week (ms)")
        self.tow_update = CSRStorage(1, description="TOW update strobe")

        # PI controller gains
        self.kp_shift = CSRStorage(8, reset=8, description="Proportional gain shift")
        self.ki_shift = CSRStorage(8, reset=16, description="Integral gain shift")

        # Phase error (signed)
        self.phase_error = CSRStatus(32, description="Phase error (ns, signed)")

        # DAC value
        self.dac_value = CSRStatus(16, description="Current DAC value")

        # PPS count
        self.pps_count = CSRStatus(32, description="PPS pulse count")

        # Manual DAC value
        self.dac_manual = CSRStorage(16, reset=32768, description="Manual DAC value")

        # === External Pins ===

        # Request pins from platform
        # DAC SPI interface
        dac_pads = platform.request("gpsdo_dac") if hasattr(platform, 'request') else None

        # PPS outputs
        pps_pads = platform.request("gpsdo_pps") if hasattr(platform, 'request') else None

        # Local oscillator input
        local_pps = platform.request("gpsdo_local_pps") if hasattr(platform, 'request') else Signal()

        # === Internal Signals ===

        # GPSDO module signals
        gps_pps_out = Signal()
        pps_led = Signal()
        dac_cs = Signal(reset=1)
        dac_clk = Signal()
        dac_mosi = Signal()
        clk_10mhz = Signal()
        clk_1pps = Signal()
        phase_error_int = Signal(32)
        dac_value_int = Signal(16)
        locked = Signal()
        pps_count_int = Signal(32)

        # === Verilog Instance ===

        # Add Verilog source to platform
        if platform is not None and hasattr(platform, 'add_source'):
            import os
            gpsdo_v_path = os.path.join(
                os.path.dirname(__file__),
                "../build/gpsdo.v"
            )
            platform.add_source(gpsdo_v_path)

        # Instantiate GPSDO Verilog module
        self.specials += Instance("GPSDO",
            # Clock and reset
            i_clk=ClockSignal("sys"),
            i_rst=ResetSignal("sys"),

            # GPS time inputs
            i_tow=self.tow.storage,
            i_tow_valid=self.tow.storage != 0,  # Simple validity check
            i_tow_update=self.tow_update.storage,

            # Control inputs
            i_enable=self.control.fields.enable,
            i_reset_integrator=self.control.fields.reset_int,
            i_kp_shift=self.kp_shift.storage,
            i_ki_shift=self.ki_shift.storage,
            i_dac_manual=self.dac_manual.storage,
            i_manual_mode=self.control.fields.manual_mode,

            # Local oscillator input
            i_local_pps_in=local_pps,

            # Outputs
            o_gps_pps_out=gps_pps_out,
            o_pps_led=pps_led,

            # DAC control
            o_dac_cs=dac_cs,
            o_dac_clk=dac_clk,
            o_dac_mosi=dac_mosi,

            # Disciplined clock outputs
            o_clk_10mhz=clk_10mhz,
            o_clk_1pps=clk_1pps,

            # Status outputs
            o_phase_error=phase_error_int,
            o_dac_value=dac_value_int,
            o_locked=locked,
            o_pps_count=pps_count_int,
        )

        # === Connect Status Registers ===

        self.comb += [
            self.status.fields.locked.eq(locked),
            self.status.fields.tow_valid.eq(self.tow.storage != 0),
            self.status.fields.pps_active.eq(gps_pps_out),

            self.phase_error.status.eq(phase_error_int),
            self.dac_value.status.eq(dac_value_int),
            self.pps_count.status.eq(pps_count_int),
        ]

        # === Connect External Pins ===

        if dac_pads is not None:
            self.comb += [
                dac_pads.cs.eq(dac_cs),
                dac_pads.clk.eq(dac_clk),
                dac_pads.mosi.eq(dac_mosi),
            ]

        if pps_pads is not None:
            self.comb += [
                pps_pads.gps_pps.eq(gps_pps_out),
                pps_pads.led.eq(pps_led),
                pps_pads.clk_1pps.eq(clk_1pps),
            ]

        # Store signals for SoC-level connections
        self.gps_pps_out = gps_pps_out
        self.pps_led = pps_led
        self.dac_cs = dac_cs
        self.dac_clk = dac_clk
        self.dac_mosi = dac_mosi
        self.clk_10mhz = clk_10mhz
        self.clk_1pps = clk_1pps
        self.local_pps_in = local_pps

    def update_time(self, tow_ms):
        """
        Update GPS time (from firmware/PVT solver).

        This would be called from the PVT solver when a new
        time solution is available.

        Parameters
        ----------
        tow_ms : int
            GPS Time of Week in milliseconds
        """
        # This is a placeholder - actual implementation would
        # write to CSR registers from firmware
        pass


# Platform definitions for GPSDO pins
def add_gpsdo_pins(io):
    """
    Add GPSDO pin definitions to platform I/O.

    Parameters
    ----------
    io : list
        Platform I/O list to append to

    Returns
    -------
    io : list
        Updated I/O list with GPSDO pins
    """
    from litex.build.generic_platform import Pins, Subsignal, IOStandard

    gpsdo_io = [
        # GPSDO DAC SPI interface
        ("gpsdo_dac", 0,
            Subsignal("cs", Pins("GPSDO_DAC_CS")),     # Chip select
            Subsignal("clk", Pins("GPSDO_DAC_CLK")),   # SPI clock
            Subsignal("mosi", Pins("GPSDO_DAC_MOSI")), # SPI data
            IOStandard("LVCMOS33")
        ),

        # GPSDO PPS outputs
        ("gpsdo_pps", 0,
            Subsignal("gps_pps", Pins("GPSDO_GPS_PPS")),    # GPS 1PPS out
            Subsignal("led", Pins("GPSDO_PPS_LED")),        # PPS LED
            Subsignal("clk_1pps", Pins("GPSDO_CLK_1PPS")),  # Disciplined 1PPS
            IOStandard("LVCMOS33")
        ),

        # Local oscillator 1PPS input
        ("gpsdo_local_pps", 0, Pins("GPSDO_LOCAL_PPS"), IOStandard("LVCMOS33")),
    ]

    return io + gpsdo_io


if __name__ == "__main__":
    """Test GPSDO core generation."""

    print("GPSDO LiteX Core Wrapper")
    print("=" * 60)
    print("\nCSR Map:")
    print("  0x00: Control (enable, reset_int, manual_mode)")
    print("  0x04: Status (locked, tow_valid, pps_active)")
    print("  0x08: GPS TOW (ms)")
    print("  0x0C: TOW Update Strobe")
    print("  0x10: Kp Shift")
    print("  0x14: Ki Shift")
    print("  0x18: Phase Error (ns)")
    print("  0x1C: DAC Value")
    print("  0x20: PPS Count")
    print("  0x24: Manual DAC Value")
    print("\nExternal Pins:")
    print("  DAC SPI: CS, CLK, MOSI")
    print("  PPS: GPS_PPS, LED, CLK_1PPS")
    print("  Input: LOCAL_PPS")
