#!/usr/bin/env python3
"""
Watch the thermal loop live: how hot the device is, how hard the controller is asking the fan to
work, and what the fan is actually doing about it.

Run it with openpilot running, unlike fan_calibrate.py which needs the panda free:

  ./system/hardware/tici/fan_watch.py

Leave it going for a drive. If maxTempC keeps climbing while desired is pinned at 100% and the fan
is at full rpm, the fan is not the bottleneck and the airflow path is worth looking at.
"""
import argparse
import time

from cereal.messaging import SubMaster

from openpilot.system.hardware.fan_controller import FanConfig

# the scale the closed-loop panda firmware maps a command percentage onto
STOCK_MAX_RPM = 6600


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--interval", type=float, default=1.0, help="seconds between lines (default: 1)")
  args = parser.parse_args()

  config = FanConfig.load()
  forced = "" if config.force_percent is None else f", FORCED to {config.force_percent}%"
  print(f"setpoint {config.setpoint_c:.0f}C, command range {config.min_percent}-{config.max_percent}%{forced}\n")
  print(f"{'temp':>7} {'peak':>7} {'status':>10} {'desired':>8} {'rpm':>7} {'target':>7} {'ratio':>6}")

  sm = SubMaster(['deviceState', 'peripheralState'])
  peak = 0.0
  next_line = time.monotonic()

  while True:
    sm.update()
    if not sm.updated['deviceState']:
      continue

    device, peripheral = sm['deviceState'], sm['peripheralState']
    peak = max(peak, device.maxTempC)

    if time.monotonic() < next_line:
      continue
    next_line = time.monotonic() + args.interval

    desired = device.fanSpeedPercentDesired
    rpm = peripheral.fanSpeedRpm
    target = round(STOCK_MAX_RPM * desired / 100)

    # how much of what was asked for the fan is delivering, only meaningful once it is asked to spin
    ratio = f"{rpm / target:5.0%}" if target > 0 else "    -"

    print(f"{device.maxTempC:6.1f}C {peak:6.1f}C {device.thermalStatus:>10} {desired:7d}% {rpm:7d} {target:7d} {ratio:>6}")


if __name__ == "__main__":
  main()
