import math
import struct
import time
from typing import Generator

import crcmod
from cobs import cobs

from generated import FlightState, TelemetryPacket

_crc16 = crcmod.predefined.mkCrcFun('kermit')
_INTERVAL = 0.1  # 10 Hz

# Midland, TX launch site
_LAUNCH_LAT = 31.9973
_LAUNCH_LON = -102.0779
_METERS_PER_DEG_LAT = 111_000.0
_METERS_PER_DEG_LON = 111_000.0 * math.cos(math.radians(_LAUNCH_LAT))

# Simulated wind drift while airborne
_DRIFT_NORTH_MPS = 8.0
_DRIFT_EAST_MPS = 5.0

# When the flight should start
_FLIGHT_START_DELAY = 25.0


def _encode(packet: TelemetryPacket) -> bytes:
    """TelemetryPacket → protobuf → CRC-16 (little-endian) → COBS."""
    payload = bytes(packet)
    framed = payload + struct.pack('<H', _crc16(payload))
    return cobs.encode(framed)


def _make_packet(counter: int, t: float) -> TelemetryPacket:
    # Simple parabolic flight arc: launch at t=5s, apogee at t=30s, land at t=180s
    if t < _FLIGHT_START_DELAY + 5:
        state, alt, vel = FlightState.STANDBY, 0.0, 0.0
    elif t < _FLIGHT_START_DELAY + 30:
        frac = (t - _FLIGHT_START_DELAY - 5) / 25
        state = FlightState.ASCENT
        alt = 3000 * math.sin(frac * math.pi / 2)
        vel = 200 * math.cos(frac * math.pi / 2)
    elif t < _FLIGHT_START_DELAY + 35:
        state, alt, vel = FlightState.MACH_LOCK, 3000.0, 0.0
    elif t < _FLIGHT_START_DELAY + 90:
        frac = (t - _FLIGHT_START_DELAY - 35) / 55
        state = FlightState.DROGUE_DESCENT
        alt = 3000 * (1 - frac)
        vel = -55.0
    elif t < _FLIGHT_START_DELAY + 180:
        frac = (t - _FLIGHT_START_DELAY - 90) / 90
        state = FlightState.MAIN_DESCENT
        alt = max(0, 3000 * (1 - (35 / 55)) * (1 - frac))
        vel = -8.0
    else:
        state, alt, vel = FlightState.LANDED, 0.0, 0.0

    accel_z = 9.8 + (vel * 0.05)  # rough thrust/drag estimate
    airborne_s = max(0.0, min(t - _FLIGHT_START_DELAY - 5.0, 175.0))  # seconds since liftoff, frozen at landing

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
        gps_latitude=_LAUNCH_LAT + (_DRIFT_NORTH_MPS * airborne_s) / _METERS_PER_DEG_LAT,
        gps_longitude=_LAUNCH_LON + (_DRIFT_EAST_MPS * airborne_s) / _METERS_PER_DEG_LON,
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
