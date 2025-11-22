#!/usr/bin/env python3
"""Test that all modules elaborate correctly."""

import sys
sys.path.insert(0, 'src')

from amaranth import Module
from amaranth.hdl import Fragment

def test_module(name, create_func):
    """Test that a module elaborates without errors."""
    try:
        print(f"Testing {name}...", end=" ")
        mod = create_func()
        fragment = Fragment.get(mod, platform=None)
        fragment.prepare()
        print("✅ OK")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def main():
    print("Testing Module Elaboration")
    print("=" * 60)

    results = []

    # Test all modules
    from carrier_nco import CarrierNCO
    results.append(test_module("CarrierNCO", lambda: CarrierNCO()))

    from code_nco import CodeNCO
    results.append(test_module("CodeNCO", lambda: CodeNCO()))

    from correlator import Correlator
    results.append(test_module("Correlator", lambda: Correlator()))

    from gps_l1ca_gen import GPSL1CAGenerator
    results.append(test_module("GPS L1 C/A Generator", lambda: GPSL1CAGenerator()))

    from navic_l5_gen import NavICL5Generator
    results.append(test_module("NavIC L5 Generator", lambda: NavICL5Generator()))

    from max2771_interface import MAX2771Interface
    results.append(test_module("MAX2771 Interface", lambda: MAX2771Interface()))

    from channel_core import ChannelCore
    results.append(test_module("Channel Core", lambda: ChannelCore(channel_id=0)))

    from channel_manager import ChannelManager
    results.append(test_module("Channel Manager (2ch)", lambda: ChannelManager(num_channels=2)))

    from csr_interface import WishboneCSRBridge
    results.append(test_module("Wishbone CSR Bridge", lambda: WishboneCSRBridge(num_channels=2)))

    from gnss_baseband import GNSSBaseband
    results.append(test_module("GNSS Baseband (2ch)", lambda: GNSSBaseband(num_channels=2)))

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} modules passed")

    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
