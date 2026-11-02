"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.param_sync import open_descriptions, set_description, sync_option, sync_toggle
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.sunnypilot.widgets.list_view import option_item_sp, toggle_item_sp
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.widgets import Widget

ACC_ENABLED_DESCRIPTION = tr_noop("Enable custom Short & Long press increments for cruise speed increase/decrease.")
ACC_NOLONG_DESCRIPTION = tr_noop("This feature can only be used with sunnypilot longitudinal control enabled.")
ACC_PCMCRUISE_DISABLED_DESCRIPTION = tr_noop("This feature is not supported on this platform due to vehicle limitations.")
ONROAD_ONLY_DESCRIPTION = tr_noop("Start the vehicle to check vehicle compatibility.")


class CruiseLayout(Widget):
  def __init__(self):
    super().__init__()
    self._long_press_stored: int | None = None
    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=True, spacing=0)
    self._descriptions_to_open: list = []

  def _initialize_items(self):
    self.custom_acc_toggle = toggle_item_sp(
      title=lambda: tr("Custom ACC Speed Increments"),
      description="",
      param="CustomAccIncrementsEnabled",
    )
    self.custom_acc_short_increment = option_item_sp(
      title=lambda: tr("Short Press Increment"),
      param="CustomAccShortPressIncrement",
      min_value=1, max_value=10, value_change_step=1,
      label_callback=self._increment_label,
    )
    self.custom_acc_long_increment = option_item_sp(
      title=lambda: tr("Long Press Increment"),
      param="CustomAccLongPressIncrement",
      value_map={1: 1, 2: 5, 3: 10},
      min_value=1, max_value=3, value_change_step=1,
      label_callback=self._long_press_label,
      on_value_changed=self._on_long_press_changed,
    )

    items = [
      self.custom_acc_toggle,
      self.custom_acc_short_increment,
      self.custom_acc_long_increment,
    ]
    return items

  @staticmethod
  def _increment_label(value: int) -> str:
    # The driving code applies the increment in the display unit (selfdrive/car/cruise.py).
    return f'{value} {"km/h" if ui_state.is_metric else "mph"}'

  def _long_press_label(self, value: int) -> str:
    # sunnylink offers any 1 to 10 here, and the car uses it as stored (clipped to 1..10), so a value that is
    # not one of the 1/5/10 choices is shown as is until -/+ is pressed.
    if self._long_press_stored is not None:
      value = min(max(self._long_press_stored, 1), 10)
    return self._increment_label(value)

  def _on_long_press_changed(self, _value: int) -> None:
    self._long_press_stored = None

  @staticmethod
  def _status() -> str | None:
    """Why the increments can't be used on this car, or None when they can.

    The car applies them when sunnypilot sets the speed (selfdrive/car/cruise.py: not pcmCruise, or
    not CP_SP.pcmCruiseSpeed), and card keeps the setting only with sunnypilot longitudinal or ICBM
    (sunnypilot/selfdrive/car/interfaces.py, _cleanup_unsupported_params). Both hold for sunnypilot
    longitudinal without pcmCruise, and for ICBM, the only thing that clears pcmCruiseSpeed. ICBM is
    recognised from all three of its conditions because CarParamsSP saved by 0.10.1 has no
    pcmCruiseSpeed field, and it reads False there.
    """
    CP = ui_state.CP
    if CP is None:
      return tr(ONROAD_ONLY_DESCRIPTION)
    # CarParams is from the last car start, while the alpha longitudinal toggle applies at the next one.
    if CP.alphaLongitudinalAvailable and ui_state.has_longitudinal_control != CP.openpilotLongitudinalControl:
      return tr(ONROAD_ONLY_DESCRIPTION)
    CP_SP = getattr(ui_state, "CP_SP", None)
    icbm = (CP_SP is not None and CP_SP.intelligentCruiseButtonManagementAvailable and
            not CP.openpilotLongitudinalControl and not CP_SP.pcmCruiseSpeed)
    if (CP.openpilotLongitudinalControl and not CP.pcmCruise) or icbm:
      return None
    return tr(ACC_PCMCRUISE_DISABLED_DESCRIPTION) if CP.openpilotLongitudinalControl else tr(ACC_NOLONG_DESCRIPTION)

  def _update_state(self):
    super()._update_state()
    status = self._status()
    base = tr(ACC_ENABLED_DESCRIPTION)
    set_description(self.custom_acc_toggle, base if status is None else f"<b>{status}</b><br><br>{base}")

    # The driving code re-reads these every 0.1 s, but they are only editable offroad. The setting is never
    # cleared here: card already removes it at car start when the car can't use it (sunnypilot/selfdrive/car/interfaces.py).
    enabled = ui_state.is_offroad() and status is None
    self.custom_acc_toggle.action_item.set_enabled(enabled)
    shown = self.custom_acc_toggle.action_item.get_state()
    for item in (self.custom_acc_short_increment, self.custom_acc_long_increment):
      item.set_visible(shown)
      item.action_item.set_enabled(enabled)

  def _render(self, rect):
    self._scroller.render(rect)
    open_descriptions(self._descriptions_to_open)

  def show_event(self):
    sync_toggle(self.custom_acc_toggle, ui_state.params)
    sync_option(self.custom_acc_short_increment, ui_state.params)
    stored = sync_option(self.custom_acc_long_increment, ui_state.params)
    self._long_press_stored = None if stored in self.custom_acc_long_increment.action_item.value_map.values() else stored
    self._scroller.show_event()
    self._update_state()
    self._descriptions_to_open = [self.custom_acc_toggle] if self._status() is not None else []
