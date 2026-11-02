"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections.abc import Callable
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.param_sync import sync_option, sync_toggle
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.sunnypilot.widgets.list_view import toggle_item_sp, option_item_sp
from openpilot.system.ui.widgets.network import NavButton
from openpilot.system.ui.widgets.scroller_tici import LineSeparator, Scroller
from openpilot.system.ui.widgets import Widget

from openpilot.sunnypilot.selfdrive.controls.lib.auto_lane_change import AutoLaneChangeMode


class LaneChangeSettingsLayout(Widget):
  def __init__(self, back_btn_callback: Callable):
    super().__init__()
    self._back_button = NavButton(tr("Back"))
    self._back_button.set_click_callback(back_btn_callback)

    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=False, spacing=0)

  def _initialize_items(self):
    self._lane_change_timer = option_item_sp(
      title=lambda: tr("Auto Lane Change by Blinker"),
      param="AutoLaneChangeTimer",
      description=lambda: tr("Set a timer to delay the auto lane change operation when the blinker is used. " +
                             "No nudge on the steering wheel is required to auto lane change if a timer is set. Default is Nudge.<br>" +
                             "Please use caution when using this feature. Only use the blinker when traffic and road conditions permit."),
      min_value=AutoLaneChangeMode.OFF,
      max_value=AutoLaneChangeMode.THREE_SECONDS,
      value_change_step=1,
      label_callback=self._timer_label,
    )
    self._bsm_delay = toggle_item_sp(
      param="AutoLaneChangeBsmDelay",
      title=lambda: tr("Auto Lane Change: Delay with Blind Spot"),
      description=lambda: tr("Toggle to enable a delay timer for seamless lane changes when blind spot monitoring " +
                             "(BSM) detects a obstructing vehicle, ensuring safe maneuvering."),
    )

    items = [
      self._lane_change_timer,
      LineSeparator(40),
      self._bsm_delay,
    ]

    return items

  @staticmethod
  def _timer_label(value: int) -> str:
    labels = {
      AutoLaneChangeMode.OFF: lambda: tr("Off"),
      AutoLaneChangeMode.NUDGE: lambda: tr("Nudge"),
      AutoLaneChangeMode.NUDGELESS: lambda: tr("Nudgeless"),
      AutoLaneChangeMode.HALF_SECOND: lambda: f"0.5 {tr('s')}",
      AutoLaneChangeMode.ONE_SECOND: lambda: f"1 {tr('s')}",
      AutoLaneChangeMode.TWO_SECONDS: lambda: f"2 {tr('s')}",
      AutoLaneChangeMode.THREE_SECONDS: lambda: f"3 {tr('s')}",
    }
    label = labels.get(value)
    return label() if label else str(value)

  def _update_state(self):
    super()._update_state()
    self._update_toggles()

  def _render(self, rect):
    self._back_button.text = tr("Back")
    self._back_button.set_position(self._rect.x, self._rect.y + 20)
    self._back_button.render()
    # subtract button
    content_rect = rl.Rectangle(rect.x, rect.y + self._back_button.rect.height + 40, rect.width, rect.height - self._back_button.rect.height - 40)
    self._scroller.render(content_rect)

  def show_event(self):
    sync_option(self._lane_change_timer, ui_state.params)
    sync_toggle(self._bsm_delay, ui_state.params)
    self._update_toggles()
    self._scroller.show_event()

  def _update_toggles(self):
    # The delay only applies to timed lane changes, and only acts when the car reports a blind spot
    # (sunnypilot/selfdrive/controls/lib/auto_lane_change.py), so on a car without BSM it is inert
    # rather than wrong. It is greyed out there instead of being removed.
    enable_bsm = ui_state.CP is not None and ui_state.CP.enableBsm
    timed = self._lane_change_timer.action_item.get_value() > AutoLaneChangeMode.NUDGE
    self._bsm_delay.action_item.set_enabled(enable_bsm and timed)
