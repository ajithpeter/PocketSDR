#!/usr/bin/env python3
"""
Generate Verilog from Amaranth GPSDO module.

This script converts the Amaranth GPSDO hardware description to Verilog
for integration into LiteX/Migen SoC.

Author: PocketSDR GPSDO Integration
License: BSD 2-Clause
"""

import sys
sys.path.insert(0, '.')

from amaranth.back import verilog
from gpsdo import GPSDO


def generate_gpsdo_verilog(output_file="gpsdo.v", sys_clk_freq=48_000_000):
    """Generate Verilog for GPSDO module."""

    print(f"Generating GPSDO Verilog...")
    print(f"  System clock: {sys_clk_freq / 1e6:.1f} MHz")

    # Create GPSDO instance
    dut = GPSDO(sys_clk_freq=sys_clk_freq)

    # Convert to Verilog
    ports = [
        # GPS time inputs
        dut.tow,
        dut.tow_valid,
        dut.tow_update,

        # Control inputs (CSRs)
        dut.enable,
        dut.reset_integrator,
        dut.kp_shift,
        dut.ki_shift,
        dut.dac_manual,
        dut.manual_mode,

        # Local oscillator input
        dut.local_pps_in,

        # Outputs
        dut.gps_pps_out,
        dut.pps_led,

        # DAC control
        dut.dac_cs,
        dut.dac_clk,
        dut.dac_mosi,

        # Disciplined clock outputs
        dut.clk_10mhz,
        dut.clk_1pps,

        # Status outputs
        dut.phase_error,
        dut.dac_value,
        dut.locked,
        dut.pps_count,
    ]

    # Generate Verilog
    verilog_text = verilog.convert(
        dut,
        ports=ports,
        name="GPSDO"
    )

    # Write to file
    with open(output_file, 'w') as f:
        f.write(verilog_text)

    # Get file size
    import os
    size = os.path.getsize(output_file)

    print(f"✅ Generated: {output_file}")
    print(f"   Size: {size:,} bytes")
    print(f"   Lines: {verilog_text.count(chr(10))}")

    return output_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate GPSDO Verilog")
    parser.add_argument("-o", "--output", default="gpsdo.v",
                       help="Output Verilog file")
    parser.add_argument("-f", "--freq", type=int, default=48,
                       help="System clock frequency in MHz")

    args = parser.parse_args()

    generate_gpsdo_verilog(
        output_file=args.output,
        sys_clk_freq=args.freq * 1_000_000
    )
