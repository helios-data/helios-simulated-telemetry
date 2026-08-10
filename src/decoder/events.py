"""
Derived event simulation.

The primary telemetry stream is a `TelemetryPacket`.  Downstream Helios
services normally republish that stream as higher-level events; here we
synthesise plausible versions of three of them directly from a decoded
`TelemetryPacket` so consumers have realistic data to work with:

  aprs                → AprsPacket        (helios.generated.helios.transport)
  ground_position     → NmeaSentence      (protos-temp/nmea.proto)
  landing_prediction  → LandingPrediction (protos-temp/landing.proto)
"""

import math

from generated import FlightState, LandingPoint, LandingPrediction, TelemetryPacket
from generated.helios.transport import (
    NmeaPosition,
    NmeaPositionFixQuality,
    NmeaSentence,
)
from helios.generated.helios.transport import AprsPacket, AprsPosition


# APRS station identity for the simulated flight computer
_APRS_SOURCE = "KD9HLO-11"
_APRS_DEST = "APZHEL"
_APRS_PATH = ["WIDE1-1", "WIDE2-1"]
_APRS_SYMBOL = "/O"  # primary table, balloon/rocket

_METERS_TO_FEET = 3.28084
_MPS_TO_KNOTS = 1.94384

# Horizontal wind the landing predictor assumes (m/s).  Independent of the
# reader's true drift — a real predictor only has a wind estimate.
_ASSUMED_WIND_NORTH_MPS = 6.0
_ASSUMED_WIND_EAST_MPS = 4.0
_METERS_PER_DEG_LAT = 111_000.0


def _course_deg(packet: TelemetryPacket) -> float:
  """Approximate course-over-ground from the assumed drift direction."""
  return (math.degrees(math.atan2(_ASSUMED_WIND_EAST_MPS, _ASSUMED_WIND_NORTH_MPS))) % 360.0


def build_aprs(packet: TelemetryPacket) -> AprsPacket:
  """A position-report APRS packet derived from the telemetry GPS fix."""
  return AprsPacket(
    source=_APRS_SOURCE,
    destination=_APRS_DEST,
    path=list(_APRS_PATH),
    position=AprsPosition(
      latitude=packet.gps_latitude,
      longitude=packet.gps_longitude,
      altitude_ft=packet.gps_altitude * _METERS_TO_FEET,
      course_deg=_course_deg(packet),
      speed_knots=packet.gps_speed * _MPS_TO_KNOTS,
      symbol=_APRS_SYMBOL,
      comment="Helios SRAD",
    ),
  )


def build_ground_position(packet: TelemetryPacket) -> NmeaSentence:
  """A decoded NMEA GGA sentence derived from the telemetry GPS fix."""
  fix = (
    NmeaPositionFixQuality.GPS
    if packet.gps_fix >= 1
    else NmeaPositionFixQuality.INVALID
  )
  return NmeaSentence(
    talker_id="GP",
    sentence_type="GGA",
    checksum_valid=True,
    position=NmeaPosition(
      latitude=packet.gps_latitude,
      longitude=packet.gps_longitude,
      altitude_m=packet.gps_altitude,
      course_deg=_course_deg(packet),
      speed_knots=packet.gps_speed * _MPS_TO_KNOTS,
      fix_quality=fix,
      satellites_used=packet.gps_sats,
      hdop=0.9,
    ),
  )


def build_landing_prediction(packet: TelemetryPacket) -> LandingPrediction:
  """
  A landing estimate: project the current position forward by the assumed
  horizontal wind over the time remaining until touchdown.
  """
  descending = packet.kf_velocity < -0.5
  landed = packet.state == FlightState.LANDED

  if landed:
    status = "final"
    remaining_s = 0.0
  elif descending:
    status = "predicting"
    # time to reach the ground at the current descent rate
    remaining_s = packet.kf_altitude / abs(packet.kf_velocity)
  else:
    status = "not_descending"
    remaining_s = 0.0

  meters_per_deg_lon = _METERS_PER_DEG_LAT * math.cos(
    math.radians(packet.gps_latitude)
  )
  est_lat = packet.gps_latitude + (
    _ASSUMED_WIND_NORTH_MPS * remaining_s
  ) / _METERS_PER_DEG_LAT
  est_lon = packet.gps_longitude + (
    _ASSUMED_WIND_EAST_MPS * remaining_s
  ) / meters_per_deg_lon

  best = LandingPoint(lat=est_lat, lon=est_lon)

  return LandingPrediction(
    based_on_packet_counter=packet.counter,
    computed_at_ms=packet.timestamp_ms,
    final=landed,
    best_estimate=best,
    dispersion_cloud=[best],
    current_lat=packet.gps_latitude,
    current_lon=packet.gps_longitude,
    current_source="srad",
    wind_source="live",
    descent_model="constant",
    current_alt_agl=packet.kf_altitude,
    flight_state=float(int(packet.state)),
    status=status,
  )
