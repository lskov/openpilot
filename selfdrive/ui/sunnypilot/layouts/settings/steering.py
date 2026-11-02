"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from enum import IntEnum

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.param_sync import set_description, sync_option, sync_toggle
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.steering_sub_layouts.lane_change_settings import LaneChangeSettingsLayout
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.steering_sub_layouts.mads_settings import MadsSettingsLayout, mads_limited
from openpilot.sunnypilot.mads.helpers import MADS_NO_ACC_MAIN_BUTTON
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.sunnypilot.widgets.list_view import ListItemSP, simple_button_item_sp, toggle_item_sp
from openpilot.system.ui.sunnypilot.widgets.option_control import BUTTON_HEIGHT as OPTION_BUTTON_HEIGHT, OptionControlSP
from openpilot.system.ui.widgets.scroller_tici import LineSeparator, Scroller
from openpilot.system.ui.widgets import Widget

MADS_BASE_DESC = tr_noop("Enable the beloved MADS feature. Disable toggle to revert back to stock sunnypilot engagement/disengagement.")
MADS_LIMITED_DESC = tr_noop("This platform supports limited MADS settings.")
MADS_FULL_DESC = tr_noop("This platform supports all MADS settings.")
MADS_CHECK_COMPAT_DESC = tr_noop("Start the vehicle to check vehicle compatibility.")

NNLC_EXPLANATION = tr_noop('Formerly known as "NNFF", this replaces the lateral "torque" controller with one using a neural network ' +
                           "trained on each car's (actually, each separate EPS firmware) driving data for increased controls accuracy.")
NNLC_SUPPORT_REACH_OUT = tr_noop("Reach out to the sunnypilot team in the following channel at the sunnypilot Discord server")
NNLC_SUPPORT_FEEDBACK = tr_noop("with feedback, or to provide log data for your car if your car is currently unsupported:")
NNLC_SUPPORT_DONATE_LOGS = tr_noop("and donate logs to get NNLC loaded for your car:")
NNLC_SUPPORT_ISSUES = tr_noop("if there are any issues:")
NNLC_SUPPORT_CHANNEL = "#tuning-nnlc"
NNLC_STATUS_CHECK_COMPAT = tr_noop("Start the car to check car compatibility")
NNLC_STATUS_NOT_AVAILABLE = tr_noop("NNLC is currently not available on this platform.")
NNLC_STATUS_NOT_LOADED = tr_noop("NNLC Not Loaded")
NNLC_STATUS_LOADED = tr_noop("NNLC Loaded")
NNLC_EXPLANATION_MATCH = tr_noop('Match: "Exact" is ideal, but "Fuzzy" is fine too.')


class PanelType(IntEnum):
  STEERING = 0
  MADS = 1
  LANE_CHANGE = 2


class StepperBelowTitleSP(ListItemSP):
  """A row with its -/+ control below the title. ListItemSP gives a control there a 120 px rect, but
  OptionControlSP draws 150 px buttons centred on that rect and takes taps only inside the rect, so the
  top and bottom 15 px of each button would light up and not respond. Grow the rect to match."""
  def __init__(self, title, action_item: OptionControlSP):
    super().__init__(title=title, action_item=action_item, inline=False)

  def get_right_item_rect(self, item_rect: rl.Rectangle) -> rl.Rectangle:
    rect = super().get_right_item_rect(item_rect)
    grow = OPTION_BUTTON_HEIGHT - rect.height
    return rl.Rectangle(rect.x, rect.y - grow / 2, rect.width, rect.height + grow)


