"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.common.params import Params
from openpilot.system.ui.sunnypilot.widgets.list_view import ListItemSP

# The settings widgets read their param once, when they are built. The driving code rewrites some of
# these keys at every car start and sunnylink can change any of them remotely, so panels re-read them
# when shown. Nothing here writes a param: OptionControlSP.set_value() does, so it is not used.


def sync_toggle(item: ListItemSP, params: Params) -> None:
  # ToggleActionSP keeps the key on the ToggleSP it wraps.
  item.action_item.set_state(params.get_bool(item.action_item.toggle.param_key))


def sync_option(item: ListItemSP, params: Params) -> int:
  """Show the stored value, and return it.

  A value outside min..max is shown at the nearest end, so -/+ always work from it. With a value_map, a
  stored value that is not one of the choices is shown at the nearest choice below it (or the first).
  """
  action = item.action_item
  stored = int(params.get(action.param_key, return_default=True))
  if action.value_map:
    below = [k for k, v in action.value_map.items() if v <= stored]
    action.current_value = int(max(below, key=lambda k: action.value_map[k])) if below else action.min_value
  else:
    action.current_value = min(max(stored, action.min_value), action.max_value)
  return stored


def sync_buttons(item: ListItemSP, params: Params, fallback: int = 0) -> None:
  """Select the stored button. The widget draws its highlight at index * width without bounds checks,
  so a stored index with no button shows as `fallback`, which callers set to what the car does with it."""
  action = item.action_item
  index = int(params.get(action.param_key, return_default=True))
  action.set_selected_button(index if 0 <= index < len(action.buttons) else fallback)


def set_description(item: ListItemSP, text: str) -> None:
  """Change a row's description and keep the row's height right.

  A row re-measures itself only when its description opens, and parses new text first only if it has an
  opened callback (system/ui/widgets/list_view.py, _set_description_visible). Register a no-op one so any
  later open measures the current text, and re-open now if the description is already showing.
  """
  if item.description_opened_callback is None:
    item.set_description_opened_callback(lambda: None)
  if item.description == text:
    return
  item.set_description(text)
  if item.description_visible:
    item.show_description(False)
    item.show_description(True)


def open_descriptions(items: list[ListItemSP]) -> None:
  """Open descriptions a panel wants shown. Call it after the panel's Scroller has rendered: a row
  measures its description at its current width, and rows only get the list's width when the Scroller
  lays them out, so opening one from show_event on a first visit makes the row far too tall."""
  for item in items:
    item.show_description(True)
  items.clear()
