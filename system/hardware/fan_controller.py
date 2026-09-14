#!/usr/bin/env python3
import json
import os
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, fields

from openpilot.common.realtime import DT_HW
from openpilot.common.swaglog import cloudlog
from openpilot.common.pid import PIDController

# Tuning for a non-stock fan lives in a plain JSON file instead of the source, so it can be
# changed on a prebuilt install without a rebuild. A missing or empty file gives stock behaviour.
FAN_CONFIG_PATH = os.getenv("FAN_CONFIG_PATH", "/data/fan_config.json")


@dataclass
class FanConfig:
  # temperature control
  setpoint_c: float = 75.0          # temperature the controller holds
  ff_lo_c: float = 60.0             # feedforward starts ramping here
  ff_hi_c: float = 100.0            # feedforward reaches full output here

  # output shaping, applied to the controller's 0-100 demand before it goes to the panda
  min_percent: int = 0              # floor whenever the fan is asked to run at all
  max_percent: int = 100            # ceiling, see note below
  force_percent: int | None = None  # bypass the controller entirely, for bring-up only

  # below this the fan counts as stalled, 0 disables the fanMalfunction alert
  min_rpm: int = 500

  # max_percent is the knob that matters for an aftermarket fan. The panda firmware shipped with
  # this build treats set_fan_power() as a target RPM request (target = 6600 * percent / 100 on a
  # tres) and closes the loop on the tachometer. A typical PC fan tops out far below 6600 RPM, so
  # every demand above 100 * fan_max_rpm / 6600 is unreachable, the firmware's integrator saturates
  # and the fan just runs flat out. Setting max_percent to that ratio restores proportional control.
  # On the newer pure-PWM firmware set_fan_power() is the duty cycle directly and max_percent simply
  # caps it. See docs/fan-mod-tici.md.

  @staticmethod
  def load(path: str = FAN_CONFIG_PATH) -> "FanConfig":
    config = FanConfig()

    try:
      with open(path) as f:
        raw = json.load(f)
    except FileNotFoundError:
      return config
    except Exception:
      cloudlog.exception(f"fan: could not read {path}, falling back to stock tuning")
      return config

    known = {f.name for f in fields(config)}
    for key, value in raw.items():
      if key in known:
        setattr(config, key, value)
      else:
        cloudlog.warning(f"fan: ignoring unknown config key {key!r}")

    config.validate()
    return config

  def validate(self) -> None:
    self.min_percent = int(np.clip(self.min_percent, 0, 100))
    self.max_percent = int(np.clip(self.max_percent, 0, 100))
    if self.max_percent < self.min_percent:
      cloudlog.warning(f"fan: max_percent {self.max_percent} below min_percent {self.min_percent}, raising it")
      self.max_percent = self.min_percent

    if self.force_percent is not None:
      self.force_percent = int(np.clip(self.force_percent, 0, 100))

    self.min_rpm = max(0, int(self.min_rpm))

    if self.ff_hi_c <= self.ff_lo_c:
      cloudlog.warning(f"fan: ff_hi_c {self.ff_hi_c} not above ff_lo_c {self.ff_lo_c}, using stock ramp")
      self.ff_lo_c, self.ff_hi_c = 60.0, 100.0


class BaseFanController(ABC):
  @abstractmethod
  def update(self, cur_temp: float, ignition: bool) -> int:
    pass


class TiciFanController(BaseFanController):
  def __init__(self, config: FanConfig | None = None) -> None:
    super().__init__()
    self.config = FanConfig.load() if config is None else config
    cloudlog.info(f"Setting up TICI fan handler: {self.config}")

    self.last_ignition = False
    self.controller = PIDController(k_p=0, k_i=4e-3, k_f=1, rate=(1 / DT_HW))

  def update(self, cur_temp: float, ignition: bool) -> int:
    self.controller.pos_limit = 100 if ignition else 30
    self.controller.neg_limit = 30 if ignition else 0

    if ignition != self.last_ignition:
      self.controller.reset()

    error = cur_temp - self.config.setpoint_c
    demand = int(self.controller.update(
                   error=error,
                   feedforward=np.interp(cur_temp, [self.config.ff_lo_c, self.config.ff_hi_c], [0, 100])
                 ))

    self.last_ignition = ignition
    return self.shape(demand)

  def shape(self, demand: int) -> int:
    """Map the controller's 0-100 demand onto what this device's fan can actually deliver."""
    if self.config.force_percent is not None:
      return self.config.force_percent

    if demand <= 0:
      return 0

    span = self.config.max_percent - self.config.min_percent
    out = round(self.config.min_percent + (demand * span / 100))
    return int(np.clip(out, self.config.min_percent, self.config.max_percent))
