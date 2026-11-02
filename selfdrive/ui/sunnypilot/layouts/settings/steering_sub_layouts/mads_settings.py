"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections.abc import Callable
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.param_sync import open_descriptions, set_description, sync_buttons, sync_toggle
from openpilot.sunnypilot.mads.helpers import MADS_NO_ACC_MAIN_BUTTON, MadsSteeringModeOnBrake, get_mads_limited_brands
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.network import NavButton
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.sunnypilot.widgets.list_view import multiple_button_item_sp, toggle_item_sp

MADS_STEERING_MODE_OPTIONS = [
  (tr_noop("Remain Active"), tr_noop("Remain Active: ALC will remain active when the brake pedal is pressed.")),
  (tr_noop("Pause"), tr_noop("Pause: ALC will pause when the brake pedal is pressed.")),
  (tr_noop("Disengage"), tr_noop("Disengage: ALC will disengage when the brake pedal is pressed.")),
]

MADS_MAIN_CRUISE_BASE_DESC = tr_noop("Note: For vehicles without LFA/LKAS button, disabling this will prevent lateral control engagement.")
MADS_UEM_ENGAGE_DESC = tr_noop("Engage lateral and longitudinal control with cruise control engagement.")
MADS_UEM_NOTE_DESC = tr_noop("Note: Once lateral control is engaged via UEM, it will remain engaged until it is manually disabled " +
                             "via the MADS button or car shut off.")
MADS_STEERING_MODE_BASE_DESC = tr_noop("Choose how Automatic Lane Centering (ALC) behaves after the brake pedal is manually pressed in sunnypilot.")

STATUS_CHECK_COMPATIBILITY = tr_noop("Start the vehicle to check vehicle compatibility.")
DEFAULT_TO_OFF = tr_noop("This feature defaults to OFF, and does not allow selection due to vehicle limitations.")
DEFAULT_TO_ON = tr_noop("This feature defaults to ON, and does not allow selection due to vehicle limitations.")
STATUS_DISENGAGE_ONLY = tr_noop("This platform only supports Disengage mode due to vehicle limitations.")


def mads_limited() -> bool:
  """Whether this car gets the reduced MADS options, as the driving code decides at car start
  (sunnypilot/mads/helpers.py): rivian always, tesla unless it has a vehicle bus. A tesla whose
  CarParamsSP has not been written yet is treated as limited, since the flag cannot be seen."""
  CP = ui_state.CP
  if CP is None:
    return False
  CP_SP = getattr(ui_state, "CP_SP", None)
  if CP.brand == "tesla" and CP_SP is None:
    return True
  return get_mads_limited_brands(CP, CP_SP)


class MadsSettingsLayout(Widget):
  def __init__(self, back_btn_callback: Callable):
    super().__init__()
    self._back_button = NavButton(tr("Back"))
    self._back_button.set_click_callback(back_btn_callback)
    self._initialize_items()
    self._scroller = Scroller(self.items, line_separator=True, spacing=0)
    self._descriptions_to_open: list = []

  def _initialize_items(self):
    self._main_cruise_toggle = toggle_item_sp(
      title=lambda: tr("Toggle with Main Cruise"),
      description="",
      param="MadsMainCruiseAllowed",
    )
    self._unified_engagement_toggle = toggle_item_sp(
      title=lambda: tr("Unified Engagement Mode (UEM)"),
      description="",
      param="MadsUnifiedEngagementMode",
    )
    self._steering_mode = multiple_button_item_sp(
      param="MadsSteeringMode",
      title=lambda: tr("Steering Mode on Brake Pedal"),
      description="",
      buttons=[(lambda label=label: tr(label)) for label, _ in MADS_STEERING_MODE_OPTIONS],
      inline=False,
      button_width=350,
    )

    self.items = [
      self._main_cruise_toggle,
      self._unified_engagement_toggle,
      self._steering_mode,
    ]

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
    open_descriptions(self._descriptions_to_open)

  def show_event(self):
    sync_toggle(self._main_cruise_toggle, ui_state.params)
    sync_toggle(self._unified_engagement_toggle, ui_state.params)
    # The car treats any value but Pause or Disengage as Remain Active (sunnypilot/mads/helpers.py).
    sync_buttons(self._steering_mode, ui_state.params, fallback=MadsSteeringModeOnBrake.REMAIN_ACTIVE)
    self._update_toggles()
    self._scroller.show_event()

    # As 0.10.1 did: the steering mode choices, and why a row is locked or not yet checked.
    CP = ui_state.CP
    self._descriptions_to_open = [self._steering_mode]
    if CP is None or CP.brand in MADS_NO_ACC_MAIN_BUTTON:
      self._descriptions_to_open.append(self._main_cruise_toggle)
    if CP is None or mads_limited():
      self._descriptions_to_open.append(self._unified_engagement_toggle)

  @staticmethod
  def _steering_mode_description(selected: int) -> str:
    result = tr(MADS_STEERING_MODE_BASE_DESC) + "<br><br>"
    for index, (_, desc) in enumerate(MADS_STEERING_MODE_OPTIONS):
      result += (f"<b>{tr(desc)}</b>" if index == selected else tr(desc)) + "<br>"
    return result

  def _update_toggles(self):
    # Display only. The driving code is what enforces these per brand at every car start
    # (sunnypilot/mads/helpers.py), so nothing here writes a param.
    CP = ui_state.CP
    limited = mads_limited()
    no_main_button = CP is not None and CP.brand in MADS_NO_ACC_MAIN_BUTTON
    check = "" if CP is not None else f"<b>{tr(STATUS_CHECK_COMPATIBILITY)}</b><br>"

    main_cruise_desc = tr(MADS_MAIN_CRUISE_BASE_DESC)
    if no_main_button:
      self._main_cruise_toggle.action_item.set_state(False)
      set_description(self._main_cruise_toggle, f"<b>{tr(DEFAULT_TO_OFF)}</b><br>{main_cruise_desc}")
    else:
      set_description(self._main_cruise_toggle, check + main_cruise_desc)
    self._main_cruise_toggle.action_item.set_enabled(not no_main_button)

    uem_desc = f"{tr(MADS_UEM_ENGAGE_DESC)}<br><h4>{tr(MADS_UEM_NOTE_DESC)}</h4>"
    if limited:
      self._unified_engagement_toggle.action_item.set_state(True)
      set_description(self._unified_engagement_toggle, f"<b>{tr(DEFAULT_TO_ON)}</b><br>{uem_desc}")
    else:
      set_description(self._unified_engagement_toggle, check + uem_desc)
    self._unified_engagement_toggle.action_item.set_enabled(not limited)

    if limited:
      self._steering_mode.action_item.set_selected_button(MadsSteeringModeOnBrake.DISENGAGE)
      set_description(self._steering_mode, f"<b>{tr(STATUS_DISENGAGE_ONLY)}</b>")
    else:
      set_description(self._steering_mode, check + self._steering_mode_description(self._steering_mode.action_item.get_selected_button()))
    # Read once at car start (sunnypilot/mads/helpers.py, mads.py), so a change only means something offroad.
    self._steering_mode.action_item.set_enabled(ui_state.is_offroad() and not limited)
