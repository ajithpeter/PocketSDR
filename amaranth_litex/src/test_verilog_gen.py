#!/usr/bin/env python3
"""
Simple test to validate Verilog generation from gnss_baseband.py
without running the full simulation.
"""

import sys
sys.path.insert(0, '.')

from amaranth.back import verilog
from gnss_baseband import GNSSBaseband

print("=" * 70)
print("GNSS Baseband Verilog Generation Test")
print("=" * 70)

try:
    print("\n[1] Instantiating GNSSBaseband module...")
    dut = GNSSBaseband(num_channels=12, fifo_depth=256)
    print("    ✓ Module instantiated successfully")

    print("\n[2] Attempting Verilog conversion...")
    output = verilog.convert(
        dut,
        ports=[
            dut.max2771_iq_data,
            dut.max2771_sample_clk,
            dut.wb_adr,
            dut.wb_dat_w,
            dut.wb_dat_r,
            dut.wb_sel,
            dut.wb_cyc,
            dut.wb_stb,
            dut.wb_we,
            dut.wb_ack,
            dut.irq
        ]
    )

    print("    ✓ Verilog conversion successful")

    print("\n[3] Writing Verilog output to file...")
    with open("gnss_baseband.v", "w") as f:
        f.write(output)

    print("    ✓ Verilog written to gnss_baseband.v")

    # Get file size
    import os
    size = os.path.getsize("gnss_baseband.v")
    print(f"    File size: {size:,} bytes ({size/1024:.1f} KB)")

    print("\n" + "=" * 70)
    print("✓ Verilog Generation Test PASSED")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ Error during Verilog generation:")
    print(f"  {type(e).__name__}: {e}")
    print("\n" + "=" * 70)
    print("✗ Verilog Generation Test FAILED")
    print("=" * 70)
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
