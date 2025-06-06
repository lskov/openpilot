#!/usr/bin/env python3
from abc import ABC, abstractmethod

from openpilot.common.realtime import DT_HW
from openpilot.common.numpy_fast import interp
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.controls.lib.pid import PIDController

class BaseFanController(ABC):
  @abstractmethod
  def update(self, cur_temp: float, ignition: bool) -> int:
    pass


class TiciFanController(BaseFanController):
  def __init__(self) -> None:
    super().__init__()
    cloudlog.info("Setting up TICI fan handler")

    self.last_ignition = False
    self.controller = PIDController(k_p=0.1, k_i=1e-3, k_f=0.5, rate=(1 / DT_HW)) 
                    # PIDController(k_p=0,   k_i=4e-3, k_f=1,   rate=(1 / DT_HW))

  def update(self, cur_temp: float, ignition: bool) -> int:
    self.controller.neg_limit = -(100 if ignition else 30)
    self.controller.pos_limit = -(30 if ignition else 0)

    if ignition != self.last_ignition:
      self.controller.reset()

    error = 70 - cur_temp
    fan_raw = -int(self.controller.update(
                      error=error,
                      feedforward=interp(cur_temp, [60.0, 100.0], [0, 100])
                    ))
    fan_pwr_out = max(0, fan_raw)  # Clip negatives

    MAX_FAN_POWER = 75
    fan_pwr_out = fan_pwr_out if fan_pwr_out <= MAX_FAN_POWER else MAX_FAN_POWER

    cloudlog.info(f"Fan out: {fan_pwr_out} | Temp: {cur_temp} | Error: {error}")

    self.last_ignition = ignition
    return fan_pwr_out

