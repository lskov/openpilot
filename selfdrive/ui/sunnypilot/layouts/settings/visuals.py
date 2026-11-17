"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.param_sync import sync_buttons, sync_toggle
from openpilot.selfdrive.ui.sunnypilot.onroad.developer_ui import DeveloperUiRenderer
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.sunnypilot.widgets.list_view import multiple_button_item_sp, toggle_item_sp
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.widgets import Widget

# Only the settings this build acts on are shown. Sunnypilot's full Visuals page also has blind spot, rainbow path,
# chevron metrics, speedometer, turn signal, standstill timer and road name settings, but nothing in this build acts on
# those keys (sunnylink only backs them up, and reports RainbowMode in its stats).
# GreenLightAlert and LeadDepartAlert are re-read every 3 s by sunnypilot/selfdrive/controls/lib/e2e_alerts_helper.py,
# and DevUIInfo every 5 s by selfdrive/ui/sunnypilot/ui_state.py, so all three apply without restarting the car.
# Both alerts are the e2eChime event: a sound with no on-screen text, which Quiet Mode mutes.

ALERT_NOTE = tr_noop("Not played when Quiet Mode is on. Note: This chime is only a notification. It is the driver's " +
                     "responsibility to observe their environment and make decisions accordingly.")
GREEN_LIGHT_DESC = tr_noop("A chime will play when you have been stopped for a couple of seconds with no vehicle detected " +
                           "ahead and the driving model starts planning to move forward, for example when the traffic light " +
                           "you are waiting at turns green. It can also chime at other stops where the model wants to go, " +
                           "such as a stop sign. It only plays while sunnypilot is not engaged. Steering-only MADS does not " +
                           "count as engaged.")
LEAD_DEPART_DESC = tr_noop("A chime will play when you are stopped close behind a vehicle (within a few meters) and it starts " +
                           "to move away. It only plays while sunnypilot is not engaged. Steering-only MADS does not count " +
                           "as engaged.")
DEV_UI_DESC = tr_noop("Display real-time parameters and metrics from various sources on the driving screen.")

# The button index is the stored DevUIInfo value, so each label sits at the mode the onroad renderer draws for it.
DEV_UI_OPTIONS = {
  DeveloperUiRenderer.DEV_UI_OFF: tr_noop("Off"),
  DeveloperUiRenderer.DEV_UI_RIGHT: tr_noop("Right"),
  DeveloperUiRenderer.DEV_UI_BOTTOM: tr_noop("Bottom"),
  DeveloperUiRenderer.DEV_UI_BOTH: tr_noop("Right & Bottom"),
}
assert sorted(DEV_UI_OPTIONS) == list(range(len(DEV_UI_OPTIONS)))


class VisualsLayout(Widget):
  def __init__(self):
    super().__init__()

    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=True, spacing=0)

  def _initialize_items(self):
    self._green_light_toggle = toggle_item_sp(
      param="GreenLightAlert",
      title=lambda: tr("Green Traffic Light Alert (Beta)"),
      description=lambda: f"{tr(GREEN_LIGHT_DESC)}<br><br>{tr(ALERT_NOTE)}",
    )
    self._lead_depart_toggle = toggle_item_sp(
      param="LeadDepartAlert",
      title=lambda: tr("Lead Departure Alert (Beta)"),
      description=lambda: f"{tr(LEAD_DEPART_DESC)}<br><br>{tr(ALERT_NOTE)}",
    )
    self._dev_ui = multiple_button_item_sp(
      param="DevUIInfo",
      title=lambda: tr("Developer UI"),
      description=lambda: tr(DEV_UI_DESC),
      buttons=[(lambda label=DEV_UI_OPTIONS[i]: tr(label)) for i in range(len(DEV_UI_OPTIONS))],
      button_width=350,
      inline=False,
    )

    return [
      self._green_light_toggle,
      self._lead_depart_toggle,
      self._dev_ui,
    ]

  def _sync_items(self):
    sync_toggle(self._green_light_toggle, ui_state.params)
    sync_toggle(self._lead_depart_toggle, ui_state.params)
    # A value the renderer has no mode for draws nothing, so it shows as Off.
    sync_buttons(self._dev_ui, ui_state.params, fallback=DeveloperUiRenderer.DEV_UI_OFF)

  def _render(self, rect):
    self._scroller.render(rect)

  def show_event(self):
    self._sync_items()
    self._scroller.show_event()
