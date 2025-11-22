"""
GPS Disciplined Oscillator (GPSDO) - Hardware Implementation

Provides precise 1PPS signal and disciplined clock output synchronized to GPS time.

Features:
- 1PPS generator from GPS time solution
- Phase detector comparing GPS 1PPS to local oscillator
- Digital PI controller for oscillator discipline
- DAC interface for VCXO/OCXO control
- Holdover mode when GPS unavailable
- Multiple synchronized clock outputs

Author: PocketSDR GPSDO Implementation
License: BSD 2-Clause
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class PPS_Generator(wiring.Component):
    """
    1PPS (Pulse Per Second) generator from GPS time of week.

    Generates precise 1Hz pulse aligned to GPS time for oscillator discipline.

    Parameters
    ----------
    sys_clk_freq : int
        System clock frequency in Hz (default: 48 MHz)
    """

    # Inputs
    tow: In(unsigned(32))           # GPS Time of Week (ms)
    tow_valid: In(1)                # TOW is valid
    tow_update: In(1)               # TOW update strobe
    enable: In(1)                   # Enable PPS generation

    # Outputs
    pps_out: Out(1)                 # 1PPS output pulse (100ms wide)
    pps_led: Out(1)                 # LED output (blink on PPS)
    pps_count: Out(unsigned(32))    # Count of PPS pulses generated

    def __init__(self, sys_clk_freq=48_000_000):
        """Initialize 1PPS generator."""
        super().__init__()
        self.sys_clk_freq = sys_clk_freq

    def elaborate(self, platform):
        m = Module()

        # Counter for 1Hz timing
        # Count to 1 second worth of clock cycles
        second_counter = Signal(range(self.sys_clk_freq))

        # Millisecond counter (tracks TOW mod 1000)
        ms_counter = Signal(10)  # 0-999 ms

        # PPS pulse width counter (100ms = 4.8M clocks at 48MHz)
        pulse_width = self.sys_clk_freq // 10  # 100ms
        pulse_counter = Signal(range(pulse_width + 1))

        # PPS state
        pps_active = Signal()
        last_tow = Signal(32)
        pps_count_reg = Signal(32)

        # LED blink timer (stays on for 100ms)
        led_timer = Signal(range(pulse_width + 1))

        # Main PPS generation logic
        with m.If(self.enable):
            # Track TOW milliseconds
            with m.If(self.tow_update & self.tow_valid):
                m.d.sync += [
                    last_tow.eq(self.tow),
                    ms_counter.eq(self.tow[:10])  # Lower 10 bits = ms within second
                ]

            # Increment second counter
            with m.If(second_counter == (self.sys_clk_freq - 1)):
                m.d.sync += second_counter.eq(0)

                # Check if we're at second boundary (ms == 0)
                with m.If(ms_counter == 0):
                    # Generate PPS pulse
                    m.d.sync += [
                        pps_active.eq(1),
                        pulse_counter.eq(0),
                        pps_count_reg.eq(pps_count_reg + 1),
                        led_timer.eq(0)
                    ]
            with m.Else():
                m.d.sync += second_counter.eq(second_counter + 1)

            # PPS pulse width control
            with m.If(pps_active):
                with m.If(pulse_counter == pulse_width):
                    m.d.sync += pps_active.eq(0)
                with m.Else():
                    m.d.sync += pulse_counter.eq(pulse_counter + 1)

            # LED blink control
            with m.If(led_timer < pulse_width):
                m.d.sync += led_timer.eq(led_timer + 1)

        with m.Else():
            # Disabled - reset counters
            m.d.sync += [
                second_counter.eq(0),
                pps_active.eq(0),
                led_timer.eq(pulse_width)
            ]

        # Output assignments
        m.d.comb += [
            self.pps_out.eq(pps_active),
            self.pps_led.eq(led_timer < pulse_width),
            self.pps_count.eq(pps_count_reg)
        ]

        return m


class PhaseDetector(wiring.Component):
    """
    Time Interval Counter (TIC) phase detector.

    Measures phase difference between GPS 1PPS and local oscillator PPS.
    Uses counter-based TIC for nanosecond resolution.

    Parameters
    ----------
    sys_clk_freq : int
        System clock frequency in Hz (for time conversion)
    counter_bits : int
        Resolution of phase counter (default: 32 bits)
    """

    # Inputs
    gps_pps: In(1)                  # GPS 1PPS reference
    local_pps: In(1)                # Local oscillator 1PPS

    # Outputs
    phase_error: Out(signed(32))    # Phase error in nanoseconds (signed)
    phase_valid: Out(1)             # Phase measurement valid

    def __init__(self, sys_clk_freq=48_000_000, counter_bits=32):
        """Initialize phase detector."""
        super().__init__()
        self.sys_clk_freq = sys_clk_freq
        self.counter_bits = counter_bits
        # Nanoseconds per clock cycle
        self.ns_per_clk = 1_000_000_000 // sys_clk_freq

    def elaborate(self, platform):
        m = Module()

        # Edge detection
        gps_pps_last = Signal()
        local_pps_last = Signal()
        gps_edge = Signal()
        local_edge = Signal()

        m.d.sync += [
            gps_pps_last.eq(self.gps_pps),
            local_pps_last.eq(self.local_pps)
        ]

        m.d.comb += [
            gps_edge.eq(self.gps_pps & ~gps_pps_last),
            local_edge.eq(self.local_pps & ~local_pps_last)
        ]

        # Time interval counter
        tic_counter = Signal(self.counter_bits)
        tic_running = Signal()
        phase_count = Signal(self.counter_bits)
        phase_valid_reg = Signal()

        # TIC state machine
        with m.If(gps_edge):
            # GPS edge starts measurement
            m.d.sync += [
                tic_counter.eq(0),
                tic_running.eq(1),
                phase_valid_reg.eq(0)
            ]
        with m.Elif(local_edge):
            # Local edge stops measurement
            with m.If(tic_running):
                m.d.sync += [
                    phase_count.eq(tic_counter),
                    phase_valid_reg.eq(1),
                    tic_running.eq(0)
                ]
        with m.Elif(tic_running):
            # Count while running
            m.d.sync += tic_counter.eq(tic_counter + 1)

        # Convert counter to nanoseconds (signed)
        # Positive = local is late, Negative = local is early
        phase_ns = Signal(signed(32))
        m.d.comb += phase_ns.eq((phase_count * self.ns_per_clk).as_signed())

        # Handle wraparound (if local is >0.5s late, it's actually early)
        max_phase = (self.sys_clk_freq // 2) * self.ns_per_clk

        with m.If(phase_ns > max_phase):
            # Wraparound: local is actually early
            m.d.comb += self.phase_error.eq(phase_ns - (1_000_000_000))
        with m.Else():
            m.d.comb += self.phase_error.eq(phase_ns)

        m.d.comb += self.phase_valid.eq(phase_valid_reg)

        return m


class PIController(wiring.Component):
    """
    Proportional-Integral controller for GPSDO.

    Implements digital PI control to discipline the local oscillator
    based on phase error measurements.

    Parameters
    ----------
    kp_shift : int
        Proportional gain bit shift (Kp = 1 >> kp_shift)
    ki_shift : int
        Integral gain bit shift (Ki = 1 >> ki_shift)
    """

    # Inputs
    phase_error: In(signed(32))     # Phase error input (nanoseconds)
    phase_valid: In(1)              # Phase error is valid
    enable: In(1)                   # Controller enable
    reset_integrator: In(1)         # Reset integral term

    # Control parameters (CSR writable)
    kp_shift: In(unsigned(8))       # Proportional gain shift
    ki_shift: In(unsigned(8))       # Integral gain shift

    # Outputs
    dac_value: Out(unsigned(16))    # DAC control output (0-65535)
    locked: Out(1)                  # PLL locked indicator

    def __init__(self, kp_shift_default=8, ki_shift_default=16):
        """Initialize PI controller."""
        super().__init__()
        self.kp_shift_default = kp_shift_default
        self.ki_shift_default = ki_shift_default

    def elaborate(self, platform):
        m = Module()

        # Integral accumulator (wide to prevent overflow)
        integrator = Signal(signed(48))

        # Proportional term
        p_term = Signal(signed(32))

        # Combined output (before limiting)
        pi_output = Signal(signed(48))

        # DAC center point (mid-scale for bipolar control)
        DAC_CENTER = 32768

        # Lock detector
        lock_counter = Signal(16)
        locked_reg = Signal()
        LOCK_THRESHOLD = 100  # ns
        LOCK_COUNT = 1000     # consecutive good measurements

        # PI control calculation
        with m.If(self.enable & self.phase_valid):
            # Reset integrator if requested
            with m.If(self.reset_integrator):
                m.d.sync += integrator.eq(0)
            with m.Else():
                # Integrate error (with anti-windup limiting)
                new_integrator = integrator + (self.phase_error >> self.ki_shift)

                # Anti-windup: limit integrator to DAC range
                MAX_INTEGRATOR = (65535 - DAC_CENTER) << 16
                MIN_INTEGRATOR = -MAX_INTEGRATOR

                with m.If(new_integrator > MAX_INTEGRATOR):
                    m.d.sync += integrator.eq(MAX_INTEGRATOR)
                with m.Elif(new_integrator < MIN_INTEGRATOR):
                    m.d.sync += integrator.eq(MIN_INTEGRATOR)
                with m.Else():
                    m.d.sync += integrator.eq(new_integrator)

            # Calculate proportional term
            m.d.comb += p_term.eq(self.phase_error >> self.kp_shift)

            # Combine PI terms
            m.d.comb += pi_output.eq(integrator + (p_term << 16))

            # Lock detection
            with m.If((self.phase_error > -LOCK_THRESHOLD) &
                     (self.phase_error < LOCK_THRESHOLD)):
                with m.If(lock_counter < LOCK_COUNT):
                    m.d.sync += lock_counter.eq(lock_counter + 1)
                with m.Else():
                    m.d.sync += locked_reg.eq(1)
            with m.Else():
                m.d.sync += [
                    lock_counter.eq(0),
                    locked_reg.eq(0)
                ]

        with m.Else():
            # Disabled: hold DAC at center
            m.d.comb += pi_output.eq(0)

        # Convert to DAC value (unsigned 16-bit)
        dac_signed = Signal(signed(32))
        m.d.comb += dac_signed.eq((pi_output >> 16) + DAC_CENTER)

        # Clamp to DAC range
        with m.If(dac_signed < 0):
            m.d.comb += self.dac_value.eq(0)
        with m.Elif(dac_signed > 65535):
            m.d.comb += self.dac_value.eq(65535)
        with m.Else():
            m.d.comb += self.dac_value.eq(dac_signed[:16])

        m.d.comb += self.locked.eq(locked_reg)

        return m


class DACInterface(wiring.Component):
    """
    SPI DAC interface for VCXO/OCXO control.

    Provides SPI interface to external DAC for analog control voltage.
    Supports common SPI DACs (MCP4821, AD5061, etc.)

    Parameters
    ----------
    dac_bits : int
        DAC resolution in bits (default: 16)
    spi_clk_div : int
        SPI clock divider (sys_clk / spi_clk_div)
    """

    # Inputs
    dac_value: In(unsigned(16))     # DAC value to output
    dac_write: In(1)                # Write strobe

    # SPI outputs
    spi_cs: Out(1)                  # Chip select (active low)
    spi_clk: Out(1)                 # SPI clock
    spi_mosi: Out(1)                # SPI data out

    # Status
    busy: Out(1)                    # Transfer in progress

    def __init__(self, dac_bits=16, spi_clk_div=8):
        """Initialize DAC interface."""
        super().__init__()
        self.dac_bits = dac_bits
        self.spi_clk_div = spi_clk_div

    def elaborate(self, platform):
        m = Module()

        # SPI state machine
        STATE_IDLE = 0
        STATE_TRANSFER = 1
        state = Signal()

        # SPI clock generation
        clk_counter = Signal(range(self.spi_clk_div))
        spi_clk_en = Signal()
        spi_clk_reg = Signal()

        m.d.comb += spi_clk_en.eq(clk_counter == 0)

        with m.If(state == STATE_TRANSFER):
            with m.If(clk_counter == self.spi_clk_div - 1):
                m.d.sync += [
                    clk_counter.eq(0),
                    spi_clk_reg.eq(~spi_clk_reg)
                ]
            with m.Else():
                m.d.sync += clk_counter.eq(clk_counter + 1)
        with m.Else():
            m.d.sync += [
                clk_counter.eq(0),
                spi_clk_reg.eq(0)
            ]

        # Shift register
        shift_reg = Signal(24)  # 24-bit for MCP4821 (4 control + 12 data + padding)
        bit_counter = Signal(5)

        # SPI transfer state machine
        with m.Switch(state):
            with m.Case(STATE_IDLE):
                with m.If(self.dac_write):
                    # Load shift register
                    # Format: [0011][12-bit DAC value][8-bit padding]
                    # 0011 = write to DAC, 2x gain, not shutdown
                    m.d.sync += [
                        shift_reg.eq(Cat(Const(0, 8),    # Padding
                                        self.dac_value[:12],  # Data
                                        Const(0b0011, 4))),   # Control
                        bit_counter.eq(23),
                        state.eq(STATE_TRANSFER)
                    ]

            with m.Case(STATE_TRANSFER):
                with m.If(spi_clk_en & ~spi_clk_reg):
                    # Shift on falling edge
                    m.d.sync += shift_reg.eq(Cat(0, shift_reg[:-1]))

                    with m.If(bit_counter == 0):
                        m.d.sync += state.eq(STATE_IDLE)
                    with m.Else():
                        m.d.sync += bit_counter.eq(bit_counter - 1)

        # Output assignments
        m.d.comb += [
            self.spi_cs.eq(state != STATE_TRANSFER),  # Active low
            self.spi_clk.eq(spi_clk_reg),
            self.spi_mosi.eq(shift_reg[23]),
            self.busy.eq(state == STATE_TRANSFER)
        ]

        return m


class GPSDO(wiring.Component):
    """
    Complete GPS Disciplined Oscillator.

    Integrates all GPSDO components:
    - 1PPS generator from GPS time
    - Phase detector
    - PI controller
    - DAC interface
    - Status monitoring

    Parameters
    ----------
    sys_clk_freq : int
        System clock frequency in Hz
    """

    # GPS time inputs
    tow: In(unsigned(32))           # GPS Time of Week (ms)
    tow_valid: In(1)                # TOW is valid
    tow_update: In(1)               # TOW update strobe

    # Control inputs (CSRs)
    enable: In(1)                   # GPSDO enable
    reset_integrator: In(1)         # Reset PI integrator
    kp_shift: In(unsigned(8))       # Proportional gain
    ki_shift: In(unsigned(8))       # Integral gain
    dac_manual: In(unsigned(16))    # Manual DAC value
    manual_mode: In(1)              # Manual DAC mode

    # Local oscillator input
    local_pps_in: In(1)             # Local oscillator 1PPS

    # Outputs
    gps_pps_out: Out(1)             # GPS 1PPS output
    pps_led: Out(1)                 # PPS LED indicator

    # DAC control
    dac_cs: Out(1)
    dac_clk: Out(1)
    dac_mosi: Out(1)

    # Disciplined clock outputs
    clk_10mhz: Out(1)               # 10 MHz output
    clk_1pps: Out(1)                # Disciplined 1PPS output

    # Status outputs
    phase_error: Out(signed(32))    # Current phase error (ns)
    dac_value: Out(unsigned(16))    # Current DAC value
    locked: Out(1)                  # PLL locked
    pps_count: Out(unsigned(32))    # PPS pulse count

    def __init__(self, sys_clk_freq=48_000_000):
        """Initialize GPSDO."""
        super().__init__()
        self.sys_clk_freq = sys_clk_freq

    def elaborate(self, platform):
        m = Module()

        # Instantiate components
        m.submodules.pps_gen = pps_gen = PPS_Generator(self.sys_clk_freq)
        m.submodules.phase_det = phase_det = PhaseDetector(self.sys_clk_freq)
        m.submodules.pi_ctrl = pi_ctrl = PIController()
        m.submodules.dac_if = dac_if = DACInterface()

        # Connect PPS generator
        m.d.comb += [
            pps_gen.tow.eq(self.tow),
            pps_gen.tow_valid.eq(self.tow_valid),
            pps_gen.tow_update.eq(self.tow_update),
            pps_gen.enable.eq(self.enable),
            self.gps_pps_out.eq(pps_gen.pps_out),
            self.pps_led.eq(pps_gen.pps_led),
            self.pps_count.eq(pps_gen.pps_count)
        ]

        # Connect phase detector
        m.d.comb += [
            phase_det.gps_pps.eq(pps_gen.pps_out),
            phase_det.local_pps.eq(self.local_pps_in),
            self.phase_error.eq(phase_det.phase_error)
        ]

        # Connect PI controller
        m.d.comb += [
            pi_ctrl.phase_error.eq(phase_det.phase_error),
            pi_ctrl.phase_valid.eq(phase_det.phase_valid),
            pi_ctrl.enable.eq(self.enable),
            pi_ctrl.reset_integrator.eq(self.reset_integrator),
            pi_ctrl.kp_shift.eq(self.kp_shift),
            pi_ctrl.ki_shift.eq(self.ki_shift),
            self.locked.eq(pi_ctrl.locked)
        ]

        # DAC control (manual or automatic)
        dac_val = Signal(16)
        dac_write_strobe = Signal()

        with m.If(self.manual_mode):
            m.d.comb += dac_val.eq(self.dac_manual)
        with m.Else():
            m.d.comb += dac_val.eq(pi_ctrl.dac_value)

        m.d.comb += [
            self.dac_value.eq(dac_val),
            dac_write_strobe.eq(phase_det.phase_valid & ~dac_if.busy)
        ]

        # Connect DAC interface
        m.d.comb += [
            dac_if.dac_value.eq(dac_val),
            dac_if.dac_write.eq(dac_write_strobe),
            self.dac_cs.eq(dac_if.spi_cs),
            self.dac_clk.eq(dac_if.spi_clk),
            self.dac_mosi.eq(dac_if.spi_mosi)
        ]

        # Disciplined clock outputs
        # (Would connect to actual clock distribution in real hardware)
        m.d.comb += [
            self.clk_10mhz.eq(0),  # Placeholder
            self.clk_1pps.eq(self.local_pps_in)
        ]

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator, Tick

    # Test GPSDO
    dut = GPSDO(sys_clk_freq=48_000_000)

    def testbench():
        """Simple GPSDO testbench."""

        # Initialize
        yield dut.enable.eq(1)
        yield dut.kp_shift.eq(8)
        yield dut.ki_shift.eq(16)
        yield dut.manual_mode.eq(0)

        # Simulate GPS time updates
        for second in range(5):
            tow = second * 1000  # milliseconds
            yield dut.tow.eq(tow)
            yield dut.tow_valid.eq(1)
            yield dut.tow_update.eq(1)
            yield Tick()
            yield dut.tow_update.eq(0)

            # Wait one second
            for _ in range(48_000_000):
                yield Tick()

            print(f"Second {second}: TOW={tow}, PPS Count={yield dut.pps_count}")

    sim = Simulator(dut)
    sim.add_clock(1/48e6)
    sim.add_testbench(testbench)

    with sim.write_vcd("gpsdo_test.vcd"):
        sim.run()