class SteeringLayout(Widget):
  def __init__(self):
    super().__init__()

    self._current_panel = PanelType.STEERING
    self._lane_change_settings_layout = LaneChangeSettingsLayout(lambda: self._set_current_panel(PanelType.STEERING))
    self._mads_settings_layout = MadsSettingsLayout(lambda: self._set_current_panel(PanelType.STEERING))

    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=False, spacing=0)

  def _initialize_items(self):
    self._mads_toggle = toggle_item_sp(
      param="Mads",
      title=lambda: tr("Modular Assistive Driving System (MADS)"),
      description="",
    )
    self._mads_settings_button = simple_button_item_sp(
      button_text=lambda: tr("Customize MADS"),
      button_width=800,
      callback=lambda: self._set_current_panel(PanelType.MADS)
    )
    self._lane_change_settings_button = simple_button_item_sp(
      button_text=lambda: tr("Customize Lane Change"),
      button_width=800,
      callback=lambda: self._set_current_panel(PanelType.LANE_CHANGE)
    )
    self._blinker_control_toggle = toggle_item_sp(
      param="BlinkerPauseLateralControl",
      description=lambda: tr("Pause lateral control with blinker when traveling below the desired speed selected."),
      title=lambda: tr("Pause Lateral Control with Blinker"),
    )
    # The title is too wide to share a row with the -/+ control, so the control goes below it.
    self._blinker_control_options = StepperBelowTitleSP(
      title=lambda: tr("Minimum Speed to Pause Lateral Control"),
      action_item=OptionControlSP(
        "BlinkerMinLateralControlSpeed", 0, 255, 5,
        label_callback=lambda speed: f'{speed} {"km/h" if ui_state.is_metric else "mph"}',
      ),
    )
    self._nnlc_toggle = toggle_item_sp(
      param="NeuralNetworkLateralControl",
      title=lambda: tr("Neural Network Lateral Control (NNLC)"),
      description="",
    )

    items = [
      self._mads_toggle,
      self._mads_settings_button,
      LineSeparator(40),
      self._lane_change_settings_button,
      LineSeparator(40),
      self._blinker_control_toggle,
      self._blinker_control_options,
      LineSeparator(40),
      self._nnlc_toggle,
    ]
    return items

  def _set_current_panel(self, panel: PanelType):
    if panel == self._current_panel:
      return
    self._current_panel = panel
    if panel == PanelType.MADS:
      self._mads_settings_layout.show_event()
    elif panel == PanelType.LANE_CHANGE:
      self._lane_change_settings_layout.show_event()
    else:
      self._sync_items()
      self._scroller.show_event()

  def _sync_items(self):
    for item in (self._mads_toggle, self._blinker_control_toggle, self._nnlc_toggle):
      sync_toggle(item, ui_state.params)
    sync_option(self._blinker_control_options, ui_state.params)

  @staticmethod
  def _nnlc_description(angle_steering: bool) -> str:
    CP_SP = getattr(ui_state, "CP_SP", None)
    model = CP_SP.neuralNetworkLateralControl.model.name if CP_SP is not None else ""
    support = tr(NNLC_SUPPORT_REACH_OUT)
    base = f"{tr(NNLC_EXPLANATION)}<br><br>{support} {tr(NNLC_SUPPORT_FEEDBACK)} {NNLC_SUPPORT_CHANNEL}"

    if angle_steering:
      status = f"<b>{tr(NNLC_STATUS_NOT_AVAILABLE)}</b>"
    elif ui_state.CP is None or not model:
      status = f"<b>{tr(NNLC_STATUS_CHECK_COMPAT)}</b>"
    elif model == "MOCK":
      status = f"<b>{tr(NNLC_STATUS_NOT_LOADED)}</b><br>{support} {tr(NNLC_SUPPORT_DONATE_LOGS)} {NNLC_SUPPORT_CHANNEL}"
    else:
      match = tr("Fuzzy") if CP_SP.neuralNetworkLateralControl.fuzzyFingerprint else tr("Exact")
      status = (f"<b>{tr(NNLC_STATUS_LOADED)} | {tr('Match')} = {match} | {model}</b><br>" +
                f"{tr(NNLC_EXPLANATION_MATCH)} {support} {tr(NNLC_SUPPORT_ISSUES)} {NNLC_SUPPORT_CHANNEL}")
    return f"{status}<br><br>{base}"

  def _update_state(self):
    super()._update_state()

    offroad = ui_state.is_offroad()
    CP = ui_state.CP

    if CP is None:
      mads_status = tr(MADS_CHECK_COMPAT_DESC)
    else:
      # A car without a main cruise button has that MADS setting locked off (sunnypilot/mads/helpers.py).
      limited = mads_limited() or CP.brand in MADS_NO_ACC_MAIN_BUTTON
      mads_status = tr(MADS_LIMITED_DESC) if limited else tr(MADS_FULL_DESC)
    set_description(self._mads_toggle, f"<b>{mads_status}</b><br><br>{tr(MADS_BASE_DESC)}")

    # Mads is read once at car start (card.py, sunnypilot/mads/mads.py), so it only changes offroad. The
    # MADS page stays open to it onroad, as in 0.10.1: Main Cruise and UEM are read live, and the page
    # locks the brake setting onroad itself.
    self._mads_toggle.action_item.set_enabled(offroad)
    self._mads_settings_button.action_item.set_enabled(self._mads_toggle.action_item.get_state())
    self._blinker_control_options.set_visible(self._blinker_control_toggle.action_item.get_state())

    # NNLC is read once at car start, and only for torque-steered cars; card removes the key on angle-steered
    # ones (sunnypilot/selfdrive/car/interfaces.py), which is why the toggle is shown off for them. Before the
    # first drive the steering type is unknown, and a choice made then is applied or removed by that rule.
    angle_steering = CP is not None and str(CP.steerControlType) == "angle"
    if angle_steering:
      self._nnlc_toggle.action_item.set_state(False)
    self._nnlc_toggle.action_item.set_enabled(offroad and not angle_steering)
    set_description(self._nnlc_toggle, self._nnlc_description(angle_steering))

  def _render(self, rect):
    if self._current_panel == PanelType.LANE_CHANGE:
      self._lane_change_settings_layout.render(rect)
    elif self._current_panel == PanelType.MADS:
      self._mads_settings_layout.render(rect)
    else:
      self._scroller.render(rect)

  def show_event(self):
    self._current_panel = PanelType.STEERING
    self._sync_items()
    self._scroller.show_event()
