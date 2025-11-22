"""
Amalthea GNSS Receiver SoC - LiteX top-level integration.

Complete system-on-chip combining:
- VexRiscv RISC-V CPU
- GNSS baseband processor
- UART, SPI, GPIO peripherals
- DDR3/SDRAM controller
- USB interface

Target: Lattice ECP5-45F FPGA

Author: PocketSDR Amaranth Implementation
License: BSD 2-Clause
"""

from migen import *

from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone

from litex.soc.cores.clock import ECP5PLL
from litex.soc.cores.spi import SPIMaster
from litex.soc.cores.gpio import GPIOOut, GPIOIn
from litex.soc.cores.uart import UARTWishbone

from litex.build.generic_platform import Pins, Subsignal, IOStandard

# Import GNSS baseband as pre-built Verilog
# (In production, this would be generated from Amaranth)
from litex.soc.cores import cpu


class AmaltheaGNSSSoC(SoCCore):
    """
    Amalthea GNSS Receiver System-on-Chip.

    Features:
    ---------
    - VexRiscv RISC-V CPU @ 50 MHz
    - 128 KB SRAM
    - GNSS baseband processor (12 channels)
    - UART @ 115200 baud
    - SPI master for MAX2771 configuration
    - GPIO for status LEDs
    - USB FIFO interface (optional)
    - DDR3 SDRAM controller (optional)

    Memory Map:
    -----------
    0x00000000 - 0x0001FFFF: SRAM (128 KB)
    0x10000000 - 0x1000FFFF: UART
    0x20000000 - 0x2000FFFF: SPI
    0x30000000 - 0x3000FFFF: GPIO
    0x40000000 - 0x4000FFFF: GNSS Baseband
    0x40000000 - 0x40000FFF:   Channel registers
    0x40001000 - 0x400010FF:   Global registers
    0xF0000000 - 0xFFFFFFFF: Flash (for future use)

    Parameters
    ----------
    platform : Platform
        LiteX platform object (ECP5 platform)
    sys_clk_freq : int
        System clock frequency (default: 50 MHz)
    with_uart : bool
        Include UART peripheral (default: True)
    with_spi : bool
        Include SPI master (default: True)
    with_gpio : bool
        Include GPIO (default: True)
    """

    def __init__(self, platform, sys_clk_freq=int(50e6), **kwargs):
        """Initialize Amalthea GNSS SoC."""

        # === SoC Core initialization ===

        # Disable integrated ROM (we'll use SRAM only for now)
        kwargs["integrated_rom_size"] = 0
        kwargs["integrated_sram_size"] = 128 * 1024  # 128 KB

        # CPU selection: VexRiscv (minimal variant for resource efficiency)
        kwargs["cpu_type"] = "vexriscv"
        kwargs["cpu_variant"] = "minimal"

        # Initialize SoC core
        SoCCore.__init__(self, platform, sys_clk_freq,
                        ident="Amalthea GNSS Receiver v0.1",
                        ident_version=True,
                        **kwargs)

        # === Clock and Reset ===

        # Create PLL for clock generation
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~platform.request("user_btn_n"))  # Active-low button

        # Input clock from oscillator (typically 25 MHz on ECP5 boards)
        pll.register_clkin(platform.request("clk25"), 25e6)

        # Generate system clock (50 MHz)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

        # === UART ===

        # Standard UART at 115200 baud for console/debug
        # Uses LiteX's built-in UART core (already included in SoCCore)
        # Accessible at 0x10000000

        # === SPI Master for MAX2771 Configuration ===

        self.submodules.spi = SPIMaster(
            pads=platform.request("spi"),
            data_width=8,
            sys_clk_freq=sys_clk_freq,
            spi_clk_freq=int(1e6)  # 1 MHz SPI clock
        )

        # Add to memory map
        self.add_wb_slave(
            mem_decoder(0x20000000),
            self.spi.bus
        )
        self.add_memory_region("spi", 0x20000000, 0x10000, type="io")

        # === GPIO ===

        # GPIO outputs for status LEDs
        leds = platform.request_all("user_led")
        self.submodules.leds = GPIOOut(leds)

        self.add_wb_slave(
            mem_decoder(0x30000000),
            self.leds.bus
        )
        self.add_memory_region("gpio_leds", 0x30000000, 0x10000, type="io")

        # GPIO inputs for user buttons (if available)
        # buttons = platform.request_all("user_btn")
        # self.submodules.buttons = GPIOIn(buttons)

        # === GNSS Baseband Processor ===

        # Instantiate GNSS baseband (12 channels)
        # Note: This would be a Verilog instance in production
        # For now, we describe it as a Wishbone peripheral placeholder

        self.gnss_baseband = gnss_baseband = wishbone.SRAM(
            mem_or_size=8192,  # 8 KB register space placeholder
            read_only=False,
            init=None,
            name="gnss_baseband"
        )
        self.register_mem("gnss", 0x40000000, gnss_baseband.bus, size=0x10000)

        # TODO: Replace with actual GNSS baseband Verilog instantiation
        # from litex.soc.cores.verilog import VerilogModule
        # self.specials += Instance("GNSSBaseband",
        #     i_clk=ClockSignal(),
        #     i_rst=ResetSignal(),
        #     # Wishbone interface
        #     i_wb_adr=...,
        #     i_wb_dat_w=...,
        #     o_wb_dat_r=...,
        #     # MAX2771 interface
        #     i_max2771_iq_data=...,
        #     i_max2771_sample_clk=...,
        #     # IRQ
        #     o_irq=...
        # )

        # === MAX2771 ADC Interface Pins ===

        # Connect MAX2771 to GNSS baseband
        # These pins would be defined in the platform file
        # max2771_pads = platform.request("max2771")
        # self.comb += [
        #     gnss_baseband.max2771_iq_data.eq(max2771_pads.iq_data),
        #     gnss_baseband.max2771_sample_clk.eq(max2771_pads.clkout)
        # ]

        # === Interrupts ===

        # Connect GNSS baseband IRQ to CPU
        # self.comb += self.cpu.interrupt[0].eq(gnss_baseband.irq)

        # === USB Interface (Optional) ===

        # For future: USB FIFO for streaming GNSS data
        # if with_usb:
        #     from litex.soc.cores.usb_fifo import FT245PHYSynchronous
        #     usb_pads = platform.request("usb_fifo")
        #     self.submodules.usb_phy = FT245PHYSynchronous(usb_pads, sys_clk_freq)

        # === DDR3 SDRAM (Optional) ===

        # For future: DDR3 controller for data buffering
        # if with_ddr3:
        #     from litedram.modules import MT41K256M16
        #     from litedram.phy import ECP5DDRPHY
        #     self.submodules.ddrphy = ECP5DDRPHY(
        #         platform.request("ddram"),
        #         sys_clk_freq=sys_clk_freq)
        #     self.add_sdram("sdram",
        #         phy=self.ddrphy,
        #         module=MT41K256M16(sys_clk_freq, "1:2"),
        #         size=0x10000000
        #     )


