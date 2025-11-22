# PocketSDR Architecture Documentation

**Version:** 0.14
**Author:** Comprehensive analysis and documentation
**Date:** 2025-11-22

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Architecture](#hardware-architecture)
3. [Software Architecture](#software-architecture)
4. [Signal Processing Pipeline](#signal-processing-pipeline)
5. [Module Interactions](#module-interactions)
6. [Data Structures](#data-structures)
7. [GNSS Signal Support](#gnss-signal-support)
8. [Integration Points](#integration-points)

---

## 1. System Overview

PocketSDR is a comprehensive open-source GNSS Software-Defined Radio receiver supporting GPS, GLONASS, Galileo, BeiDou, QZSS, NavIC, and SBAS constellations. The system consists of:

- **Hardware**: USB-connected RF frontend devices (FE 2CH/4CH/8CH)
- **Firmware**: Cypress EZ-USB FX2LP/FX3 firmware for USB streaming
- **Software**: C/C++/Python applications for signal processing and positioning
- **Libraries**: Core SDR library + RTKLIB integration

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GNSS Satellites                              │
│         GPS | GLONASS | Galileo | BeiDou | QZSS | NavIC           │
└────────────────────────────┬────────────────────────────────────────┘
                             │ RF Signals (L1/L2/L5/L6 bands)
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   RF Frontend (MAX2771)                             │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐          │
│  │   LNA    │  Mixer   │  Filter  │   ADC    │  Clock   │          │
│  │  Gain    │ LO=PLL   │ 2.5-36MHz│ 2/3-bit  │ 24MHz    │          │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Digitized IF Data
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│              USB Controller (FX2LP/FX3)                             │
│  ┌──────────────────┬─────────────────────────────────┐            │
│  │ GPIF II / Slave  │   USB 2.0/3.0 Bulk Transfer    │            │
│  │ FIFO Interface   │   40 MB/s (USB2) / 400 MB/s    │            │
│  └──────────────────┴─────────────────────────────────┘            │
└────────────────────────────┬────────────────────────────────────────┘
                             │ USB 3.0 / USB 2.0
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Host Computer                                    │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │               SDR Applications                            │      │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │      │
│  │  │pocket_acq│pocket_trk│pocket_snap│pocket_sdr│          │      │
│  │  └─────┬────┴────┬─────┴─────┬────┴────┬─────┘          │      │
│  └────────┼─────────┼───────────┼─────────┼────────────────┘      │
│           │         │           │         │                        │
│  ┌────────┴─────────┴───────────┴─────────┴────────────────┐      │
│  │            libpocketsdr.so (Core SDR Library)            │      │
│  │  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐    │      │
│  │  │ Code │ Corr │ Track│ Nav  │ PVT  │ FEC  │ USB  │    │      │
│  │  │ Gen  │ FFT  │ Loop │ Dec  │ Comp │ LDPC │ Ctrl │    │      │
│  │  └──────┴──────┴──────┴──────┴──────┴──────┴──────┘    │      │
│  └──────────────────────────┬───────────────────────────────┘      │
│                             │                                       │
│  ┌──────────────────────────┴───────────────────────────────┐      │
│  │              RTKLIB (Positioning Library)                 │      │
│  │    SPP | DGPS | RTK | PPP | RINEX | RTCM | Ephemeris    │      │
│  └───────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ↓
                   Position/Velocity/Time Solution
```

---

## 2. Hardware Architecture

### 2.1 Frontend Variants Comparison

| Feature | FE 2CH | FE 4CH | FE 8CH |
|---------|--------|--------|--------|
| **RF Channels** | 2 | 4 | 8 |
| **RF Inputs** | 1 antenna | 1 antenna | 1 or 8 antennas |
| **USB Controller** | FX2LP (USB 2.0) | FX3 (USB 3.0) | FX3 (USB 3.0) |
| **Max Throughput** | 40 MB/s | 400 MB/s | 400 MB/s |
| **Sampling Rate** | 4-32 Msps | 4-48 Msps | 4-48 Msps |
| **IF Bandwidth** | 2.5-23.4 MHz | 2.5-36 MHz | 2.5-36 MHz |
| **Power Consumption** | 0.7 W | 1.2 W | 1.65 W |
| **USB Connector** | micro-B / Type-C | Type-C | Type-C |

### 2.2 MAX2771 RF Frontend Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      MAX2771 GNSS Receiver                       │
│                                                                  │
│  RF Input    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │
│   (ANT)  ───→│  LNA   │→ │ Mixer  │→ │ Filter │→ │  ADC   │──→│
│              └────────┘  └───┬────┘  └────────┘  └────────┘   │
│                              │                                  │
│                         ┌────┴────┐                            │
│              TCXO ────→ │   PLL   │                            │
│            (24 MHz)     └─────────┘                            │
│                                                                  │
│  Configuration:                                                 │
│  • LO Frequency: PLL dividers (NDIV, RDIV, FDIV)              │
│  • IF Filter: FCEN (0-31), FBW (0-7), F3OR5 (3rd/5th order)  │
│  • Sampling: ADCCLK, REFDIV, IQEN (I-only or IQ)             │
│  • Quantization: BITS (1-3), DRVCFG (output driver)          │
│  • AGC: AGCMODE, GAINREF, GAININ                             │
│                                                                  │
│  Output: 2-bit or 3-bit digitized IF samples                   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 USB Streaming Architecture (FE 4CH/8CH)

```
┌──────────────────────────────────────────────────────────────────┐
│                    EZ-USB FX3 Architecture                        │
│                                                                   │
│  ┌────────────┐        ┌──────────────┐      ┌──────────────┐  │
│  │  MAX2771   │  PIB   │   GPIF II    │ DMA  │  USB 3.0     │  │
│  │  (Ch 1-8)  │───────→│ State Machine│─────→│  Controller  │─→│
│  │  Parallel  │ 32-bit │              │      │   EP 0x86    │  │
│  │  Data Bus  │        │ Dual-Socket  │      │ Bulk IN      │  │
│  └────────────┘        └──────────────┘      └──────────────┘  │
│        ↑                      ↑                                  │
│        │ SPI Control          │ ARM926 CPU @ 200 MHz            │
│        │                      │                                  │
│  ┌─────┴──────────────────────┴────────┐                        │
│  │         Firmware (pocket_fw_v3/v4)  │                        │
│  │  • GPIO control (chip selects, LEDs)│                        │
│  │  • SPI master for MAX2771 config    │                        │
│  │  • USB vendor requests (0x40-0x4B)  │                        │
│  │  • EEPROM management (64 KB)        │                        │
│  └─────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘

DMA Buffer Architecture (USB 3.0 SuperSpeed):
┌────────────┐   ┌────────────┐
│ Buffer 0   │   │ Buffer 1   │
│ 16 KB      │←─→│ 16 KB      │  Ping-Pong Buffering
└────────────┘   └────────────┘
     │                 │
     └────────┬────────┘
              ↓
        USB Bulk Transfer
       (16 burst × 1024 bytes)
```

### 2.4 Channel Configuration Examples

**L1+L6 Dual-Band Setup (FE 2CH):**
```
CH1: L1 Band (1575.42 MHz)  →  IF = 4.092 MHz, fs = 12 MHz
CH2: L6 Band (1278.75 MHz)  →  IF = 4.092 MHz, fs = 12 MHz
```

**Multi-GNSS Setup (FE 4CH):**
```
CH1: L1 (GPS/Galileo/QZSS/BeiDou)  →  IF = 0 MHz (Zero-IF), IQ, fs = 24 MHz
CH2: L5 (GPS L5/Galileo E5a)       →  IF = 0 MHz, IQ, fs = 24 MHz
CH3: E5b (Galileo)                 →  IF = +30.69 MHz offset
CH4: L6 (QZSS)                     →  IF = +30.69 MHz offset
```

---

## 3. Software Architecture

### 3.1 Module Organization

```
PocketSDR/
├── src/              # Core SDR Library (libpocketsdr.so)
│   ├── sdr_rcv.c     # Receiver orchestration & multi-threading
│   ├── sdr_ch.c      # Channel state machine & tracking loops
│   ├── sdr_dev.c     # USB device driver abstraction
│   ├── sdr_usb.c     # Low-level USB I/O (libusb/CyAPI)
│   ├── sdr_conf.c    # MAX2771 configuration management
│   ├── sdr_func.c    # Signal processing functions (FFT, correlation)
│   ├── sdr_code.c    # PRN code generation (GPS, GLONASS, etc.)
│   ├── sdr_code_gal.c # Galileo code lookup tables
│   ├── sdr_nav.c     # Navigation message decoders
│   ├── sdr_pvt.c     # PVT solution computation & RTCM/NMEA output
│   ├── sdr_fec.c     # FEC (Viterbi, Reed-Solomon)
│   ├── sdr_ldpc.c    # Binary LDPC decoder (GPS, NavIC)
│   └── sdr_nb_ldpc.c # Non-binary LDPC (BeiDou GF(64))
│
├── app/              # Applications
│   ├── pocket_dump/  # IF data capture utility
│   ├── pocket_scan/  # USB device scanner
│   ├── pocket_conf/  # Device configurator
│   ├── pocket_acq/   # Signal acquisition (C version)
│   ├── pocket_trk/   # Signal tracking + PVT (C version)
│   ├── pocket_snap/  # Snapshot positioning
│   ├── convbin/      # Binary→RINEX converter
│   └── str2str/      # Stream server/converter
│
├── python/           # Python Applications
│   ├── pocket_psd.py # Power spectral density plotter
│   ├── pocket_acq.py # Signal acquisition with plots
│   ├── pocket_trk.py # Signal tracking with plots
│   ├── pocket_snap.py# Snapshot positioning with plots
│   ├── pocket_sdr.py # GUI-based real-time receiver
│   └── pocket_plot.py# Log file plotter
│
└── lib/              # External Libraries
    ├── RTKLIB/       # Positioning & navigation data processing
    ├── cyusb/        # Cypress USB API (Windows)
    ├── libfec/       # Forward error correction
    └── LDPC-codes/   # Radford Neal's LDPC library
```

### 3.2 Core SDR Library Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                     libpocketsdr.so                               │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               Receiver Layer (sdr_rcv.c)                  │   │
│  │  • Multi-threading coordination                          │   │
│  │  • Buffer management (8000-cycle circular buffers)       │   │
│  │  • Channel lifecycle management                          │   │
│  │  • PVT integration & output streaming                    │   │
│  └───────────────┬──────────────────────────────────────────┘   │
│                  │                                               │
│  ┌───────────────┴──────────────────────────────────────────┐   │
│  │            Channel Layer (sdr_ch.c)                       │   │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │   │
│  │  │  IDLE    │  SEARCH  │  LOCK    │  State   │          │   │
│  │  │  State   │  State   │  State   │  Machine │          │   │
│  │  └──────────┴──────────┴──────────┴──────────┘          │   │
│  │  • Acquisition (FFT-based parallel search)              │   │
│  │  • Tracking loops (FLL→PLL, DLL)                        │   │
│  │  • Correlation (Standard/FFT correlators)               │   │
│  │  • Navigation data extraction                           │   │
│  └───────┬──────────────────────────────────────────────────┘   │
│          │                                                       │
│  ┌───────┴───────┬───────────┬───────────┬───────────┐         │
│  │               │           │           │           │         │
│  ├───────────────┤           │           │           │         │
│  │ Device Driver │  Signal   │    Nav    │    PVT    │         │
│  │  (sdr_dev.c)  │Processing │  Decoder  │ Computer  │         │
│  │               │(sdr_func.c)│(sdr_nav.c)│(sdr_pvt.c)│         │
│  ├───────────────┤           │           │           │         │
│  │  USB I/O      │   Code    │    FEC    │   RTCM    │         │
│  │ (sdr_usb.c)   │Generation │Decoders   │  NMEA     │         │
│  │               │(sdr_code.c)│(sdr_fec.c)│  Output   │         │
│  └───────────────┴───────────┴───────────┴───────────┘         │
└───────────────────────────────────────────────────────────────────┘
```

### 3.3 Thread Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Main Thread                               │
│              (User interface, initialization)                    │
└──────────────────┬───────────────────────────────────────────────┘
                   │
      ┌────────────┼────────────┬────────────────────────┐
      │            │            │                        │
      ↓            ↓            ↓                        ↓
┌──────────┐ ┌──────────┐ ┌──────────┐          ┌──────────┐
│ Receiver │ │   USB    │ │ Channel  │   ...    │ Channel  │
│  Thread  │ │  Event   │ │ Thread 1 │          │ Thread N │
│          │ │ Handler  │ │          │          │          │
│          │ │ (Real-   │ │          │          │          │
│          │ │  time    │ │          │          │          │
│          │ │ priority)│ │          │          │          │
└────┬─────┘ └────┬─────┘ └────┬─────┘          └────┬─────┘
     │            │            │                     │
     │ 1ms cycle  │ USB IRQ    │ 50ms cycle          │ 50ms cycle
     │            │            │                     │
     ↓            ↓            ↓                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Shared Circular Buffers (Mutex Protected)       │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │RF CH 1   │RF CH 2   │RF CH 3   │RF CH 4   │  ...         │
│  │8000 cyc  │8000 cyc  │8000 cyc  │8000 cyc  │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
└─────────────────────────────────────────────────────────────┘

Thread Responsibilities:

1. Receiver Thread (rcv_thread):
   - Read IF data from USB device
   - Demultiplex to RF channel buffers
   - Manage buffer write pointers

2. USB Event Handler (event_handler):
   - High-priority bulk transfer completion
   - Circular buffer management (6 × 1 MB)
   - Real-time priority (SCHED_RR, priority 99)

3. Channel Threads (ch_thread × N):
   - Per-channel signal processing
   - Independent state machines
   - Acquisition or tracking operations
   - Navigation data decoding
   - PVT observation updates
```

---

## 4. Signal Processing Pipeline

### 4.1 Acquisition Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     Signal Acquisition                           │
│                                                                  │
│  IF Data Buffer     Carrier Mixing      FFT Correlation         │
│  (1ms segment)                                                   │
│       │                 │                    │                   │
│       ↓                 ↓                    ↓                   │
│  ┌─────────┐      ┌──────────┐        ┌──────────┐             │
│  │ N samples│      │ LUT-based│        │Code FFT  │             │
│  │ @ fs MHz │  →   │ exp(j2πf)│   →    │conjugate │             │
│  │ INT8/IQ  │      │ multipli-│        │multiply  │             │
│  └─────────┘      │ cation   │        └──────────┘             │
│                    └──────────┘              │                   │
│                          ↓                   ↓                   │
│                    ┌──────────┐        ┌──────────┐             │
│                    │ Complex  │        │  IFFT    │             │
│                    │ Baseband │   →    │          │             │
│                    │  I + jQ  │        │          │             │
│                    └──────────┘        └──────────┘             │
│                                              │                   │
│                                              ↓                   │
│  Doppler Bins     Non-coherent Int.    Peak Detection           │
│  (-5000 to        (20ms default)                                 │
│   +5000 Hz)                                                      │
│       │                 │                    │                   │
│       ↓                 ↓                    ↓                   │
│  ┌─────────┐      ┌──────────┐        ┌──────────┐             │
│  │ 21 bins │      │Accumulate│        │Find max  │             │
│  │ 500 Hz  │  ×   │  |C|²    │   →    │correlation│            │
│  │ steps   │      │  power   │        │C/N0 est. │             │
│  └─────────┘      └──────────┘        └──────────┘             │
│                                              │                   │
│                                              ↓                   │
│                                        ┌──────────┐             │
│                                        │Fine      │             │
│                                        │Doppler   │             │
│                                        │(quadratic│             │
│                                        │fitting)  │             │
│                                        └──────────┘             │
│                                              │                   │
│                                              ↓                   │
│                     C/N0 ≥ 34 dB-Hz? ──→ Transition to LOCK     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Parameters:**
- Integration time: 20ms (configurable via `sdr_t_acq`)
- Doppler search: ±5000 Hz (`sdr_max_dop`), step = 0.5/T Hz
- Threshold C/N0: 34 dB-Hz (`THRES_CN0_L`)
- FFT size: N samples per code cycle (e.g., 12,276 for L1CA @ 12 MHz)

### 4.2 Tracking Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                   Signal Tracking (1ms cycle)                     │
│                                                                   │
│  Code Offset          Carrier Mixing        Correlation          │
│  Adjustment                                                       │
│       │                    │                     │                │
│       ↓                    ↓                     ↓                │
│  ┌─────────┐         ┌──────────┐         ┌──────────┐          │
│  │ fd→code │         │exp(j2π·  │         │E/P/L/N/  │          │
│  │ offset  │    →    │fd·t·+φ)  │    →    │VE/VL taps│          │
│  │ carrier │         │ carrier  │         │Standard  │          │
│  │ aiding  │         │ wipeoff  │         │or FFT    │          │
│  └─────────┘         └──────────┘         │correlator│          │
│                                            └──────────┘          │
│                                                  │                │
│  ┌──────────────────────────────────────────────┘                │
│  │                                                                │
│  ├→ P correlator  → Navigation data demod                        │
│  ├→ E/L correlator→ DLL discriminator                            │
│  ├→ VE/VL         → Bump-jump detection (BOC signals)            │
│  └→ N correlator  → C/N0 estimation                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Tracking Loop Filters                      │    │
│  │                                                           │    │
│  │  ┌──────────────────────────────────────────────┐       │    │
│  │  │ FLL (Frequency Lock Loop)                    │       │    │
│  │  │ • Cross-product discriminator                │       │    │
│  │  │ • BW: 5 Hz (wide) → 2 Hz (narrow)           │       │    │
│  │  │ • Duration: 0-1 second after lock            │       │    │
│  │  └──────────────────────────────────────────────┘       │    │
│  │                        ↓                                 │    │
│  │  ┌──────────────────────────────────────────────┐       │    │
│  │  │ PLL (Phase Lock Loop)                        │       │    │
│  │  │ • Costas/ATAN2 discriminator                 │       │    │
│  │  │ • BW: 5 Hz                                   │       │    │
│  │  │ • 2nd order loop filter                      │       │    │
│  │  └──────────────────────────────────────────────┘       │    │
│  │                        ↓                                 │    │
│  │  ┌──────────────────────────────────────────────┐       │    │
│  │  │ DLL (Delay Lock Loop)                        │       │    │
│  │  │ • Early-minus-late discriminator             │       │    │
│  │  │ • BW: 0.25 Hz                                │       │    │
│  │  │ • Spacing: 0.25 chips                        │       │    │
│  │  │ • Integration: 20ms                          │       │    │
│  │  └──────────────────────────────────────────────┘       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                       │
│                          ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Updated State Variables                        │    │
│  │  • Doppler frequency (fd) in Hz                         │    │
│  │  • Code offset (coff) in seconds                        │    │
│  │  • Carrier phase (adr) accumulated in cycles            │    │
│  │  • C/N0 estimate in dB-Hz                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                       │
│                          ↓                                       │
│                 C/N0 < 30 dB-Hz? ──→ Signal lost → IDLE         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Correlator Architecture:**
```
Code Delay (chips):
  VE      E       P       L      VL       N
   │      │       │       │       │       │
   ↓      ↓       ↓       ↓       ↓       ↓
  -1.0  -0.125   0.0   +0.125  +1.0    -120 samples

VE/VL: Very Early/Late (BOC bump-jump detection)
E/L:   Early/Late (DLL tracking, spacing 0.25 chips)
P:     Prompt (carrier phase, navigation data)
N:     Noise (C/N0 estimation, far from signal)

Additional: 81 correlators spanning ±2μs for multipath monitoring
```

### 4.3 Navigation Message Decoding Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                 Navigation Data Decoder                           │
│                                                                   │
│  Prompt Correlator     Symbol Sync       Frame Sync              │
│  (IP, QP)                                                         │
│       │                    │                 │                    │
│       ↓                    ↓                 ↓                    │
│  ┌─────────┐         ┌──────────┐      ┌──────────┐             │
│  │ IP/QP   │         │ Detect   │      │ Preamble │             │
│  │ corr-   │    →    │ bit      │  →   │ search   │             │
│  │ elation │         │ trans-   │      │ (±polar) │             │
│  │ values  │         │ itions   │      │          │             │
│  └─────────┘         └──────────┘      └──────────┘             │
│                                              │                    │
│                                              ↓                    │
│  Secondary Code      FEC Decoding       Message Parsing          │
│  Sync (if needed)                                                 │
│       │                    │                 │                    │
│       ↓                    ↓                 ↓                    │
│  ┌─────────┐         ┌──────────┐      ┌──────────┐             │
│  │ NH10/20 │         │ Viterbi  │      │ Extract  │             │
│  │ CS codes│    →    │ LDPC     │  →   │ ephemeris│             │
│  │ align   │         │ BCH      │      │ iono/UTC │             │
│  │         │         │ RS, CRC  │      │ TOW/week │             │
│  └─────────┘         └──────────┘      └──────────┘             │
│                                              │                    │
│                                              ↓                    │
│                                        ┌──────────┐              │
│                                        │ Update   │              │
│                                        │ nav DB   │              │
│                                        │ Output   │              │
│                                        │ RTCM/log │              │
│                                        └──────────┘              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               FEC Algorithm Selection                     │   │
│  │                                                            │   │
│  │  GPS L1 C/A:      Parity (6-bit Hamming)                 │   │
│  │  GPS L2C/L5:      Viterbi (1/2 rate, K=7)                │   │
│  │  GPS L1C:         Binary LDPC (600/274 bits)             │   │
│  │  GLONASS L1OF:    CRC-8                                  │   │
│  │  GLONASS L1OCD:   Viterbi (1/2 rate)                     │   │
│  │  Galileo I/NAV:   Viterbi + CRC-24Q                      │   │
│  │  BeiDou D1/D2:    BCH(15,11,1)                           │   │
│  │  BeiDou B1C:      NB-LDPC GF(64) (600/264 bits)          │   │
│  │  NavIC L1/L5:     Binary LDPC (600/274 bits)             │   │
│  │  SBAS:            Viterbi (1/2 rate) + CRC-24            │   │
│  │  QZSS L6:         Reed-Solomon RS(255,223)               │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 4.4 PVT Computation Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                  PVT (Position, Velocity, Time)                   │
│                                                                   │
│  Observations         Ephemeris          Corrections              │
│  from Channels        Database                                    │
│       │                    │                 │                    │
│       ↓                    ↓                 ↓                    │
│  ┌─────────┐         ┌──────────┐      ┌──────────┐             │
│  │Pseudorange│       │Broadcast │      │Klobuchar │             │
│  │Carrier    │   +   │ephemeris │  +   │iono     │             │
│  │phase      │       │(nav msg) │      │Saastam.  │             │
│  │Doppler    │       │          │      │tropo     │             │
│  │C/N0       │       │          │      │          │             │
│  └─────────┘         └──────────┘      └──────────┘             │
│       │                                                           │
│       ↓                                                           │
│  ┌──────────────────────────────────────────────────────┐        │
│  │        Pseudorange Generation                        │        │
│  │  τ = (TOW_rx - TOW_sat) + code_offset                │        │
│  │  PR = c × τ  (speed of light × time difference)     │        │
│  │                                                       │        │
│  │  100ms ambiguity resolution for pilot channels:      │        │
│  │  - Reference: data channel pseudorange               │        │
│  │  - Align to nearest millisecond boundary             │        │
│  └──────────────────────────────────────────────────────┘        │
│                          │                                        │
│                          ↓                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │       RTKLIB Single Point Positioning                 │        │
│  │                 (pntpos)                              │        │
│  │                                                       │        │
│  │  1. Satellite position computation (satpos)          │        │
│  │  2. Geometric distance (geodist)                     │        │
│  │  3. Ionospheric delay (ionmodel)                     │        │
│  │  4. Tropospheric delay (tropmodel)                   │        │
│  │  5. Satellite clock correction                       │        │
│  │  6. Earth rotation correction                        │        │
│  │  7. Iterative least-squares solution:                │        │
│  │     - Position (x, y, z) or (lat, lon, hgt)         │        │
│  │     - Receiver clock bias                            │        │
│  │  8. RAIM-FDE (fault detection/exclusion)            │        │
│  └──────────────────────────────────────────────────────┘        │
│                          │                                        │
│                          ↓                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │              Output Generation                        │        │
│  │                                                       │        │
│  │  NMEA: RMC, GGA, GSA, GSV (1 Hz)                    │        │
│  │  RTCM3: MSM7 observations (1 Hz)                    │        │
│  │        Ephemeris messages (every 30-60s)            │        │
│  │  Logs: $POS, $OBS, $SAT, $EPH, $NAV, $ION          │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘

Epoch Management:
┌────────────────────────────────────────────────────────────┐
│  Default epoch: 1.0 second intervals                       │
│  Wait for all channels to report observations              │
│  Lag tolerance: 0.5 seconds maximum                        │
│  Adjust epoch based on receiver clock bias estimate        │
└────────────────────────────────────────────────────────────┘
```

---

## 5. Module Interactions

### 5.1 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  USB Device        Receiver         Channels          PVT          │
│  (sdr_dev.c)      (sdr_rcv.c)      (sdr_ch.c)      (sdr_pvt.c)    │
│                                                                     │
│      │                 │                │              │           │
│      │  IF Data        │                │              │           │
│      │  Streaming      │                │              │           │
│      ├────────────────→│                │              │           │
│      │                 │                │              │           │
│      │                 │  Demux to      │              │           │
│      │                 │  RF Buffers    │              │           │
│      │                 ├───────────────→│              │           │
│      │                 │                │              │           │
│      │                 │                │ Acquisition  │           │
│      │                 │                │ / Tracking   │           │
│      │                 │                │              │           │
│      │                 │   ←────────────┤              │           │
│      │                 │   Observations │              │           │
│      │                 │   (PR, CP, D)  │              │           │
│      │                 │                │              │           │
│      │                 │                │ Navigation   │           │
│      │                 │                │ Data         │           │
│      │                 │   ←────────────┤              │           │
│      │                 │   Ephemeris    │              │           │
│      │                 │   TOW, Week    │              │           │
│      │                 │                │              │           │
│      │                 │  Update PVT    │              │           │
│      │                 ├───────────────────────────────→│           │
│      │                 │                │              │           │
│      │                 │                │   Compute    │           │
│      │                 │                │   Position   │           │
│      │                 │                │              │           │
│      │                 │   ←────────────────────────────│           │
│      │                 │   NMEA/RTCM                    │           │
│      │                 │                                            │
│      │                 │  Stream to                                 │
│      │                 │  Output Files                              │
│      │                 ├───────────────→ [NMEA.txt]                │
│      │                 ├───────────────→ [RTCM3.rtcm3]             │
│      │                 └───────────────→ [LOG.txt]                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Channel State Machine

```
┌──────────────────────────────────────────────────────────────────┐
│                   Channel State Machine                           │
│                                                                   │
│                    ┌────────────┐                                 │
│                    │            │                                 │
│          ┌─────────│    IDLE    │←──────────┐                    │
│          │         │            │           │                    │
│          │         └────────────┘           │                    │
│          │               │                  │                    │
│          │ Assignment    │                  │ Signal Lost        │
│          │ (sig, prn)    │                  │ (C/N0 < 30)       │
│          │               ↓                  │                    │
│          │         ┌────────────┐           │                    │
│          │         │            │           │                    │
│          │         │   SEARCH   │───────────┘                    │
│          │         │            │  Not Found                     │
│          │         └────────────┘  (timeout)                     │
│          │               │                                        │
│          │               │ Signal Found                           │
│          │               │ (C/N0 ≥ 34)                           │
│          │               │                                        │
│          │               ↓                                        │
│          │         ┌────────────┐                                 │
│          │         │            │                                 │
│          └─────────│    LOCK    │                                 │
│         (re-acq)   │  (Tracking)│                                 │
│                    │            │                                 │
│                    └────────────┘                                 │
│                                                                   │
│  State Responsibilities:                                         │
│                                                                   │
│  IDLE:   • Wait for assignment from receiver                     │
│          • No processing load                                    │
│                                                                   │
│  SEARCH: • FFT-based parallel code search                        │
│          • Doppler bin scanning (±5000 Hz)                       │
│          • Non-coherent integration (20ms)                       │
│          • C/N0 estimation from correlation peak                 │
│          • Transition to LOCK if C/N0 ≥ threshold                │
│                                                                   │
│  LOCK:   • Carrier tracking (FLL→PLL)                            │
│          • Code tracking (DLL)                                   │
│          • Navigation data demodulation                          │
│          • Observation generation (PR, CP, Doppler)              │
│          • Continuous C/N0 monitoring                            │
│          • Return to IDLE if signal lost                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Multi-GNSS Time System Management

```
┌──────────────────────────────────────────────────────────────────┐
│                Time System Conversions                            │
│                                                                   │
│  GNSS System │ Time Reference │ Offset from GPST │ Week Offset   │
│  ────────────┼────────────────┼──────────────────┼──────────────│
│  GPS         │ GPST           │ 0.0 s            │ 0 weeks      │
│  GLONASS     │ GLONASST (UTC) │ ~18.0 s (leap)   │ N/A          │
│  Galileo     │ GST            │ 0.0 s            │ +1024 weeks  │
│  BeiDou      │ BDT            │ +14.0 s          │ +1356 weeks  │
│  QZSS        │ GPST           │ 0.0 s            │ 0 weeks      │
│  NavIC       │ IRT            │ 0.0 s            │ +1024 weeks  │
│  ────────────┴────────────────┴──────────────────┴──────────────│
│                                                                   │
│  UTC Leap Seconds (as of 2025): 18 seconds                       │
│  GPST = UTC + 18 seconds                                         │
│                                                                   │
│  PVT Solution Time Selection:                                    │
│  1. GPS time if available (most common reference)                │
│  2. GLONASS time if no GPS                                       │
│  3. Galileo time if no GPS/GLONASS                               │
│  4. BeiDou time if only BDS available                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Structures

### 6.1 Core Data Types

#### IF Sample Format (sdr_cpx8_t)

```c
typedef uint8_t sdr_cpx8_t;

// 8-bit packed format:
// Bits [7:4] = I component (4-bit signed)
// Bits [3:0] = Q component (4-bit signed)

#define SDR_CPX8_I(x) ((int8_t)(((x) & 0xF0) - ((x) & 0x80) * 2) >> 4)
#define SDR_CPX8_Q(x) ((int8_t)(((x) & 0x0F) - ((x) & 0x08) * 2))
```

#### Channel Structure (sdr_ch_t)

```c
typedef struct {
    // Identity
    int no;                  // Channel number (0-1499)
    int rf_ch;               // RF channel assignment (0-7)
    int state;               // State: IDLE(1), SRCH(2), LOCK(3)

    // Signal identification
    char sat[16];            // Satellite ID ("G12", "E05", "C19", etc.)
    char sig[16];            // Signal ID ("L1CA", "E5AQ", "B1CP", etc.)
    int prn;                 // PRN number

    // Code properties
    const int8_t *code;      // Primary code pointer (±1 values)
    const int8_t *sec_code;  // Secondary code pointer
    int len_code;            // Primary code length (chips)
    int len_sec_code;        // Secondary code length (chips)

    // Signal parameters
    double fc;               // Carrier frequency (Hz)
    double fs;               // Sampling frequency (Hz)
    double fi;               // IF frequency (Hz)
    double T;                // Code cycle period (seconds)
    int N;                   // Samples per code cycle

    // Tracking state
    double time;             // Receiver time (seconds)
    double fd;               // Doppler frequency (Hz)
    double coff;             // Code offset (seconds)
    double adr;              // Accumulated Doppler range (cycles)
    double cn0;              // C/N0 estimate (dB-Hz)
    int lock, lost;          // Lock/lost counters
    int week, tow;           // GPS week and time-of-week (ms)
    int tow_v;               // TOW validity (0=invalid, 1=100ms, 2=1ms)

    // Processing modules
    sdr_acq_t *acq;         // Acquisition state
    sdr_trk_t *trk;         // Tracking state
    sdr_nav_t *nav;         // Navigation decoder state

    // Buffers
    sdr_cpx16_t *data;      // Carrier-mixed data buffer
    sdr_cpx_t *corr;        // Correlation buffer (L6D/E CSK)

    // Thread safety
    pthread_mutex_t mtx;
} sdr_ch_t;
```

#### Receiver Structure (sdr_rcv_t)

```c
typedef struct {
    int state;               // Receiver state
    int dev;                 // Device type: FILE(0) or USB(1+)
    void *dp;                // Device pointer

    // Format and configuration
    int fmt;                 // Data format (INT8, INT8X2, RAW8/16/32)
    double fs;               // Sampling frequency (Hz)
    double fo[8];            // LO frequencies per RF channel
    int IQ[8];               // Sampling types (0=I, 1=IQ)
    int bits[8];             // Quantization bits (2 or 3)

    // Channels and buffers
    int nch;                 // Number of signal channels
    int nbuff;               // Number of RF buffers (1-8)
    int N;                   // Samples per 1ms cycle
    sdr_ch_th_t *th[SDR_MAX_NCH];  // Channel threads (max 1500)
    sdr_buff_t *buff[8];     // IF data buffers (8000 cycles each)
    int64_t ix;              // Current cycle counter

    // PVT and output
    sdr_pvt_t *pvt;          // PVT processor
    stream_t *strs[4];       // Output streams (NMEA, RTCM, log, IF)

    // Threading
    pthread_t thread;        // Receiver thread
    pthread_mutex_t mtx;     // Mutex for thread safety
} sdr_rcv_t;
```

### 6.2 Observation Data Flow

```
┌────────────────────────────────────────────────────────────────┐
│                  Observation Data Structure                     │
│                                                                 │
│  Channel                RTKLIB                  PVT             │
│  (sdr_ch_t)            (obsd_t)              Solution           │
│                                                                 │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐       │
│  │ time     │────────→│ time     │         │ Position │       │
│  │ week     │         │ sat      │    →    │ lat,lon  │       │
│  │ tow      │         │ rcv      │         │ height   │       │
│  │          │         │          │         │          │       │
│  │ fd       │────────→│ D[j]     │         │ Velocity │       │
│  │ (Doppler)│         │ (Hz)     │    →    │ vn,ve,vu │       │
│  │          │         │          │         │          │       │
│  │ coff     │         │ P[j]     │         │ Clock    │       │
│  │ (code)   │────────→│ (meters) │    →    │ bias     │       │
│  │          │         │          │         │ drift    │       │
│  │ adr      │         │ L[j]     │         │          │       │
│  │ (phase)  │────────→│ (cycles) │         │ GDOP     │       │
│  │          │         │          │         │ PDOP     │       │
│  │ cn0      │────────→│ SNR[j]   │         │ HDOP     │       │
│  │ (dB-Hz)  │         │ (0.001dB)│         │ VDOP     │       │
│  │          │         │          │         │          │       │
│  │ nav data │───→ nav database  │         │ Solution │       │
│  │ (eph)    │    (eph_t, geph_t)│    →    │ quality  │       │
│  └──────────┘         └──────────┘         └──────────┘       │
│                                                                 │
│  Data Mapping:                                                 │
│  • Pseudorange (P): CLIGHT × (TOW_rx - TOW_sat + coff)        │
│  • Carrier Phase (L): -adr (accumulated Doppler range)        │
│  • Doppler (D): fd (Doppler frequency)                        │
│  • SNR: cn0 × 1000 (convert dB-Hz to 0.001 dB-Hz units)      │
│  • Time: GPS time (week, TOW in seconds)                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. GNSS Signal Support

### 7.1 Supported Signal Matrix

| System | Band | Signal ID | Code Length | Period | Modulation | PRN Range |
|--------|------|-----------|-------------|--------|------------|-----------|
| **GPS** | L1 | L1CA | 1023 | 1 ms | BPSK | 1-210 |
| | L1 | L1CP | 10230 | 10 ms | TMBOC(6,1,4/33) | 1-210 |
| | L1 | L1CD | 10230 | 10 ms | BOC(1,1) | 1-210 |
| | L2 | L2CM | 10230 | 20 ms | BPSK | 1-210 |
| | L5 | L5I/Q | 10230 | 1 ms | BPSK | 1-210 |
| **GLONASS** | G1 | G1CA | 511 | 1 ms | BPSK+FDMA | FCN -7~+6 |
| | G1 | G1OCD/P | 1023/4092 | 1/8 ms | TDM/BOC+TDM | 1-63 |
| | G2 | G2CA | 511 | 1 ms | BPSK+FDMA | FCN -7~+6 |
| | G2 | G2OCP | 10230 | 20 ms | BOC+TDM | 1-63 |
| | G3 | G3OCD/P | 10230 | 1 ms | BPSK | 1-63 |
| **Galileo** | E1 | E1B/C | 4092 | 4 ms | BOC(1,1) | 1-50 |
| | E5a | E5AI/Q | 10230 | 1 ms | BPSK | 1-50 |
| | E5b | E5BI/Q | 10230 | 1 ms | BPSK | 1-50 |
| | E6 | E6B/C | 5115 | 1 ms | BPSK | 1-50 |
| **BeiDou** | B1 | B1I | 2046 | 1 ms | BPSK | 1-63 |
| | B1 | B1CD/P | 10230 | 10 ms | BOC(1,1) | 1-63 |
| | B2a | B2AD/P | 10230 | 1 ms | BPSK | 1-63 |
| | B2b | B2BI | 10230 | 1 ms | BPSK | 1-63 |
| | B3 | B3I | 10230 | 1 ms | BPSK | 1-63 |
| **QZSS** | L1 | L1CA/S | 1023 | 1 ms | BPSK | 193-202 |
| | L1 | L1CP/D | 10230 | 10 ms | TMBOC/BOC | 193-202 |
| | L2 | L2CM | 10230 | 20 ms | BPSK | 193-202 |
| | L5 | L5I/Q/SI/SQ | 10230 | 1 ms | BPSK | 193-202 |
| | L6 | L6D/E | CSK | 1 ms | CSK | 193-202 |
| **NavIC** | I1 | I1SD/P | 10230 | 10 ms | BOC(1,1) | 1-14 |
| | I5 | I5S | 1023 | 1 ms | BPSK | 1-14 |
| **SBAS** | L1 | L1CA | 1023 | 1 ms | BPSK | 120-158 |
| | L5 | L5I/Q | 10230 | 1 ms | BPSK | 120-158 |

**Total: 40+ distinct signal types across 5 constellations**

### 7.2 PRN Code Generation Algorithms

```
┌────────────────────────────────────────────────────────────────┐
│                 Code Generation Methods                         │
│                                                                 │
│  1. Gold Codes (LFSR XOR)                                      │
│     • GPS L1 C/A: G1(1023) ⊕ G2(1023) with delay              │
│     • NavIC I5S: Same as GPS L1 C/A                           │
│     Polynomials: G1=0x081, G2=0x197 (10-bit)                  │
│                                                                 │
│  2. Weil Codes (Legendre Sequences)                            │
│     • GPS L1C: Legendre(10223) product                        │
│     • BeiDou B1C: Legendre(10243) product                     │
│     Method: L[k] × L[(k+w) mod N]                             │
│                                                                 │
│  3. Dual-LFSR XOR                                              │
│     • GPS L2C/L5: Extended LFSR ⊕ LFSR                        │
│     • Galileo E5a/b: X1(14-bit) ⊕ X2(14-bit)                  │
│     • BeiDou B2a/B3I: Extended G1 ⊕ G2                        │
│                                                                 │
│  4. Custom Shift Registers                                     │
│     • NavIC I1S: Two 55-bit + one 5-bit registers             │
│     • GLONASS G1OC/G2OC: DC1 ⊕ DC2 with TDM                   │
│                                                                 │
│  5. Memory Codes (Pre-stored Tables)                           │
│     • Galileo E1B/C: Hex lookup tables                        │
│     • Galileo E6B/C: Hex lookup tables                        │
│     Storage: sdr_code_gal.c (3596 lines)                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 7.3 FEC Decoder Summary

| System | Signal | FEC Type | Code | Info Bits | Error Capacity |
|--------|--------|----------|------|-----------|----------------|
| GPS | L1 C/A | Parity | (6,1) | - | ~1 bit |
| GPS | L2C/L5 | Convolutional | (2,1,7) | 300/600 | ~5 bits |
| GPS | L1C | Binary LDPC | (600,300)/(274,137) | 600/274 | ~50/25 bits |
| GLONASS | L1OF | CRC | CRC-8 | - | Detection only |
| GLONASS | L1OCD | Convolutional | (2,1,7) | 262 | ~5 bits |
| Galileo | E1B (I/NAV) | Conv+CRC | (2,1,7)+CRC24 | 114 | ~5 bits |
| BeiDou | D1/D2 | BCH | (15,11,1) | 300 | 1 bit/word |
| BeiDou | B1C | NB-LDPC | GF(64) (100,50) | 600/264 | ~40/20 bits |
| BeiDou | B2a | NB-LDPC | GF(64) (48,24) | 288 | ~20 bits |
| NavIC | L1-SPS | Binary LDPC | (600,300)/(274,137) | 600/274 | ~50/25 bits |
| QZSS | L6 | Reed-Solomon | (255,223) | 223×8 bits | 16 symbols |
| SBAS | L1/L5 | Conv+CRC | (2,1,7)+CRC24 | 212 | ~5 bits |

---

## 8. Integration Points

### 8.1 RTKLIB Integration

```
┌────────────────────────────────────────────────────────────────┐
│                    RTKLIB Functions Used                        │
│                                                                 │
│  Positioning Algorithms:                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ pntpos()        Single point positioning (SPP)           │  │
│  │ rtkpos()        RTK positioning                          │  │
│  │ pppos()         Precise point positioning (PPP)          │  │
│  │ lambda()        LAMBDA ambiguity resolution              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Satellite Functions:                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ satpos()        Satellite position/clock                 │  │
│  │ satazel()       Azimuth/elevation calculation            │  │
│  │ geodist()       Geometric distance                       │  │
│  │ ionmodel()      Ionospheric delay (Klobuchar)            │  │
│  │ tropmodel()     Tropospheric delay (Saastamoinen)        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Navigation Decoders:                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ decode_frame()      GPS LNAV                             │  │
│  │ decode_glostr()     GLONASS navigation                   │  │
│  │ decode_gal_inav()   Galileo I/NAV                        │  │
│  │ decode_gal_fnav()   Galileo F/NAV                        │  │
│  │ decode_bds_d1/d2()  BeiDou D1/D2                         │  │
│  │ decode_irn_nav()    NavIC navigation                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  RINEX I/O:                                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ readrnx()       Read RINEX observation/navigation        │  │
│  │ outrnxobsh/b()  Write RINEX observation header/body      │  │
│  │ outrnxnavh()    Write navigation file headers           │  │
│  │ convrnx()       Convert receiver raw to RINEX           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  RTCM:                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ init_rtcm()     Initialize RTCM structure               │  │
│  │ input_rtcm3()   Decode RTCM3 messages                   │  │
│  │ gen_rtcm3()     Generate RTCM3 messages                 │  │
│  │   - Type 1077-1137: MSM7 observations                   │  │
│  │   - Type 1019-1046: Ephemeris messages                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 External Library Dependencies

```
┌────────────────────────────────────────────────────────────────┐
│                   Dependency Graph                              │
│                                                                 │
│  PocketSDR Applications                                        │
│         │                                                       │
│         ├──→ libpocketsdr.so (Core SDR library)               │
│         │        │                                             │
│         │        ├──→ FFTW3 (FFT operations)                  │
│         │        │     • fftwf_plan_dft_1d()                  │
│         │        │     • fftwf_execute_dft()                  │
│         │        │     • Wisdom files for optimization        │
│         │        │                                             │
│         │        ├──→ libfec (FEC decoding)                   │
│         │        │     • create_viterbi27()                   │
│         │        │     • decode_viterbi27()                   │
│         │        │     • decode_rs_8()                        │
│         │        │                                             │
│         │        ├──→ LDPC-codes (LDPC decoding)              │
│         │        │     • mod2sparse_*() functions             │
│         │        │     • prprp decoder                        │
│         │        │                                             │
│         │        └──→ USB Libraries                           │
│         │              • Linux: libusb-1.0                    │
│         │              • Windows: CyUSB (Cypress API)         │
│         │                                                      │
│         └──→ RTKLIB (libRTKLIB.so)                            │
│                  • Positioning algorithms                      │
│                  • Navigation data processing                  │
│                  • RINEX/RTCM I/O                             │
│                                                                 │
│  Python Applications (pocket_*.py)                             │
│         │                                                       │
│         ├──→ ctypes (C library binding)                       │
│         ├──→ numpy (Array operations)                         │
│         ├──→ scipy (Signal processing, FFT)                   │
│         ├──→ matplotlib (Plotting)                            │
│         └──→ tkinter (GUI for pocket_sdr.py)                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 8.3 File I/O and Data Formats

```
┌────────────────────────────────────────────────────────────────┐
│                    Input/Output Formats                         │
│                                                                 │
│  IF Data Files:                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ .bin         INT8 (I-only, 1 byte/sample)               │  │
│  │              INT8X2 (IQ, 2 bytes/sample)                │  │
│  │ .tag         Metadata (time, fs, fi, IQ, bits)          │  │
│  │                                                          │  │
│  │ Example:                                                 │  │
│  │   [TIME]                                                │  │
│  │   2024/03/15 10:30:45.123 (GPST)                        │  │
│  │   [FORMAT]                                              │  │
│  │   INT8                                                  │  │
│  │   [FS_MSPS]                                             │  │
│  │   12.0                                                  │  │
│  │   [FI_MHZ]                                              │  │
│  │   4.092                                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Configuration Files (.conf):                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [CH1]                                                    │  │
│  │ FCEN     = 97     # IF filter center                    │  │
│  │ LOBAND   = 0      # LO band (0=L1, 1=L2/L5)            │  │
│  │ NDIV     = 65     # PLL integer division                │  │
│  │ FDIV     = 411566 # PLL fractional division             │  │
│  │ ...                                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Output Formats:                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ NMEA         RMC, GGA, GSA, GSV sentences               │  │
│  │ RTCM3        MSM7 (observations), ephemeris messages    │  │
│  │ RINEX 2/3    Observation and navigation files           │  │
│  │ Logs         $POS, $OBS, $SAT, $EPH, $NAV, $ION        │  │
│  │ Solutions    RTKLIB format (lat, lon, hgt, Q, ns)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Summary

PocketSDR represents a **production-grade, open-source GNSS SDR receiver** with:

✓ **Multi-constellation support**: GPS, GLONASS, Galileo, BeiDou, QZSS, NavIC, SBAS
✓ **Scalable hardware**: 2/4/8-channel USB frontends with USB 2.0/3.0 connectivity
✓ **Professional signal processing**: FFT-based acquisition, multi-loop tracking, advanced FEC
✓ **Comprehensive positioning**: SPP, DGPS, RTK, PPP via RTKLIB integration
✓ **Flexible architecture**: Modular C library + Python applications + real-time GUI
✓ **Open ecosystem**: RINEX, RTCM3, NMEA outputs for integration with existing tools

**Key Differentiators:**
- Complete hardware+software solution with open-source firmware
- Support for 40+ GNSS signal types including modern signals (L5, E5, B1C, B2a)
- Advanced FEC (Binary/Non-binary LDPC, Viterbi, Reed-Solomon, BCH)
- Multi-threaded architecture for real-time multi-channel processing
- Tight RTKLIB integration for professional-grade positioning

This architecture documentation provides a comprehensive blueprint for understanding, extending, and building upon the PocketSDR platform.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-22
**Maintainer:** PocketSDR Development Team
**License:** BSD 2-Clause (see LICENSE.txt)
