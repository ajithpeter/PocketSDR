#!/usr/bin/env python3
"""Complete build verification with OSS CAD Suite and RISC-V GCC."""

import sys
import subprocess
import os

# Set up paths
os.environ['PATH'] = "/home/user/tools/oss-cad-suite/bin:" + \
                     "/home/user/tools/xpack-riscv-none-elf-gcc-13.2.0-2/bin:" + \
                     os.environ.get('PATH', '')

sys.path.insert(0, 'src')

print("="*70)
print("COMPLETE BUILD VERIFICATION")
print("="*70)

# Test 1: Verilog Generation with Yosys
print("\n[TEST 1] Verilog Generation")
print("-"*70)

try:
    from amaranth.back import verilog
    from gnss_baseband import GNSSBaseband

    print("Creating GNSS Baseband (2 channels)...")
    dut = GNSSBaseband(num_channels=2)

    print("Generating Verilog with Yosys...")
    output = verilog.convert(dut, ports=[])

    with open('/tmp/gnss_baseband_test.v', 'w') as f:
        f.write(output)

    lines = output.count('\n')
    size = len(output)

    print(f"✅ SUCCESS: Verilog generated")
    print(f"   Output: /tmp/gnss_baseband_test.v")
    print(f"   Size: {size:,} bytes ({lines:,} lines)")

    # Check for key Verilog components
    if 'module top' in output:
        print("   ✅ Contains module definition")
    if 'always @' in output:
        print("   ✅ Contains sequential logic")
    if 'assign' in output:
        print("   ✅ Contains combinational logic")

    test1_pass = True
except Exception as e:
    print(f"❌ FAIL: {e}")
    test1_pass = False

# Test 2: Firmware Build with RISC-V GCC
print("\n[TEST 2] Firmware Build")
print("-"*70)

try:
    # Create a simple test firmware
    test_c = """
#include <stdint.h>

volatile uint32_t *const UART = (uint32_t *)0x80000000;
volatile uint32_t *const LED = (uint32_t *)0x80001000;

void main(void) {
    uint32_t count = 0;

    while(1) {
        *LED = count;
        *UART = count;
        count++;
    }
}

void _start(void) {
    main();
}
"""

    with open('/tmp/test_firmware.c', 'w') as f:
        f.write(test_c)

    print("Compiling test firmware...")
    result = subprocess.run([
        'riscv-none-elf-gcc',
        '-march=rv32im',
        '-mabi=ilp32',
        '-O2',
        '-nostdlib',
        '-ffreestanding',
        '-Wl,-Ttext=0x0',
        '-o', '/tmp/test_firmware.elf',
        '/tmp/test_firmware.c'
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ SUCCESS: Firmware compiled")

        # Get binary info
        result = subprocess.run([
            'riscv-none-elf-size',
            '/tmp/test_firmware.elf'
        ], capture_output=True, text=True)

        print(f"   Binary info:")
        for line in result.stdout.strip().split('\n'):
            print(f"   {line}")

        # Create binary
        subprocess.run([
            'riscv-none-elf-objcopy',
            '-O', 'binary',
            '/tmp/test_firmware.elf',
            '/tmp/test_firmware.bin'
        ])

        bin_size = os.path.getsize('/tmp/test_firmware.bin')
        print(f"   Binary: {bin_size} bytes")

        test2_pass = True
    else:
        print(f"❌ FAIL: Compilation failed")
        print(result.stderr)
        test2_pass = False

except Exception as e:
    print(f"❌ FAIL: {e}")
    import traceback
    traceback.print_exc()
    test2_pass = False

# Test 3: Build actual GNSS firmware
print("\n[TEST 3] GNSS Firmware Build")
print("-"*70)

try:
    print("Attempting to build GNSS firmware...")

    # Update Makefile to use the correct toolchain
    result = subprocess.run([
        'make',
        'clean'
    ], cwd='/home/user/PocketSDR/amaranth_litex/firmware',
       capture_output=True, text=True)

    result = subprocess.run([
        'make',
        'CC=riscv-none-elf-gcc',
        'OBJCOPY=riscv-none-elf-objcopy',
        'SIZE=riscv-none-elf-size',
        'all'
    ], cwd='/home/user/PocketSDR/amaranth_litex/firmware',
       capture_output=True, text=True, timeout=60)

    if result.returncode == 0:
        print("✅ SUCCESS: GNSS firmware built")
        # Check for output files
        if os.path.exists('/home/user/PocketSDR/amaranth_litex/firmware/build/gnss_firmware.elf'):
            size = os.path.getsize('/home/user/PocketSDR/amaranth_litex/firmware/build/gnss_firmware.elf')
            print(f"   ELF size: {size:,} bytes")

        test3_pass = True
    else:
        print("⚠️  PARTIAL: Build attempted (may need linker script)")
        print("   Stdout:", result.stdout[:500])
        print("   Stderr:", result.stderr[:500])
        test3_pass = False

except subprocess.TimeoutExpired:
    print("⚠️  TIMEOUT: Build took too long")
    test3_pass = False
except Exception as e:
    print(f"⚠️  ERROR: {e}")
    test3_pass = False

# Summary
print("\n" + "="*70)
print("BUILD VERIFICATION SUMMARY")
print("="*70)

tests = [
    ("Verilog Generation (Yosys)", test1_pass),
    ("Firmware Compilation (RISC-V GCC)", test2_pass),
    ("GNSS Firmware Build", test3_pass),
]

passed = sum(1 for _, p in tests if p)
total = len(tests)

for name, passed_test in tests:
    status = "✅ PASS" if passed_test else "❌ FAIL"
    print(f"{status}  {name}")

print(f"\n{passed}/{total} tests passed")

if test1_pass and test2_pass:
    print("\n✅ CORE BUILD TOOLS WORKING")
    print("   - Yosys can generate Verilog")
    print("   - RISC-V GCC can compile firmware")
    print("\nStatus: Ready for FPGA development!")
elif test1_pass:
    print("\n✅ VERILOG GENERATION WORKING")
    print("⚠️  Firmware build needs configuration")
elif test2_pass:
    print("\n✅ FIRMWARE COMPILATION WORKING")
    print("⚠️  Verilog generation needs attention")
else:
    print("\n❌ BUILD VERIFICATION FAILED")
    print("   Review errors above")

sys.exit(0 if (test1_pass and test2_pass) else 1)
