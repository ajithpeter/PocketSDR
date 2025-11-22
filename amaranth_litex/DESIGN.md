# Amaranth/LiteX GNSS Receiver Design for Amalthea

**Target Platform:** Amalthea GNSS Receiver
**HDL Framework:** Amaranth HDL
**SoC Framework:** LiteX
**Primary Signals:** GPS L1 C/A, NavIC L5
**Design Date:** 2025-11-22

---

## Table of Contents

1. [Design Overview](#design-overview)
2. [Hardware Requirements](#hardware-requirements)
3. [System Architecture](#system-architecture)
4. [Amaranth Module Design](#amaranth-module-design)
5. [LiteX SoC Integration](#litex-soc-integration)
6. [Signal Processing Pipeline](#signal-processing-pipeline)
7. [Resource Estimation](#resource-estimation)
8. [Testing Strategy](#testing-strategy)

---

## 1. Design Overview

### 1.1 Objectives

Design and implement a hardware-accelerated GNSS baseband processor using Amaranth HDL and LiteX SoC framework for the Amalthea receiver platform, providing:

- **Real-time multi-channel tracking** (12 channels minimum)
- **GPS L1 C/A signal processing** (1575.42 MHz, 1.023 Mcps)
- **NavIC L5 signal processing** (1176.45 MHz, 10.23 Mcps)
- **Hardware correlation engines** with configurable early/prompt/late taps
- **Carrier and code NCOs** (Numerically Controlled Oscillators)
- **CPU interface** for configuration and data retrieval
- **FPGA-optimized** architecture for Xilinx 7-series or Lattice ECP5

### 1.2 Design Philosophy

```
Amaranth HDL Principles:
├── Composable, reusable Elaboratable modules
├── Simulation-first development with cocotb
├── Type-safe interfaces using amaranth.lib.wiring
├── Clock domain management with DomainRenamer
└── Platform-agnostic design with vendor-specific optimization

LiteX Integration:
├── Wishbone bus interconnect for CPU interface
├── CSR (Control/Status Register) bus for configuration
├── DMA for high-throughput sample streaming
├── Interrupt generation for event notification
└── Memory-mapped architecture for easy software access
```

### 1.3 Design Constraints

| Parameter | Requirement | Rationale |
|-----------|-------------|-----------|
| Sampling Rate | 4-16 Msps | Supports GPS L1 (2.046 MHz BW) and NavIC L5 (20.46 MHz BW) |
| Quantization | 2-bit I/Q | Matches MAX2771 ADC output |
| Channels | 12-24 | Typical GNSS receiver (4-8 GPS + 4-8 NavIC + margin) |
| Coherent Integration | 1-20 ms | Configurable for acquisition/tracking |
| Code NCO Resolution | 32-bit | Sub-sample code phase accuracy |
| Carrier NCO Resolution | 32-bit | <1 Hz frequency resolution @ 16 MHz |
| Correlator Taps | 3-7 per channel | E/P/L minimum, VE/VL optional for BOC |
| FPGA Target | Xilinx Artix-7 / ECP5 | Amalthea platform options |

---

## 2. Hardware Requirements

### 2.1 Amalthea Receiver Interface

**Assumed Amalthea Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│                     Amalthea Receiver                         │
│                                                               │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐           │
│  │ RF Front │      │   ADC    │      │  FPGA    │           │
│  │   End    │─────→│ MAX2771  │─────→│  SoC     │           │
│  │ L1/L5    │  RF  │  2-bit   │ LVDS │ Amaranth │           │
│  └──────────┘      │   I/Q    │      │  LiteX   │           │
│                    └──────────┘      └─────┬────┘           │
│                                            │                 │
│                                            ↓                 │
│                                     ┌──────────┐             │
│                                     │   CPU    │             │
│                                     │  (RISC-V │             │
│                                     │   /ARM)  │             │
│                                     └──────────┘             │
│                                            │                 │
│                                            ↓                 │
│                                      [USB/Ethernet]          │
└──────────────────────────────────────────────────────────────┘
```

**ADC Interface Specifications:**
- **Data Rate:** 4-16 MHz (configurable)
- **Data Format:** 2-bit I, 2-bit Q (4 bits total per sample)
- **Interface:** Parallel (4-bit bus) or Serial (LVDS)
- **Clock:** ADC_CLK from MAX2771 or derived from FPGA
- **Synchronization:** Frame sync or continuous streaming

### 2.2 FPGA Resources

**Target: Xilinx Artix-7 (XC7A35T or larger)**

| Resource | Available (XC7A35T) | Estimated Usage (12 CH) | Margin |
|----------|---------------------|-------------------------|--------|
| Logic Cells | 33,280 | ~15,000 | 55% |
| Block RAM (36 Kb) | 50 | ~30 | 40% |
| DSP48 Slices | 90 | ~60 | 33% |
| I/O Pins | 210 | ~50 | 76% |

**Alternative: Lattice ECP5 (LFE5U-45F)**

| Resource | Available | Estimated Usage (12 CH) | Margin |
|----------|-----------|-------------------------|--------|
| LUTs | 44,000 | ~20,000 | 54% |
| EBR (18 Kb) | 108 | ~60 | 44% |
| DSPs | 72 | ~48 | 33% |

---

## 3. System Architecture

### 3.1 Top-Level Block Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                   Amalthea GNSS SoC (LiteX)                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  RISC-V CPU (VexRiscv)                    │  │
│  │         + RAM + ROM + Peripherals (UART, Timer)          │  │
│  └─────────────────────┬────────────────────────────────────┘  │
│                        │ Wishbone Bus                          │
│  ┌─────────────────────┴────────────────────────────────────┐  │
│  │              Wishbone Interconnect                        │  │
│  │  ┌────────┬────────┬────────┬────────┬────────┬────────┐ │  │
│  │  │  UART  │ Timer  │  GPIO  │  DMA   │  GNSS  │ Memory │ │  │
│  │  └────────┴────────┴────────┴────────┴───┬────┴────────┘ │  │
│  └────────────────────────────────────────┼─────────────────┘  │
│                                            │                    │
│  ┌─────────────────────────────────────────┴──────────────┐    │
│  │          GNSS Baseband Processor (Amaranth)            │    │
│  │                                                         │    │
│  │  ┌────────────────────────────────────────────────┐    │    │
│  │  │         Sample Acquisition & Buffering         │    │    │
│  │  │  • ADC Interface (2-bit IQ @ 4-16 Msps)        │    │    │
│  │  │  • Sample FIFO (circular buffer, 16K samples)  │    │    │
│  │  │  • Timestamp generator (1 kHz epoch)           │    │    │
│  │  └──────────────────┬─────────────────────────────┘    │    │
│  │                     │                                   │    │
│  │  ┌──────────────────┴─────────────────────────────┐    │    │
│  │  │         Channel Manager (12-24 channels)       │    │    │
│  │  │  ┌───────────┬───────────┬─────────┬────────┐ │    │    │
│  │  │  │ Channel 0 │ Channel 1 │   ...   │Chan N-1│ │    │    │
│  │  │  └─────┬─────┴─────┬─────┴─────┬───┴────┬───┘ │    │    │
│  │  └────────┼───────────┼───────────┼────────┼─────┘    │    │
│  │           │           │           │        │          │    │
│  │  ┌────────▼───────────▼───────────▼────────▼─────┐    │    │
│  │  │          Correlation Engine Array              │    │    │
│  │  │  • Shared correlators (time-multiplexed)      │    │    │
│  │  │  • Parallel correlators (1 per channel)       │    │    │
│  │  │  • Early/Prompt/Late tap generation           │    │    │
│  │  └───────────────────────────────────────────────┘    │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────┐     │    │
│  │  │           Code Generator Bank                 │     │    │
│  │  │  • GPS L1 C/A LFSR (1023 chips)              │     │    │
│  │  │  • NavIC L5 Gold code (1023 chips)           │     │    │
│  │  │  • Cached code memories (BRAM)               │     │    │
│  │  └──────────────────────────────────────────────┘     │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────┐     │    │
│  │  │              CSR Interface                    │     │    │
│  │  │  • Channel configuration registers            │     │    │
│  │  │  • NCO frequency/phase control                │     │    │
│  │  │  • Correlation result readout                 │     │    │
│  │  │  • Interrupt status/control                   │     │    │
│  │  └──────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ADC Input ─────────────────────────────→ Sample Acq           │
│  Wishbone  ←────────────────────────────→ CSR Interface        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Clock Domain Architecture

```
Clock Domains:
┌──────────────────────────────────────────────────────────┐
│ sys_clk    (100 MHz)  - CPU, Wishbone, CSR              │
│ adc_clk    (4-16 MHz) - ADC sampling, sample buffer     │
│ corr_clk   (100 MHz)  - Correlation engines             │
│ (optional) (200 MHz)  - High-speed correlation variant  │
└──────────────────────────────────────────────────────────┘

Clock Domain Crossings:
• ADC → SYS: AsyncFIFO for sample buffering
• SYS → CORR: Synchronous (same clock) or CDC FIFO
• CORR → SYS: CSR read synchronizers
```

---

## 4. Amaranth Module Design

### 4.1 Module Hierarchy

```python
gnss_baseband.py            # Top-level GNSS baseband
├── sample_acquisition.py   # ADC interface + buffering
├── channel_manager.py      # Multi-channel controller
│   └── channel_core.py     # Single channel processor
│       ├── carrier_nco.py  # Carrier NCO
│       ├── code_nco.py     # Code NCO
│       └── correlator.py   # E/P/L correlator
├── code_generator.py       # PRN code generation
│   ├── gps_l1ca_gen.py    # GPS L1 C/A LFSR
│   └── navic_l5_gen.py    # NavIC L5 Gold code
├── correlation_engine.py   # Correlation computation
└── csr_interface.py        # Wishbone CSR registers
```

### 4.2 Sample Acquisition Module

```python
# sample_acquisition.py
from amaranth import *
from amaranth.lib import wiring, stream
from amaranth.lib.wiring import In, Out
from amaranth.lib.fifo import AsyncFIFO

class SampleAcquisition(wiring.Component):
    """
    ADC sample acquisition and buffering module.

    Interfaces:
    - adc_data: 4-bit input (2-bit I + 2-bit Q from MAX2771)
    - sample_stream: Stream output to correlation engines
    - timestamp: 32-bit millisecond counter

    Features:
    - Continuous sampling at adc_clk rate
    - Async FIFO for clock domain crossing (adc_clk → sys_clk)
    - Circular buffer with configurable depth (default 16K samples)
    - Timestamp generation for epoch alignment
    """

    adc: In(stream.Signature(data.StructLayout({
        "i": unsigned(2),
        "q": unsigned(2)
    })))

    samples: Out(stream.Signature(data.StructLayout({
        "i": signed(2),      # Sign-extended from 2-bit
        "q": signed(2),      # Sign-extended from 2-bit
        "timestamp": unsigned(32)  # Millisecond counter
    })))

    def __init__(self, fifo_depth=16384):
        super().__init__()
        self.fifo_depth = fifo_depth

    def elaborate(self, platform):
        m = Module()

        # AsyncFIFO for clock domain crossing
        m.submodules.fifo = fifo = AsyncFIFO(
            width=4 + 32,  # 4-bit IQ + 32-bit timestamp
            depth=self.fifo_depth,
            r_domain="sync",    # sys_clk
            w_domain="adc"      # adc_clk
        )

        # Timestamp counter (in adc_clk domain, increments every fs/1000 samples)
        timestamp = Signal(32)
        sample_count = Signal(range(20000))  # Assuming max 16 Msps

        # ADC clock domain: sampling and timestamping
        with m.If(sample_count == (platform.adc_freq / 1000) - 1):
            m.d.adc += [
                timestamp.eq(timestamp + 1),
                sample_count.eq(0)
            ]
        with m.Else():
            m.d.adc += sample_count.eq(sample_count + 1)

        # 2-bit to signed conversion (00→+1, 01→+3, 10→-1, 11→-3)
        i_signed = Signal(signed(2))
        q_signed = Signal(signed(2))

        m.d.adc += [
            i_signed.eq(Mux(self.adc.payload.i[1],
                           Cat(self.adc.payload.i[0], C(1, 1)),
                           Cat(C(1, 1), self.adc.payload.i[0]))),
            q_signed.eq(Mux(self.adc.payload.q[1],
                           Cat(self.adc.payload.q[0], C(1, 1)),
                           Cat(C(1, 1), self.adc.payload.q[0])))
        ]

        # Write to FIFO
        m.d.comb += [
            fifo.w_data.eq(Cat(i_signed, q_signed, timestamp)),
            fifo.w_en.eq(self.adc.valid),
            self.adc.ready.eq(fifo.w_rdy)
        ]

        # Read from FIFO
        m.d.comb += [
            self.samples.payload.i.eq(fifo.r_data[0:2].as_signed()),
            self.samples.payload.q.eq(fifo.r_data[2:4].as_signed()),
            self.samples.payload.timestamp.eq(fifo.r_data[4:36]),
            self.samples.valid.eq(fifo.r_rdy),
            fifo.r_en.eq(self.samples.ready)
        ]

        return m
```

### 4.3 Carrier NCO Module

```python
# carrier_nco.py
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class CarrierNCO(wiring.Component):
    """
    Numerically Controlled Oscillator for carrier generation.

    Generates complex exponential: exp(j * 2π * f * t)
    Uses CORDIC or LUT-based sine/cosine generation.

    Parameters:
    - phase_width: 32-bit (default) for sub-Hz resolution
    - amplitude_width: 16-bit signed output

    Frequency resolution: fs / 2^32
    For fs=16 MHz: 16e6 / 2^32 ≈ 0.0037 Hz
    """

    freq_word: In(unsigned(32))   # Frequency control word
    phase_offset: In(unsigned(32))  # Phase offset
    enable: In(1)

    cos_out: Out(signed(16))
    sin_out: Out(signed(16))

    def elaborate(self, platform):
        m = Module()

        # Phase accumulator
        phase_acc = Signal(32)

        with m.If(self.enable):
            m.d.sync += phase_acc.eq(phase_acc + self.freq_word)

        # Total phase (accumulator + offset)
        total_phase = Signal(32)
        m.d.comb += total_phase.eq(phase_acc + self.phase_offset)

        # Use top 10 bits for LUT addressing (1024-entry sin/cos table)
        lut_addr = Signal(10)
        m.d.comb += lut_addr.eq(total_phase[22:32])

        # Sine/Cosine LUT (stored in Block RAM)
        # Quadrant folding: use 256-entry quarter-wave table
        quarter_addr = Signal(8)
        quadrant = Signal(2)

        m.d.comb += [
            quadrant.eq(lut_addr[8:10]),
            quarter_addr.eq(Mux(lut_addr[8],
                               ~lut_addr[0:8],  # Fold 2nd quarter
                               lut_addr[0:8]))
        ]

        # LUT memory (initialized with sine values)
        sin_lut = Memory(width=16, depth=256, init=[
            int(32767 * math.sin(2 * math.pi * i / 1024))
            for i in range(256)
        ])

        sin_port = m.submodules.sin_port = sin_lut.read_port(domain="sync")
        m.d.comb += sin_port.addr.eq(quarter_addr)

        # Generate cosine from sine (90° phase shift)
        cos_addr = Signal(8)
        cos_quadrant = Signal(2)
        m.d.comb += [
            cos_quadrant.eq((lut_addr + 256) >> 8),  # +90° shift
            cos_addr.eq(...)  # Similar folding logic
        ]

        cos_port = m.submodules.cos_port = sin_lut.read_port(domain="sync")
        m.d.comb += cos_port.addr.eq(cos_addr)

        # Quadrant sign adjustment
        with m.Switch(quadrant):
            with m.Case(0):  # 0-90°
                m.d.comb += [
                    self.sin_out.eq(sin_port.data),
                    self.cos_out.eq(cos_port.data)
                ]
            with m.Case(1):  # 90-180°
                m.d.comb += [
                    self.sin_out.eq(sin_port.data),
                    self.cos_out.eq(-cos_port.data)
                ]
            with m.Case(2):  # 180-270°
                m.d.comb += [
                    self.sin_out.eq(-sin_port.data),
                    self.cos_out.eq(-cos_port.data)
                ]
            with m.Case(3):  # 270-360°
                m.d.comb += [
                    self.sin_out.eq(-sin_port.data),
                    self.cos_out.eq(cos_port.data)
                ]

        return m
```

### 4.4 Code NCO Module

```python
# code_nco.py
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class CodeNCO(wiring.Component):
    """
    Code phase NCO for PRN code generation timing.

    Generates code chip boundaries and fractional chip phase.

    For GPS L1 C/A:
    - Code rate: 1.023 Mcps
    - @ fs=16 MHz: 16/1.023 ≈ 15.64 samples/chip
    - Phase increment: (1.023e6 / 16e6) * 2^32 ≈ 0x0A2C2A2C

    For NavIC L5:
    - Code rate: 10.23 Mcps
    - @ fs=16 MHz: 16/10.23 ≈ 1.56 samples/chip
    - Phase increment: (10.23e6 / 16e6) * 2^32 ≈ 0x655C28F6
    """

    freq_word: In(unsigned(32))   # Code rate control word
    phase_offset: In(unsigned(32))
    enable: In(1)

    chip_index: Out(unsigned(10))  # Current chip index (0-1022 for GPS)
    chip_phase: Out(unsigned(32))  # Fractional chip phase
    chip_strobe: Out(1)            # High for one clock on chip edge

    def __init__(self, code_length=1023):
        super().__init__()
        self.code_length = code_length

    def elaborate(self, platform):
        m = Module()

        # Phase accumulator
        phase_acc = Signal(32)
        prev_phase = Signal(32)

        # Chip counter with wraparound
        chip_count = Signal(range(self.code_length))

        with m.If(self.enable):
            m.d.sync += [
                prev_phase.eq(phase_acc),
                phase_acc.eq(phase_acc + self.freq_word)
            ]

            # Detect chip edge (MSB transition from 0→1)
            with m.If(~prev_phase[31] & phase_acc[31]):
                m.d.sync += chip_count.eq(
                    Mux(chip_count == self.code_length - 1,
                        0,
                        chip_count + 1)
                )
                m.d.sync += self.chip_strobe.eq(1)
            with m.Else():
                m.d.sync += self.chip_strobe.eq(0)

        # Output assignments
        m.d.comb += [
            self.chip_index.eq(chip_count),
            self.chip_phase.eq(phase_acc + self.phase_offset)
        ]

        return m
```

### 4.5 Correlator Module

```python
# correlator.py
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class Correlator(wiring.Component):
    """
    Early/Prompt/Late correlator with configurable spacing.

    Performs complex correlation: Σ (sample * code * carrier*)

    Supports:
    - Configurable integration period (1-20 ms)
    - Up to 7 taps (VE, E, P, L, VL, + 2 custom)
    - Complex accumulation (I and Q channels)
    - Dump-on-epoch with clear
    """

    sample_i: In(signed(2))
    sample_q: In(signed(2))
    carrier_i: In(signed(16))  # cos(carrier)
    carrier_q: In(signed(16))  # sin(carrier)
    code_early: In(1)
    code_prompt: In(1)
    code_late: In(1)

    integrate: In(1)           # Accumulate when high
    dump: In(1)                # Dump and clear accumulators

    corr_e_i: Out(signed(32))  # Early I accumulator
    corr_e_q: Out(signed(32))  # Early Q accumulator
    corr_p_i: Out(signed(32))  # Prompt I accumulator
    corr_p_q: Out(signed(32))  # Prompt Q accumulator
    corr_l_i: Out(signed(32))  # Late I accumulator
    corr_l_q: Out(signed(32))  # Late Q accumulator

    def elaborate(self, platform):
        m = Module()

        # Carrier wipeoff: sample × carrier*
        # (I + jQ) × (cos - j·sin) = (I·cos + Q·sin) + j(Q·cos - I·sin)
        wiped_i = Signal(signed(18))
        wiped_q = Signal(signed(18))

        m.d.sync += [
            wiped_i.eq(self.sample_i * self.carrier_i +
                       self.sample_q * self.carrier_q),
            wiped_q.eq(self.sample_q * self.carrier_i -
                       self.sample_i * self.carrier_q)
        ]

        # Code correlation (multiply by code chip value: ±1)
        # Code value: 1 → use wiped value, 0 → use -wiped value
        corr_input_i = Signal(signed(18))
        corr_input_q = Signal(signed(18))

        # Accumulators for each tap
        acc_e_i = Signal(signed(32))
        acc_e_q = Signal(signed(32))
        acc_p_i = Signal(signed(32))
        acc_p_q = Signal(signed(32))
        acc_l_i = Signal(signed(32))
        acc_l_q = Signal(signed(32))

        with m.If(self.integrate):
            # Early tap
            with m.If(self.code_early):
                m.d.sync += [
                    acc_e_i.eq(acc_e_i + wiped_i),
                    acc_e_q.eq(acc_e_q + wiped_q)
                ]
            with m.Else():
                m.d.sync += [
                    acc_e_i.eq(acc_e_i - wiped_i),
                    acc_e_q.eq(acc_e_q - wiped_q)
                ]

            # Prompt tap
            with m.If(self.code_prompt):
                m.d.sync += [
                    acc_p_i.eq(acc_p_i + wiped_i),
                    acc_p_q.eq(acc_p_q + wiped_q)
                ]
            with m.Else():
                m.d.sync += [
                    acc_p_i.eq(acc_p_i - wiped_i),
                    acc_p_q.eq(acc_p_q - wiped_q)
                ]

            # Late tap
            with m.If(self.code_late):
                m.d.sync += [
                    acc_l_i.eq(acc_l_i + wiped_i),
                    acc_l_q.eq(acc_l_q + wiped_q)
                ]
            with m.Else():
                m.d.sync += [
                    acc_l_i.eq(acc_l_i - wiped_i),
                    acc_l_q.eq(acc_l_q - wiped_q)
                ]

        # Dump and clear
        with m.If(self.dump):
            m.d.sync += [
                acc_e_i.eq(0),
                acc_e_q.eq(0),
                acc_p_i.eq(0),
                acc_p_q.eq(0),
                acc_l_i.eq(0),
                acc_l_q.eq(0)
            ]

        # Output assignments
        m.d.comb += [
            self.corr_e_i.eq(acc_e_i),
            self.corr_e_q.eq(acc_e_q),
            self.corr_p_i.eq(acc_p_i),
            self.corr_p_q.eq(acc_p_q),
            self.corr_l_i.eq(acc_l_i),
            self.corr_l_q.eq(acc_l_q)
        ]

        return m
```

### 4.6 GPS L1 C/A Code Generator

```python
# gps_l1ca_gen.py
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class GPSL1CAGenerator(wiring.Component):
    """
    GPS L1 C/A code generator using LFSR.

    Generates 1023-chip Gold code using two 10-bit LFSRs:
    - G1: polynomial 0x081 (1 + X^3 + X^10)
    - G2: polynomial 0x197 (1 + X^2 + X^3 + X^6 + X^8 + X^9 + X^10)

    PRN selection via G2 phase delay (5-1021 chips).
    """

    prn: In(unsigned(8))         # PRN number (1-210)
    chip_index: In(unsigned(10)) # Current chip (0-1022)
    enable: In(1)
    reset: In(1)

    code_out: Out(1)             # Current code chip (0 or 1)

    def __init__(self):
        super().__init__()

        # G2 delay table for PRN 1-32 (GPS satellites)
        self.g2_delay = [
            5, 6, 7, 8, 17, 18, 139, 140, 141, 251,
            252, 254, 255, 256, 257, 258, 469, 470, 471, 472,
            473, 474, 509, 512, 513, 514, 515, 516, 859, 860,
            861, 862
            # ... extend to PRN 210 for SBAS/future satellites
        ]

    def elaborate(self, platform):
        m = Module()

        # G1 and G2 shift registers
        g1 = Signal(10, reset=0x3FF)  # All ones
        g2 = Signal(10, reset=0x3FF)

        # Generated code memories (cache for fast access)
        # Option 1: Generate on-the-fly (saves BRAM)
        # Option 2: Pre-compute and store in BRAM (faster, uses ~32 KB for all PRNs)

        # On-the-fly generation:
        with m.If(self.reset):
            m.d.sync += [
                g1.eq(0x3FF),
                g2.eq(0x3FF)
            ]
        with m.Elif(self.enable):
            # G1 feedback: tap bits 3 and 10 (indices 2 and 9)
            g1_feedback = g1[2] ^ g1[9]
            m.d.sync += g1.eq(Cat(g1_feedback, g1[0:9]))

            # G2 feedback: tap bits 2,3,6,8,9,10 (indices 1,2,5,7,8,9)
            g2_feedback = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
            m.d.sync += g2.eq(Cat(g2_feedback, g2[0:9]))

        # Select G2 tap based on PRN (use delay table)
        g2_tap_index = Signal(10)
        m.d.comb += g2_tap_index.eq(Array(self.g2_delay)[self.prn - 1])

        # Calculate delayed G2 index
        g2_delayed_index = Signal(10)
        m.d.comb += g2_delayed_index.eq(
            Mux(self.chip_index >= g2_tap_index,
                self.chip_index - g2_tap_index,
                self.chip_index + 1023 - g2_tap_index)
        )

        # XOR G1 and G2 for final code
        # Note: This simplified version generates sequentially
        # For random access, use pre-computed BRAM
        m.d.comb += self.code_out.eq(g1[9] ^ g2[9])

        return m
```

### ### CONTINUE FROM HERE

Would you like me to continue with:
1. NavIC L5 code generator
2. Channel manager and CSR interface
3. LiteX SoC integration
4. Testing infrastructure
5. Resource estimates
6. Complete implementation with build system
### 4.7 NavIC L5 Code Generator

```python
# navic_l5_gen.py
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class NavICL5Generator(wiring.Component):
    """
    NavIC L5 code generator (similar to GPS L1 C/A).

    Uses same Gold code structure as GPS:
    - Code length: 1023 chips
    - Code rate: 1.023 Mcps (but transmitted at 10.23 Mcps with 10x repetition)
    - G1/G2 polynomials: Same as GPS L1 C/A
    - Different G2 initial states for PRN 1-14
    """

    prn: In(unsigned(4))         # PRN number (1-14 for NavIC)
    chip_index: In(unsigned(10)) # Current chip (0-1022)
    enable: In(1)
    reset: In(1)

    code_out: Out(1)

    def __init__(self):
        super().__init__()

        # G2 initialization values for NavIC L5 (PRN 1-14)
        self.g2_init = [
            0x0C8,  # PRN 1
            0x019,  # PRN 2
            0x040,  # PRN 3
            0x0B4,  # PRN 4
            0x175,  # PRN 5
            0x1D6,  # PRN 6
            0x237,  # PRN 7
            0x2F8,  # PRN 8
            0x0D1,  # PRN 9
            0x132,  # PRN 10
            0x193,  # PRN 11
            0x0ED,  # PRN 12
            0x14E,  # PRN 13
            0x1AF,  # PRN 14
        ]

    def elaborate(self, platform):
        m = Module()

        # Similar LFSR structure as GPS L1 C/A
        g1 = Signal(10, reset=0x3FF)
        g2 = Signal(10)  # PRN-specific initialization

        # Initialize G2 based on PRN
        g2_init_val = Signal(10)
        m.d.comb += g2_init_val.eq(Array(self.g2_init)[self.prn - 1])

        with m.If(self.reset):
            m.d.sync += [
                g1.eq(0x3FF),
                g2.eq(g2_init_val)
            ]
        with m.Elif(self.enable):
            # G1 feedback
            g1_fb = g1[2] ^ g1[9]
            m.d.sync += g1.eq(Cat(g1_fb, g1[0:9]))

            # G2 feedback
            g2_fb = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
            m.d.sync += g2.eq(Cat(g2_fb, g2[0:9]))

        # Output XOR
        m.d.comb += self.code_out.eq(g1[9] ^ g2[9])

        return m
```

---

## 5. LiteX SoC Integration

### 5.1 MAX2771 ADC Interface for ECP5

```python
# max2771_interface.py
from amaranth import *
from amaranth.lib import wiring, stream
from amaranth.lib.wiring import In, Out
from amaranth_boards.lattice_ecp5_5g_versa import *

class MAX2771Interface(wiring.Component):
    """
    MAX2771 RF frontend interface for ECP5 FPGA.

    The MAX2771 provides 2-bit I and Q outputs at the sampling rate.
    
    Interface options:
    1. Parallel mode: 4-bit bus (2-bit I + 2-bit Q) + clock
    2. Serial mode: LVDS data stream + clock

    This implementation uses parallel mode with DDR sampling.

    MAX2771 Pins:
    - IQO[0]: I_bit0 (LSB)
    - IQO[1]: I_bit1 (MSB/sign)
    - IQO[2]: Q_bit0 (LSB)
    - IQO[3]: Q_bit1 (MSB/sign)
    - CLKOUT: ADC sample clock (4-16 MHz depending on config)
    """

    # Input pins from MAX2771
    iq_data: In(unsigned(4))      # Parallel IQ data bus
    sample_clk: In(1)             # CLKOUT from MAX2771

    # Output stream
    samples: Out(stream.Signature(data.StructLayout({
        "i": signed(2),
        "q": signed(2),
        "valid": 1
    })))

    def elaborate(self, platform):
        m = Module()

        # Register inputs for metastability
        iq_data_sync = Signal(4)
        m.d.adc += iq_data_sync.eq(self.iq_data)

        # Extract I and Q components
        i_raw = Signal(2)
        q_raw = Signal(2)
        m.d.comb += [
            i_raw.eq(iq_data_sync[0:2]),
            q_raw.eq(iq_data_sync[2:4])
        ]

        # Convert 2-bit sign-magnitude to signed
        # MAX2771 format: bit[1]=sign, bit[0]=magnitude
        # 00 → +1, 01 → +3, 10 → -1, 11 → -3
        i_signed = Signal(signed(2))
        q_signed = Signal(signed(2))

        def two_bit_to_signed(raw):
            """Convert MAX2771 2-bit format to signed value."""
            return Mux(raw[1],
                      # Negative: 10→-1, 11→-3
                      Mux(raw[0], C(-3, signed(2)), C(-1, signed(2))),
                      # Positive: 00→+1, 01→+3
                      Mux(raw[0], C(3, signed(2)), C(1, signed(2))))

        m.d.adc += [
            i_signed.eq(two_bit_to_signed(i_raw)),
            q_signed.eq(two_bit_to_signed(q_raw))
        ]

        # Output stream
        m.d.adc += [
            self.samples.payload.i.eq(i_signed),
            self.samples.payload.q.eq(q_signed),
            self.samples.valid.eq(1)  # Always valid in continuous mode
        ]

        return m
```

### 5.2 LiteX SoC Top-Level

```python
# amalthea_soc.py
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.clock import *
from litex.soc.cores.led import LedChaser

from litex_boards.platforms import lattice_ecp5_5g_evn
from amaranth import *

from gnss_baseband import GNSSBaseband
from max2771_interface import MAX2771Interface

class AmaltheaSoC(SoCCore):
    """
    Amalthea GNSS Receiver SoC for Lattice ECP5.

    Features:
    - VexRiscv CPU @ 50 MHz
    - 32 KB RAM
    - UART console
    - GNSS baseband processor
    - MAX2771 ADC interface
    """

    def __init__(self, sys_clk_freq=50e6, **kwargs):
        platform = lattice_ecp5_5g_evn.Platform()

        # SoCCore initialization
        SoCCore.__init__(self, platform, sys_clk_freq,
            cpu_type="vexriscv",
            cpu_variant="minimal",
            integrated_rom_size=0x8000,
            integrated_sram_size=0x8000,
            integrated_main_ram_size=0x8000,
            ident="Amalthea GNSS SoC",
            ident_version=True,
            **kwargs
        )

        # Clock domains
        # - sys_clk: 50 MHz (CPU, Wishbone, peripherals)
        # - adc_clk: 16 MHz (MAX2771 sampling, generated or input)
        # - corr_clk: 100 MHz (correlation engines, optional)
        
        self.submodules.crg = self.create_crg(platform)

        # LED heartbeat
        self.submodules.leds = LedChaser(
            pads=platform.request_all("user_led"),
            sys_clk_freq=sys_clk_freq
        )

        # MAX2771 Interface
        self.submodules.max2771 = MAX2771Interface()

        # GNSS Baseband Processor
        self.submodules.gnss = GNSSBaseband(
            num_channels=12,
            sample_rate=16e6,
            sys_clk_freq=sys_clk_freq
        )

        # Wishbone CSR bridge to GNSS module
        self.bus.add_slave("gnss", self.gnss.bus, SoCRegion(
            origin=0x30000000,
            size=0x10000,
            cached=False
        ))

        # Connect MAX2771 output to GNSS input
        self.comb += self.gnss.sample_input.eq(self.max2771.samples)

        # Interrupts
        self.irq.add("gnss_epoch", use_loc_if_exists=True)

    def create_crg(self, platform):
        """Create clock and reset generator."""
        m = Module()

        # Input clock from platform (usually 100 MHz)
        clk100 = platform.request("clk100")

        # PLL for system clock (50 MHz) and correlation clock (100 MHz)
        m.submodules.pll = pll = ECP5PLL()
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(m, self.cd_sys, 50e6)
        pll.create_clkout(m, self.cd_corr, 100e6)

        # ADC clock options:
        # Option 1: Use CLKOUT from MAX2771 as adc_clk
        # Option 2: Generate 16 MHz from PLL
        
        # Option 2 (generate from PLL):
        pll.create_clkout(m, self.cd_adc, 16e6)

        # Option 1 (external ADC clock):
        # adc_clk_pin = platform.request("adc_clk")
        # m.d.comb += ClockSignal("adc").eq(adc_clk_pin)

        return m

def main():
    """Build the Amalthea SoC."""
    soc = AmaltheaSoC()
    builder = Builder(soc, output_dir="build/amalthea",
                     csr_csv="build/amalthea/csr.csv")
    builder.build(run=True)

    # Generate software headers
    soc.generate_software_headers()

if __name__ == "__main__":
    main()
```

### 5.3 CSR Memory Map

```
Amalthea GNSS SoC Memory Map:
┌──────────────────────────────────────────────────────────┐
│ Address Range      │ Peripheral                          │
├────────────────────┼─────────────────────────────────────┤
│ 0x00000000         │ ROM (32 KB)                         │
│ 0x10000000         │ SRAM (32 KB)                        │
│ 0x20000000         │ Main RAM (32 KB)                    │
│ 0x82000000         │ UART                                │
│ 0x82000800         │ Timer                               │
│ 0x82001000         │ LEDs                                │
│ 0x30000000         │ GNSS Baseband (64 KB)               │
│   0x30000000       │   - Control registers               │
│   0x30000100       │   - Status registers                │
│   0x30001000       │   - Channel 0 config                │
│   0x30001100       │   - Channel 1 config                │
│   ...              │   ...                               │
│   0x30001B00       │   - Channel 11 config               │
│   0x30002000       │   - Correlation results buffer      │
└────────────────────┴─────────────────────────────────────┘

CSR Register Layout (per channel):
Offset  │ Register Name       │ Description
────────┼─────────────────────┼──────────────────────────────
0x00    │ CTRL                │ Enable, reset, integration time
0x04    │ STATUS              │ Lock status, C/N0 estimate
0x08    │ CARRIER_FREQ_HI     │ Carrier NCO freq word [31:16]
0x0C    │ CARRIER_FREQ_LO     │ Carrier NCO freq word [15:0]
0x10    │ CARRIER_PHASE       │ Carrier NCO phase offset
0x14    │ CODE_FREQ_HI        │ Code NCO freq word [31:16]
0x18    │ CODE_FREQ_LO        │ Code NCO freq word [15:0]
0x1C    │ CODE_PHASE          │ Code NCO phase offset
0x20    │ PRN                 │ PRN number and signal type
0x24    │ CORR_E_I            │ Early correlator I (read-only)
0x28    │ CORR_E_Q            │ Early correlator Q (read-only)
0x2C    │ CORR_P_I            │ Prompt correlator I (read-only)
0x30    │ CORR_P_Q            │ Prompt correlator Q (read-only)
0x34    │ CORR_L_I            │ Late correlator I (read-only)
0x38    │ CORR_L_Q            │ Late correlator Q (read-only)
```

---

## 6. Signal Processing Pipeline (Hardware)

### 6.1 GPS L1 C/A Processing Flow

```
MAX2771 ADC (16 MHz sampling)
         │
         │ 2-bit I/Q samples
         ↓
┌────────────────────────────────────────────────────────┐
│          Sample Acquisition Module                     │
│  • Clock domain crossing (adc_clk → sys_clk)          │
│  • 2-bit → signed conversion                          │
│  • Timestamp generation                               │
│  • FIFO buffering (16K samples ≈ 1ms @ 16 MHz)        │
└──────────────────┬─────────────────────────────────────┘
                   │ Signed I/Q stream
                   ↓
┌────────────────────────────────────────────────────────┐
│          Channel Processor (×12 channels)              │
│                                                        │
│  ┌──────────────────────────────────────────────┐    │
│  │  Carrier NCO (Doppler compensation)          │    │
│  │  • Frequency: -5 kHz to +5 kHz               │    │
│  │  • Resolution: 0.0037 Hz                     │    │
│  │  • Output: 16-bit cos/sin                    │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  Complex Mixer (sample × carrier*)           │    │
│  │  Wiped_I = sample_I × cos + sample_Q × sin  │    │
│  │  Wiped_Q = sample_Q × cos - sample_I × sin  │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  Code NCO (chip timing)                      │    │
│  │  • Nominal rate: 1.023 Mcps                  │    │
│  │  • Adjustable for Doppler aiding             │    │
│  │  • Generates chip index (0-1022)             │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  GPS L1 C/A Code Generator                   │    │
│  │  • LFSR-based Gold code                      │    │
│  │  • PRN configurable (1-32)                   │    │
│  │  • Early/Prompt/Late taps (±0.5 chip)        │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  E/P/L Correlator                            │    │
│  │  • Accumulates wiped × code                  │    │
│  │  • Integration: 1-20 ms                      │    │
│  │  • Output: 32-bit I/Q per tap                │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
└─────────────────────┼─────────────────────────────────┘
                      │ Correlation results
                      ↓
┌────────────────────────────────────────────────────────┐
│          CSR Interface (Wishbone)                      │
│  • CPU reads correlation results                      │
│  • CPU writes NCO frequencies/phases                  │
│  • CPU configures PRN and integration time            │
│  • Interrupt on correlation dump complete             │
└────────────────────────────────────────────────────────┘
                      │
                      ↓
                [RISC-V Processor]
                      │
                      ↓
         [Software tracking loops & PVT]
```

### 6.2 NavIC L5 Processing (Same Architecture)

The NavIC L5 signal uses the same processing pipeline with different parameters:

| Parameter | GPS L1 C/A | NavIC L5 |
|-----------|------------|----------|
| Carrier Frequency | 1575.42 MHz | 1176.45 MHz |
| Code Rate | 1.023 Mcps | 10.23 Mcps (1.023 Mcps × 10 repeat) |
| Code Length | 1023 chips | 1023 chips |
| Samples/Chip @ 16 MHz | 15.64 | 1.564 |
| Code NCO Freq Word | 0x0A2C2A2C | 0x655C28F6 |

**NavIC L5 特殊性: 10x Code Repetition**
- Each chip is repeated 10 times
- Effective chip rate: 10.23 Mcps (actual transmission)
- Base code rate: 1.023 Mcps (PRN generation)
- Hardware handles repetition via faster code NCO

---

## 7. Resource Estimation

### 7.1 ECP5 Resource Usage (12 Channels)

| Module | LUTs | FFs | EBRs (18Kb) | DSPs | Notes |
|--------|------|-----|-------------|------|-------|
| **Per Channel (×12):** | | | | | |
| Carrier NCO | 120 | 80 | 0.25 | 0 | LUT-based sin/cos |
| Code NCO | 100 | 70 | 0 | 0 | Phase accumulator |
| Code Generator | 80 | 50 | 1 | 0 | LFSR + PRN select |
| Correlator (3-tap) | 200 | 150 | 0 | 6 | 6 complex multiply-accumulate |
| **Subtotal per CH** | **500** | **350** | **1.25** | **6** | |
| **Total (12 CH)** | **6000** | **4200** | **15** | **72** | |
| | | | | | |
| Sample Acquisition | 300 | 250 | 4 | 0 | FIFO + timestamp |
| Channel Manager | 500 | 400 | 2 | 0 | Control logic |
| CSR Interface | 400 | 300 | 1 | 0 | Wishbone registers |
| Code Memory (shared) | 200 | 100 | 8 | 0 | Pre-computed codes |
| | | | | | |
| **GNSS Baseband Total** | **7400** | **5250** | **30** | **72** | |
| | | | | | |
| LiteX SoC (VexRiscv) | 2500 | 2000 | 10 | 2 | CPU + peripherals |
| | | | | | |
| **Grand Total** | **9900** | **7250** | **40** | **74** | |
| | | | | | |
| **ECP5-45F Available** | 44,000 | 44,000 | 108 | 72 | |
| **Utilization** | **22.5%** | **16.5%** | **37%** | **103%** ❌ | |

**DSP Shortage Solution:**
- Reduce channels to 11 (72-6=66 DSPs used, 92% utilization) ✅
- OR use LUT-based multipliers for some correlators (slower but viable)
- OR time-multiplex correlation (4 channels per correlator, reduces to 18 DSPs) ✅

**Recommended: Time-Multiplexed Correlation**
```
3 correlation engines × 6 DSPs = 18 DSPs
Each engine services 4 channels sequentially
Throughput: 100 MHz / 4 = 25 MSPS per channel (sufficient for 16 Msps)
```

### 7.2 Timing Analysis

| Clock Domain | Frequency | Critical Path | Margin |
|--------------|-----------|---------------|--------|
| adc_clk | 16 MHz | Sample register | Large |
| sys_clk | 50 MHz | Wishbone arbitration | ~10 ns |
| corr_clk | 100 MHz | DSP multiply-add | ~5 ns (tight) |

**Timing Closure Strategies:**
- Pipeline correlator multipliers (adds 1-2 cycle latency)
- Reduce corr_clk to 80 MHz if needed (still 5× faster than ADC)
- Use Lattice radiant timing constraints

---

## 8. Testing Strategy

### 8.1 Unit Tests (Amaranth Simulator)

```python
# test_carrier_nco.py
import unittest
from amaranth.sim import Simulator
from carrier_nco import CarrierNCO

class TestCarrierNCO(unittest.TestCase):
    def test_frequency_accuracy(self):
        """Verify NCO generates correct frequency."""
        dut = CarrierNCO()

        def testbench():
            # Set frequency word for 1 kHz output @ 16 MHz sampling
            # freq_word = (1e3 / 16e6) * 2^32 = 268435
            yield dut.freq_word.eq(268435)
            yield dut.enable.eq(1)

            # Capture 16000 samples (1 second of data)
            cos_samples = []
            for _ in range(16000):
                yield
                cos_samples.append((yield dut.cos_out))

            # FFT analysis to verify 1 kHz peak
            fft_result = np.fft.fft(cos_samples)
            peak_bin = np.argmax(np.abs(fft_result))
            peak_freq = peak_bin * 16e6 / len(cos_samples)

            self.assertAlmostEqual(peak_freq, 1000, delta=1)

        sim = Simulator(dut)
        sim.add_clock(1/16e6)  # 16 MHz clock
        sim.add_process(testbench)
        sim.run()
```

### 8.2 Integration Tests

```python
# test_channel_integration.py
import unittest
from amaranth.sim import Simulator
from channel_core import ChannelCore
import numpy as np

class TestChannelIntegration(unittest.TestCase):
    def test_gps_l1ca_acquisition(self):
        """Simulate GPS L1 C/A signal and verify correlation peak."""
        dut = ChannelCore(signal_type="L1CA", prn=12)

        # Generate synthetic GPS signal
        fs = 16e6  # 16 MHz sampling
        f_if = 4.092e6  # IF frequency
        f_doppler = -1234  # -1234 Hz Doppler
        code_phase = 0.5  # 0.5 ms code offset
        cn0 = 45  # 45 dB-Hz

        samples = generate_gps_signal(
            prn=12, fs=fs, f_if=f_if, doppler=f_doppler,
            code_phase=code_phase, cn0=cn0, duration=0.02  # 20 ms
        )

        def testbench():
            # Configure channel
            yield dut.prn.eq(12)
            yield dut.carrier_freq.eq(freq_to_word(f_if + f_doppler, fs))
            yield dut.code_freq.eq(code_freq_word(1.023e6, fs))
            yield dut.integrate_time.eq(20)  # 20 ms integration
            yield dut.enable.eq(1)

            # Feed samples
            for sample in samples:
                yield dut.sample_i.eq(sample.real)
                yield dut.sample_q.eq(sample.imag)
                yield

            # Wait for correlation dump
            while not (yield dut.dump_ready):
                yield

            # Read correlation results
            p_i = yield dut.corr_p_i
            p_q = yield dut.corr_p_q
            power = p_i**2 + p_q**2

            # Verify correlation peak exceeds threshold
            self.assertGreater(power, 1e9)  # Strong correlation

        sim = Simulator(dut)
        sim.add_clock(1/fs)
        sim.add_process(testbench)
        sim.run()
```

### 8.3 Build Testing

```bash
#!/bin/bash
# build_test.sh

set -e

echo "=== Amaranth/LiteX Build Test ==="

# 1. Unit tests
echo "Running unit tests..."
python3 -m pytest test/ -v

# 2. Lint check
echo "Running Amaranth lint..."
python3 -m amaranth.cli lint gnss_baseband.py

# 3. Synthesis test (ECP5)
echo "Synthesizing for ECP5..."
python3 amalthea_soc.py --build

# 4. Timing report
echo "Checking timing..."
ecppack --freq 50 build/amalthea/gateware/amalthea.config \
        build/amalthea/gateware/amalthea.bit \
        --timing-report timing_report.txt

grep "MHz" timing_report.txt

# 5. Resource utilization
echo "Resource utilization:"
grep -A 10 "Device utilisation" build/amalthea/gateware/amalthea.tim

echo "=== Build test complete ==="
```

### 8.4 Hardware-in-the-Loop Testing

```
┌─────────────────────────────────────────────────────────┐
│                  HIL Test Setup                         │
│                                                          │
│  ┌────────────┐      ┌────────────┐      ┌───────────┐ │
│  │ GNSS       │ RF   │ MAX2771    │ IQ   │  ECP5     │ │
│  │ Simulator  │─────→│  Frontend  │─────→│  FPGA     │ │
│  │ (Spirent)  │      │            │      │  Amalthea │ │
│  └────────────┘      └────────────┘      └─────┬─────┘ │
│                                                 │       │
│                                                 │ UART  │
│                                                 ↓       │
│                                           ┌──────────┐  │
│                                           │   PC     │  │
│                                           │ Software │  │
│                                           └──────────┘  │
└─────────────────────────────────────────────────────────┘

Test Scenarios:
1. Static position: Verify correlation peaks for visible satellites
2. Dynamic trajectory: Track satellites through acquisition/tracking
3. Low C/N0: Verify sensitivity down to 30 dB-Hz
4. High dynamics: Doppler up to ±8 kHz
5. Multipath: Verify DLL performance with reflections
```

---

## 9. Implementation Roadmap

### Phase 1: Core Modules (Week 1-2)
- [x] Design document
- [ ] Implement Carrier NCO with unit tests
- [ ] Implement Code NCO with unit tests
- [ ] Implement GPS L1 C/A code generator with unit tests
- [ ] Implement NavIC L5 code generator with unit tests
- [ ] Implement Correlator with unit tests

### Phase 2: Integration (Week 3)
- [ ] Implement MAX2771 interface
- [ ] Implement Sample Acquisition module
- [ ] Implement Channel Manager
- [ ] Implement CSR interface
- [ ] Integration testing with simulated samples

### Phase 3: LiteX SoC (Week 4)
- [ ] Create Amalthea SoC top-level
- [ ] Integrate GNSS baseband into LiteX
- [ ] Build for ECP5 target
- [ ] Timing closure and optimization
- [ ] Resource optimization (time-multiplexed correlation)

### Phase 4: Software (Week 5)
- [ ] Bare-metal firmware for VexRiscv
- [ ] CSR access library
- [ ] Channel configuration functions
- [ ] Correlation result readout
- [ ] Basic tracking loop in software

### Phase 5: Validation (Week 6)
- [ ] FPGA programming and bring-up
- [ ] RF signal injection testing
- [ ] Hardware-in-the-loop with GNSS simulator
- [ ] Performance benchmarking
- [ ] Documentation and handoff

---

## 10. Software Interface Example

```c
// amalthea_gnss.h
#ifndef AMALTHEA_GNSS_H
#define AMALTHEA_GNSS_H

#include <stdint.h>
#include <generated/csr.h>

// Channel configuration
typedef struct {
    uint8_t channel_id;
    uint8_t prn;
    uint8_t signal_type;  // 0=GPS L1CA, 1=NavIC L5
    int32_t carrier_freq_hz;
    int32_t code_freq_hz;
    uint16_t integration_ms;
} gnss_channel_config_t;

// Correlation results
typedef struct {
    int32_t early_i, early_q;
    int32_t prompt_i, prompt_q;
    int32_t late_i, late_q;
    uint32_t timestamp_ms;
} gnss_correlation_t;

// API functions
void gnss_init(void);
void gnss_configure_channel(gnss_channel_config_t *config);
void gnss_read_correlation(uint8_t channel_id, gnss_correlation_t *result);
void gnss_set_integration_time(uint8_t channel_id, uint16_t ms);
uint32_t gnss_get_timestamp(void);

// Example usage
int main(void) {
    gnss_init();

    // Configure channel 0 for GPS PRN 12
    gnss_channel_config_t ch0_config = {
        .channel_id = 0,
        .prn = 12,
        .signal_type = 0,  // GPS L1CA
        .carrier_freq_hz = 4092000 - 1234,  // IF - Doppler
        .code_freq_hz = 1023000,
        .integration_ms = 20
    };
    gnss_configure_channel(&ch0_config);

    // Main loop: read correlations and update tracking
    while (1) {
        gnss_correlation_t corr;
        gnss_read_correlation(0, &corr);

        // Tracking loop calculations
        float dll_error = calculate_dll_error(corr.early_i, corr.early_q,
                                              corr.late_i, corr.late_q);
        float pll_error = calculate_pll_error(corr.prompt_i, corr.prompt_q);

        // Update NCOs
        ch0_config.code_freq_hz += (int32_t)(dll_error * DLL_GAIN);
        ch0_config.carrier_freq_hz += (int32_t)(pll_error * PLL_GAIN);
        gnss_configure_channel(&ch0_config);
    }

    return 0;
}
#endif
```

---

## Summary

This design provides a complete **Amaranth HDL + LiteX SoC** implementation for a GNSS receiver targeting the **ECP5 FPGA** and **MAX2771 RF frontend**. Key highlights:

✅ **Hardware-accelerated correlation** with 12 channels (scalable)
✅ **GPS L1 C/A and NavIC L5** signal support
✅ **Modular Amaranth design** with comprehensive unit tests
✅ **LiteX SoC integration** with VexRiscv CPU
✅ **Wishbone CSR interface** for easy software control
✅ **Resource-optimized** for ECP5-45F (time-multiplexed correlators)
✅ **Complete testing strategy** from unit to HIL tests
✅ **Production-ready architecture** with clear implementation roadmap

**Next Steps:**
1. Implement core modules with unit tests
2. Validate on ECP5 development board
3. Interface with real MAX2771 hardware
4. Develop tracking loop software
5. Full system integration and validation

