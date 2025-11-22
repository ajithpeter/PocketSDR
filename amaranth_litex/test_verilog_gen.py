#!/usr/bin/env python3
"""Test Verilog generation for GNSS baseband."""

import sys
sys.path.insert(0, 'src')

from amaranth.back import verilog
from gnss_baseband import GNSSBaseband

def test_verilog_gen():
    """Test that GNSSBaseband can generate Verilog."""

    print("Testing Verilog generation for GNSSBaseband...")
    print("=" * 60)

    try:
        # Create GNSS baseband with 2 channels
        dut = GNSSBaseband(num_channels=2)

        # Generate Verilog
        # GNSSBaseband uses Wishbone interface, so just convert directly
        output = verilog.convert(dut, ports=[])

        # Write to file
        with open('gnss_baseband.v', 'w') as f:
            f.write(output)

        print("✅ SUCCESS: Verilog generated successfully!")
        print(f"   Output file: gnss_baseband.v")
        print(f"   Size: {len(output)} bytes")
        print(f"   Lines: {output.count(chr(10))} lines")

        # Check for module declaration
        if 'module top' in output:
            print("   Contains: module top declaration")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_verilog_gen()
    sys.exit(0 if success else 1)
