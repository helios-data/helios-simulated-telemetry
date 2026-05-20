"""
Entry point for the simulated telemetry service.

Configuration is read from environment variables first, with CLI flags
as overrides. This makes the service easy to configure in Docker Compose
without rebuilding the image.

Environment variables:
  CSV_OUTPUT_PATH    CSV log file path           (default: no logging)
"""

import argparse
import asyncio
import os
import sys
import contextlib

from helios import HeliosClient

from decoder.csv_logger import CsvLogger
from decoder.formatting import print_compact, print_verbose
from decoder.packet import decode_packet
from decoder.simulated_reader import SimulatedReader


def build_config() -> argparse.Namespace:
  """Parse CLI args, falling back to environment variables for each option."""
  parser = argparse.ArgumentParser(
    description="Simulate COBS/CRC/Protobuf telemetry packets",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  )
  parser.add_argument(
    "-v", "--verbose",
    action="store_true",
    help="Print all fields (default: compact one-liner)",
  )
  parser.add_argument(
    "-d", "--debug",
    action="store_true",
    help="Hex-dump each decode stage to stderr",
  )
  parser.add_argument(
    "-o", "--output",
    default=os.environ.get("CSV_OUTPUT_PATH"),
    metavar="FILE",
    help="CSV log file path.  Env: CSV_OUTPUT_PATH",
  )

  return parser.parse_args()


async def _wait_first(*events: asyncio.Event) -> None:
  """Return as soon as any one of the given events is set."""
  tasks = [asyncio.create_task(e.wait()) for e in events]
  try:
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
  finally:
    for t in tasks:
      t.cancel()
      with contextlib.suppress(asyncio.CancelledError):
        await t


async def helios_manager(
  sdk: HeliosClient,
  ready: asyncio.Event,
  connection_lost: asyncio.Event,
  stop: asyncio.Event,
  retry_delays: tuple[int, ...] = (2, 5),
) -> None:
  """
  Manages the Helios connection lifecycle independently of the reader.

  Flow:
    1. Try to connect.
    2. On success  → set `ready`, then wait for either a `connection_lost`
                      signal (reader got a send failure) or a `stop` signal.
    3. On failure  → clear `ready`, back off, then loop.
    4. On stop     → disconnect and return.
  """
  attempt = 0

  while not stop.is_set():
    connection_lost.clear()
    try:
      await sdk.connect()
      ready.set()
      label = "Connected" if attempt == 0 else "Reconnected"
      print(f"[Helios] {label}")
      attempt = 0

      # Stay here until the reader reports a dead connection or we shut down
      await _wait_first(connection_lost, stop)
      ready.clear()

      if stop.is_set():
        break

      print("[Helios] Connection lost — scheduling reconnect…", file=sys.stderr)

    except Exception as e:
      ready.clear()
      delay = retry_delays[min(attempt, len(retry_delays) - 1)]
      label = "Initial connection" if attempt == 0 else "Reconnect"
      print(
        f"[Helios] {label} failed: {e}. Retrying in {delay}s…",
        file=sys.stderr,
      )
      attempt += 1
      # Interruptible sleep — exits early if stop fires
      with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=delay)

  ready.clear()
  with contextlib.suppress(Exception):
    await sdk.disconnect()
  print("[Helios] Manager exited.")


async def main_loop(args: argparse.Namespace) -> None:
  """Main loop — read packets, decode them, log and display."""

  reader_ctx = SimulatedReader()

  helios_sdk = HeliosClient(
    core_address="Helios",
    core_port=5000,
    node_uri="Helios.FALCON.Telemetry",
  )

  # Shared coordination events
  helios_ready      = asyncio.Event()   # set = currently connected
  connection_lost   = asyncio.Event()   # reader sets this on send failure
  stop              = asyncio.Event()   # graceful shutdown signal

  # Helios runs in the background — the reader never waits on it
  manager_task = asyncio.create_task(
    helios_manager(helios_sdk, helios_ready, connection_lost, stop)
  )

  logger_ctx    = CsvLogger(args.output) if args.output else _NullLogger()

  try:
    with reader_ctx as reader, logger_ctx as logger:
      if args.output:
        print(f"Logging to {args.output}")
      print("Simulating packets…\n")

      packet_gen = reader.packets()
      packet_count = 0

      while True:
        raw = await asyncio.to_thread(next, packet_gen, None)
        if raw is None or len(raw) < 15:
          continue

        packet_count += 1

        if args.debug:
          print(f"[{packet_count}] Raw COBS ({len(raw)} bytes): {raw.hex()}")

        packet = decode_packet(raw, debug=args.debug)
        if packet is None:
          continue

        # Helios send: non-blocking
        if helios_ready.is_set():
          try:
            await helios_sdk.publish_event(
              event_name="telemetry",
              data=bytes(raw),
            )
          except Exception as e:
            print(f"[Helios] Send failed: {e}", file=sys.stderr)
            helios_ready.clear()
            connection_lost.set()   # wake the manager to reconnect

        if logger:
          logger.write(packet)

        if args.verbose:
          print_verbose(packet_count, packet)
        else:
          print_compact(packet_count, packet)

  except KeyboardInterrupt:
    print("\nExiting…")
    if args.output:
        print(f"CSV saved to {args.output}")
  except Exception as exc:
    print(f"\n[ERROR] Unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
  finally:
    stop.set()                           # tell the manager to exit cleanly
    await manager_task                   # wait for it to disconnect and return

# Used when CSV logging is disabled
class _NullLogger:
  def __enter__(self): return None
  def __exit__(self, *_): pass


if __name__ == "__main__":
  args = build_config()
  try:
    asyncio.run(main_loop(args))
  except KeyboardInterrupt:
    pass