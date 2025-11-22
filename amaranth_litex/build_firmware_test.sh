#!/bin/bash
# Build GNSS Firmware with RISC-V GCC

export PATH="/home/user/tools/xpack-riscv-none-elf-gcc-13.2.0-2/bin:$PATH"

CD=/home/user/PocketSDR/amaranth_litex/firmware
BUILD=$CD/build

echo "======================================================================"
echo "GNSS FIRMWARE BUILD TEST"
echo "======================================================================"

mkdir -p $BUILD

echo ""
echo "[1/5] Compiling gnss_csr.c..."
riscv-none-elf-gcc -march=rv32im -mabi=ilp32 -O2 -g -Wall -Wextra \
    -ffunction-sections -fdata-sections -Iinclude \
    -c src/gnss_csr.c -o $BUILD/gnss_csr.o

if [ $? -eq 0 ]; then
    echo "✅ gnss_csr.o created"
else
    echo "❌ Failed to compile gnss_csr.c"
    exit 1
fi

echo ""
echo "[2/5] Compiling gnss_tracking.c..."
riscv-none-elf-gcc -march=rv32im -mabi=ilp32 -O2 -g -Wall -Wextra \
    -ffunction-sections -fdata-sections -Iinclude \
    -c src/gnss_tracking.c -o $BUILD/gnss_tracking.o

if [ $? -eq 0 ]; then
    echo "✅ gnss_tracking.o created"
else
    echo "❌ Failed to compile gnss_tracking.c"
    exit 1
fi

echo ""
echo "[3/5] Compiling gnss_nav.c..."
riscv-none-elf-gcc -march=rv32im -mabi=ilp32 -O2 -g -Wall -Wextra \
    -ffunction-sections -fdata-sections -Iinclude \
    -c src/gnss_nav.c -o $BUILD/gnss_nav.o

if [ $? -eq 0 ]; then
    echo "✅ gnss_nav.o created"
else
    echo "❌ Failed to compile gnss_nav.c"
    exit 1
fi

echo ""
echo "[4/5] Compiling gnss_pvt.c..."
riscv-none-elf-gcc -march=rv32im -mabi=ilp32 -O2 -g -Wall -Wextra \
    -ffunction-sections -fdata-sections -Iinclude \
    -c src/gnss_pvt.c -o $BUILD/gnss_pvt.o

if [ $? -eq 0 ]; then
    echo "✅ gnss_pvt.o created"
else
    echo "❌ Failed to compile gnss_pvt.c"
    exit 1
fi

echo ""
echo "[5/5] Compiling main.c..."
riscv-none-elf-gcc -march=rv32im -mabi=ilp32 -O2 -g -Wall -Wextra \
    -ffunction-sections -fdata-sections -Iinclude \
    -c src/main.c -o $BUILD/main.o

if [ $? -eq 0 ]; then
    echo "✅ main.o created"
else
    echo "❌ Failed to compile main.c"
    exit 1
fi

echo ""
echo "======================================================================"
echo "BUILD SUMMARY"
echo "======================================================================"
echo ""
echo "Object files created:"
ls -lh $BUILD/*.o | awk '{printf "  %-20s %8s\n", $9, $5}'

total_size=$(du -sh $BUILD | awk '{print $1}')
echo ""
echo "Total build size: $total_size"

echo ""
echo "✅ ALL FIRMWARE FILES COMPILED SUCCESSFULLY"
echo ""
echo "Note: Linking requires a linker script (firmware.ld) which would be"
echo "      provided by the LiteX SoC build system."
echo ""
echo "Status: RISC-V GCC toolchain fully functional!"
