"""
CSV logger for TelemetryPacket data.
"""

import csv
from datetime import datetime
from pathlib import Path

from helios.generated.helios.cots import TelemetryPacket
from decoder.formatting import flight_state_name


COLUMNS = [
  "recv_time",
  "counter",
  "timestamp_ms",
  "state",
  "accel_x",
  "accel_y",
  "accel_z",
  "gyro_x",
  "gyro_y",
  "gyro_z",
  "kf_altitude",
  "kf_velocity",
  "kf_alt_variance",
  "kf_vel_variance",
  "baro0_healthy",
  "baro1_healthy",
  "baro0_pressure",
  "baro0_temperature",
  "baro0_altitude",
  "baro0_nis",
  "baro0_faults",
  "baro1_pressure",
  "baro1_temperature",
  "baro1_altitude",
  "baro1_nis",
  "baro1_faults",
  "ground_altitude",
  "gps_latitude",
  "gps_longitude",
  "gps_altitude",
  "gps_speed",
  "gps_sats",
  "gps_fix",
]


def packet_to_row(packet: TelemetryPacket) -> list:
  """Convert a TelemetryPacket to a CSV row aligned with COLUMNS."""
  assert(packet.accel != None)
  assert(packet.gyro != None)

  return [
    datetime.now().isoformat(timespec='milliseconds'),
    packet.counter,
    packet.timestamp_ms,
    flight_state_name(packet.state),
    packet.accel.x,
    packet.accel.y,
    packet.accel.z,
    packet.gyro.x,
    packet.gyro.y,
    packet.gyro.z,
    packet.kf_altitude,
    packet.kf_velocity,
    packet.kf_alt_variance,
    packet.kf_vel_variance,
    packet.barometers[0].healthy,
    packet.barometers[0].pressure,
    packet.barometers[0].temperature,
    packet.barometers[0].altitude,
    packet.barometers[0].nis,
    packet.barometers[0].faults,
    packet.barometers[1].healthy,
    packet.barometers[1].pressure,
    packet.barometers[1].temperature,
    packet.barometers[1].altitude,
    packet.barometers[1].nis,
    packet.barometers[1].faults,
    packet.ground_altitude,
    packet.gps_latitude,
    packet.gps_longitude,
    packet.gps_altitude,
    packet.gps_speed,
    packet.gps_sats,
    packet.gps_fix,
  ]


class CsvLogger:
  """
  Writes TelemetryPacket rows to a CSV file.

  Opens the file on __enter__ and writes the header row immediately,
  so a zero-packet run still produces a valid (header-only) CSV.

  Args:
    path: Destination file path.  Parent directories are created
      automatically if they do not exist.

  Usage:
    with CsvLogger("/data/telemetry.csv") as log:
      log.write(packet)
  """

  def __init__(self, path: str | Path) -> None:
    self._path = Path(path)
    self._file = None
    self._writer = None

  def __enter__(self) -> "CsvLogger":
    self._path.parent.mkdir(parents=True, exist_ok=True)
    self._file = open(self._path, "w", newline="")
    self._writer = csv.writer(self._file)
    self._writer.writerow(COLUMNS)
    return self

  def __exit__(self, *_) -> None:
    if self._file:
      self._file.close()

  def write(self, packet: TelemetryPacket) -> None:
    """Append one packet as a CSV row and flush immediately."""
    assert self._writer is not None, "CsvLogger must be used as a context manager"
    self._writer.writerow(packet_to_row(packet))
    if self._file:
      self._file.flush()