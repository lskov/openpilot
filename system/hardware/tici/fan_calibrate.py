#!/usr/bin/env python3
"""
Sweep the fan and work out what it can actually do, then suggest a /data/fan_config.json for it.

Meant for a device whose stock fan has been replaced. Stop openpilot first, it holds the panda:

  sudo systemctl stop comma
  ./system/hardware/tici/fan_calibrate.py --write
  sudo systemctl restart comma
"""
import argparse
import json
import statistics
import time

from panda import Panda

from openpilot.system.hardware.fan_controller import FAN_CONFIG_PATH, FanConfig

# what the panda's closed-loop firmware believes the fan tops out at
STOCK_MAX_RPM = {
  Panda.HW_TYPE_DOS: 6500,
  Panda.HW_TYPE_TRES: 6600,
  Panda.HW_TYPE_CUATRO: 12500,
}

SPIN_UP_RPM = 100  # above this the fan counts as actually turning


def sample(panda: Panda, dwell: float) -> tuple[int, int]:
  """Let the fan settle, then average RPM and PWM duty over the back half of the dwell."""
  time.sleep(dwell / 2)

  rpms, powers = [], []
  end = time.monotonic() + (dwell / 2)
  while time.monotonic() < end:
    rpms.append(panda.get_fan_rpm())
    powers.append(panda.health()['fan_power'])
    time.sleep(0.2)

  return round(statistics.mean(rpms)), round(statistics.mean(powers))


def detect_pure_pwm(panda: Panda, dwell: float) -> bool:
  """Pure-PWM firmware drives the duty straight from the command, the older firmware closes a loop
     on the tachometer and its duty will not track the command."""
  panda.set_fan_power(50)
  _, power = sample(panda, dwell)
  panda.set_fan_power(0)
  return abs(power - 50) <= 2


def sweep(panda: Panda, step: int, dwell: float) -> list[tuple[int, int, int]]:
  results = []
  for command in range(0, 101, step):
    panda.set_fan_power(command)
    rpm, power = sample(panda, dwell)
    results.append((command, rpm, power))
    print(f"  command {command:3d}%   ->   {rpm:5d} rpm   at {power:3d}% duty")
  return results


def recommend(results: list[tuple[int, int, int]], pure_pwm: bool, hw_type: bytes) -> FanConfig:
  config = FanConfig()

  spinning = [(c, r) for c, r, _ in results if c > 0 and r > SPIN_UP_RPM]
  if not spinning:
    # either the fan never turns, or its tachometer is not wired up
    config.min_rpm = 0
    return config

  max_rpm = max(r for _, r in spinning)

  config.min_percent = min(c for c, _ in spinning)
  config.min_rpm = max(0, round(min(r for _, r in spinning) / 2))

  if pure_pwm:
    # the command is the duty cycle, so the full range is usable
    config.max_percent = 100
  else:
    # the command is a target RPM of STOCK_MAX_RPM * command / 100. Anything above what the fan can
    # reach is unreachable, the firmware's integrator saturates and the fan just runs flat out.
    stock_max = STOCK_MAX_RPM.get(hw_type, 6600)
    config.max_percent = int(min(100, max(config.min_percent, round(100 * max_rpm / stock_max))))

  return config


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--step", type=int, default=10, help="command increment in percent (default: 10)")
  parser.add_argument("--dwell", type=float, default=8.0, help="seconds to hold each step (default: 8)")
  parser.add_argument("--path", default=FAN_CONFIG_PATH, help=f"where to write the config (default: {FAN_CONFIG_PATH})")
  parser.add_argument("--write", action="store_true", help="write the suggested config instead of only printing it")
  args = parser.parse_args()

  with Panda(cli=False) as panda:
    if not panda.is_internal():
      raise SystemExit("this is not an internal panda, there is no fan on it")

    hw_type = bytes(panda.get_type())
    panda.set_heartbeat_disabled()

    try:
      print("detecting panda fan firmware...")
      pure_pwm = detect_pure_pwm(panda, args.dwell)
      print(f"  {'pure PWM, the command is the duty cycle' if pure_pwm else 'closed loop, the command is a target RPM'}\n")

      print("sweeping the fan, this takes a couple of minutes...")
      results = sweep(panda, args.step, args.dwell)
    finally:
      panda.set_fan_power(0)

  max_rpm = max((r for c, r, _ in results if c > 0), default=0)
  print()
  if max_rpm <= SPIN_UP_RPM:
    print("the tachometer never read above idle. Either the fan is not turning at all, or it has no")
    print("tachometer wired to the panda. min_rpm is set to 0 so the fan malfunction alert stays quiet.")
  else:
    print(f"the fan tops out around {max_rpm} rpm")
    if not pure_pwm:
      stock_max = STOCK_MAX_RPM.get(hw_type, 6600)
      print(f"the firmware scales the command against {stock_max} rpm, so only part of the range is usable")

  config = recommend(results, pure_pwm, hw_type)
  payload = json.dumps(config.__dict__, indent=2)
  print(f"\nsuggested {args.path}:\n{payload}")

  if args.write:
    with open(args.path, "w") as f:
      f.write(payload + "\n")
    print("\nwritten. Reboot or restart openpilot to pick it up.")
  else:
    print("\nre-run with --write to save it.")


if __name__ == "__main__":
  main()
