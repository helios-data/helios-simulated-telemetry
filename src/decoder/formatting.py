"""
Pure display helpers: hex dumps, enum name lookup, and formatted packet printing.
"""

from helios.generated.helios.cots import  TelemetryPacket, FlightState


_FLIGHT_STATE_NAMES = {
  FlightState.STANDBY:        "STANDBY",
  FlightState.ASCENT:         "ASCENT",
  FlightState.MACH_LOCK:      "MACH_LOCK",
  FlightState.DROGUE_DESCENT: "DROGUE_DESCENT",
  FlightState.MAIN_DESCENT:   "MAIN_DESCENT",
  FlightState.LANDED:         "LANDED",
}


def flight_state_name(state: FlightState) -> str:
  """Convert a FlightState enum value to a human-readable string."""
  return _FLIGHT_STATE_NAMES.get(state, f"UNKNOWN({state})")


def hexdump(data: bytes, prefix: str = "  ") -> str:
  """Format bytes as a hex dump with ASCII representation."""
  lines = []
  for i in range(0, len(data), 16):
    chunk = data[i:i + 16]
    hex_part = " ".join(f"{b:02x}" for b in chunk)
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    lines.append(f"{prefix}{i:04x}: {hex_part:<48} |{ascii_part}|")
  return "\n".join(lines)


def print_compact(index: int, packet: TelemetryPacket) -> None:
  """Print a single-line summary of a packet."""
  baro_parts = [
    "B0:OK"   if packet.barometers[0].healthy else "B0:FAIL",
    "B1:OK"   if packet.barometers[1].healthy else "B1:FAIL",
  ]
  gps_info = (
    f"GPS: {packet.gps_latitude:.5f},{packet.gps_longitude:.5f}"
    f" ({packet.gps_sats}sats)"
  )
  print(
    f"[{index}] t={packet.timestamp_ms:>8}ms | "
    f"{flight_state_name(packet.state):14} | "
    f"Alt: {packet.kf_altitude:>8.2f}m | "
    f"Vel: {packet.kf_velocity:>7.2f}m/s | "
    f"{gps_info} | "
    f"{' '.join(baro_parts)}"
  )


def print_verbose(index: int, packet: TelemetryPacket) -> None:
  assert(packet.accel != None)
  assert(packet.gyro != None)

  """Print all fields of a packet."""
  state = flight_state_name(packet.state)
  print(f"[{index}] TelemetryPacket:")
  print(f"    counter:         {packet.counter}")
  print(f"    timestamp_ms:    {packet.timestamp_ms}")
  print(f"    state:           {state}")
  print(f"    accel_x:         {packet.accel.x:.4f}")
  print(f"    accel_y:         {packet.accel.y:.4f}")
  print(f"    accel_z:         {packet.accel.z:.4f}")
  print(f"    gyro_x:          {packet.gyro.x:.4f}")
  print(f"    gyro_y:          {packet.gyro.y:.4f}")
  print(f"    gyro_z:          {packet.gyro.z:.4f}")
  print(f"    kf_altitude:     {packet.kf_altitude:.4f}")
  print(f"    kf_velocity:     {packet.kf_velocity:.4f}")
  print(f"    kf_alt_variance: {packet.kf_alt_variance:.4f}")
  print(f"    kf_vel_variance: {packet.kf_vel_variance:.4f}")
  print(f"    baro0_healthy:   {packet.barometers[0].healthy}")
  print(f"    baro0_pressure:  {packet.barometers[0].pressure:.2f}")
  print(f"    baro0_temp:      {packet.barometers[0].temperature:.2f}")
  print(f"    baro0_altitude:  {packet.barometers[0].altitude:.4f}")
  print(f"    baro0_nis:       {packet.barometers[0].nis:.4f}")
  print(f"    baro0_faults:    {packet.barometers[0].faults}")
  print(f"    baro1_healthy:   {packet.barometers[1].healthy}")
  print(f"    baro1_pressure:  {packet.barometers[1].pressure:.2f}")
  print(f"    baro1_temp:      {packet.barometers[1].temperature:.2f}")
  print(f"    baro1_altitude:  {packet.barometers[1].altitude:.4f}")
  print(f"    baro1_nis:       {packet.barometers[1].nis:.4f}")
  print(f"    baro1_faults:    {packet.barometers[1].faults}")
  print(f"    ground_altitude: {packet.ground_altitude:.4f}")
  print(f"    gps_latitude:    {packet.gps_latitude:.6f}")
  print(f"    gps_longitude:   {packet.gps_longitude:.6f}")
  print(f"    gps_altitude:    {packet.gps_altitude:.2f}")
  print(f"    gps_speed:       {packet.gps_speed:.2f}")
  print(f"    gps_sats:        {packet.gps_sats}")
  print(f"    gps_fix:         {packet.gps_fix}")
  print()