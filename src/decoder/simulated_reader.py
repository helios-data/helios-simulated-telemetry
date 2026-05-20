import math
import struct
import time
from typing import Generator

import crcmod
from cobs import cobs

from generated import FlightState, TelemetryPacket

_crc16 = crcmod.predefined.mkCrcFun('kermit')
_INTERVAL = 0.1  # 10 Hz


def _encode(packet: TelemetryPacket) -> bytes:
    """TelemetryPacket → protobuf → CRC-16 (little-endian) → COBS."""
    payload = bytes(packet)
    framed = payload + struct.pack('<H', _crc16(payload))
    return cobs.encode(framed)


def _make_packet(counter: int, t: float) -> TelemetryPacket:
    # Simple parabolic flight arc: launch at t=5s, apogee at t=30s, land at t=180s
    if t < 5:
        state, alt, vel = FlightState.STANDBY, 0.0, 0.0
    elif t < 30:
        frac = (t - 5) / 25
        state = FlightState.ASCENT
        alt = 3000 * math.sin(frac * math.pi / 2)
        vel = 200 * math.cos(frac * math.pi / 2)
    elif t < 35:
        state, alt, vel = FlightState.MACH_LOCK, 3000.0, 0.0
    elif t < 90:
        frac = (t - 35) / 55
        state = FlightState.DROGUE_DESCENT
        alt = 3000 * (1 - frac)
        vel = -55.0
    elif t < 180:
        frac = (t - 90) / 90
        state = FlightState.MAIN_DESCENT
        alt = max(0, 3000 * (1 - (35 / 55)) * (1 - frac))
        vel = -8.0
    else:
        state, alt, vel = FlightState.LANDED, 0.0, 0.0

    accel_z = 9.8 + (vel * 0.05)  # rough thrust/drag estimate

    return TelemetryPacket(
        counter=counter,
        timestamp_ms=int(t * 1000),
        state=state,
        accel_x=math.sin(t * 0.3) * 0.5,
        accel_y=math.cos(t * 0.3) * 0.5,
        accel_z=accel_z,
        gyro_x=math.sin(t * 0.1) * 2.0,
        gyro_y=math.cos(t * 0.1) * 2.0,
        gyro_z=0.1,
        kf_altitude=alt,
        kf_velocity=vel,
        kf_alt_variance=0.5,
        kf_vel_variance=0.1,
        baro0_healthy=True,
        baro1_healthy=True,
        baro0_altitude=alt + math.sin(t) * 2,
        baro1_altitude=alt + math.cos(t) * 2,
        ground_altitude=0.0,
        gps_latitude=34.0522,
        gps_longitude=-118.2437,
        gps_altitude=alt,
        gps_speed=abs(vel),
        gps_sats=8,
        gps_fix=3,
    )


class SimulatedReader:
    def __init__(self, interval: float = _INTERVAL) -> None:
        self._interval = interval

    def __enter__(self) -> "SimulatedReader":
        return self

    def __exit__(self, *_) -> None:
        pass

    def packets(self) -> Generator[bytes, None, None]:
        counter = 0
        start = time.monotonic()
        while True:
            t = time.monotonic() - start
            yield _encode(_make_packet(counter, t))
            counter += 1
            time.sleep(self._interval)