def add_max2771_pins(platform):
    """
    Add MAX2771 interface pin definitions to platform.

    This is a reference implementation - actual pin assignments
    depend on the specific board layout.
    """

    max2771_ios = [
        ("max2771", 0,
            Subsignal("iq_data", Pins("A1 A2 A3 A4"), IOStandard("LVCMOS33")),
            Subsignal("clkout", Pins("B1"), IOStandard("LVCMOS33")),
            Subsignal("ld", Pins("C1"), IOStandard("LVCMOS33")),  # Lock detect
        ),
    ]

    platform.add_extension(max2771_ios)


def add_spi_pins(platform):
    """Add SPI pin definitions for MAX2771 configuration."""

    spi_ios = [
        ("spi", 0,
            Subsignal("clk", Pins("D1"), IOStandard("LVCMOS33")),
            Subsignal("mosi", Pins("E1"), IOStandard("LVCMOS33")),
            Subsignal("miso", Pins("F1"), IOStandard("LVCMOS33")),
            Subsignal("cs_n", Pins("G1"), IOStandard("LVCMOS33")),
        ),
    ]

    platform.add_extension(spi_ios)


# === Build Script ===

def main():
    """Build Amalthea GNSS SoC for ECP5 platform."""

    from litex.build.lattice import LatticePlatform
    from litex.build.generic_platform import *

    # Define a minimal ECP5 platform for demonstration
    # In production, use actual board platform file
    class MinimalECP5Platform(LatticePlatform):
        default_clk_name = "clk25"
        default_clk_period = 1e9 / 25e6

        def __init__(self):
            # Minimal I/O definitions
            io = [
                ("clk25", 0, Pins("P3"), IOStandard("LVCMOS33")),
                ("user_btn_n", 0, Pins("P4"), IOStandard("LVCMOS33")),
                ("user_led", 0, Pins("E16"), IOStandard("LVCMOS33")),
                ("user_led", 1, Pins("D17"), IOStandard("LVCMOS33")),
                ("user_led", 2, Pins("D18"), IOStandard("LVCMOS33")),
                ("user_led", 3, Pins("E18"), IOStandard("LVCMOS33")),
                ("serial", 0,
                    Subsignal("tx", Pins("L4")),
                    Subsignal("rx", Pins("M1")),
                    IOStandard("LVCMOS33")
                ),
            ]

            LatticePlatform.__init__(self, "LFE5U-45F-6BG381C", io, toolchain="trellis")

    # Create platform
    platform = MinimalECP5Platform()

    # Add custom pin definitions
    add_max2771_pins(platform)
    add_spi_pins(platform)

    # Create SoC
    soc = AmaltheaGNSSSoC(platform, sys_clk_freq=int(50e6))

    # Build SoC
    builder = Builder(soc, output_dir="build/amalthea",
                     csr_csv="build/amalthea/csr.csv")

    builder.build(build_name="amalthea_gnss")

    print("\n" + "=" * 70)
    print("✓ Amalthea GNSS SoC Build Complete")
    print("=" * 70)
    print("\nGenerated files:")
    print("  • build/amalthea/gateware/amalthea_gnss.v  - Verilog netlist")
    print("  • build/amalthea/gateware/amalthea_gnss.bit - FPGA bitstream")
    print("  • build/amalthea/software/bios/bios.elf     - BIOS firmware")
    print("  • build/amalthea/csr.csv                    - Register map")
    print("\nNext steps:")
    print("  1. Program FPGA: openFPGALoader -b ecp5-evn build/amalthea/gateware/amalthea_gnss.bit")
    print("  2. Connect UART and monitor output")
    print("  3. Configure MAX2771 via SPI")
    print("  4. Start GNSS signal acquisition")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Amalthea GNSS SoC")
    parser.add_argument("--build", action="store_true", help="Build the SoC")
    parser.add_argument("--sim", action="store_true", help="Run simulation")
    parser.add_argument("--load", action="store_true", help="Load bitstream to FPGA")

    args = parser.parse_args()

    if args.build:
        main()
    elif args.sim:
        print("Simulation not yet implemented")
        print("Use individual module tests:")
        print("  python3 gnss_baseband.py")
        print("  python3 channel_core.py")
        print("  python3 channel_manager.py")
    elif args.load:
        import os
        os.system("openFPGALoader -b ecp5-evn build/amalthea/gateware/amalthea_gnss.bit")
    else:
        print(__doc__)
        print("\nUsage:")
        print("  python3 amalthea_soc.py --build    # Build the SoC")
        print("  python3 amalthea_soc.py --sim      # Run simulation")
        print("  python3 amalthea_soc.py --load     # Load to FPGA")
        print("\nFor help: python3 amalthea_soc.py --help")
