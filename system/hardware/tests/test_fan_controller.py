import json
import pytest

from openpilot.system.hardware.fan_controller import FanConfig, TiciFanController

ALL_CONTROLLERS = [TiciFanController]

def patched_controller(mocker, controller_class):
  mocker.patch("os.system", new=mocker.Mock())
  return controller_class()

class TestFanController:
  def wind_up(self, controller, ignition=True):
    for _ in range(1000):
      controller.update(100, ignition)

  def wind_down(self, controller, ignition=False):
    for _ in range(1000):
      controller.update(10, ignition)

  @pytest.mark.parametrize("controller_class", ALL_CONTROLLERS)
  def test_hot_onroad(self, mocker, controller_class):
    controller = patched_controller(mocker, controller_class)
    self.wind_up(controller)
    assert controller.update(100, True) >= 70

  @pytest.mark.parametrize("controller_class", ALL_CONTROLLERS)
  def test_offroad_limits(self, mocker, controller_class):
    controller = patched_controller(mocker, controller_class)
    self.wind_up(controller)
    assert controller.update(100, False) <= 30

  @pytest.mark.parametrize("controller_class", ALL_CONTROLLERS)
  def test_no_fan_wear(self, mocker, controller_class):
    controller = patched_controller(mocker, controller_class)
    self.wind_down(controller)
    assert controller.update(10, False) == 0

  @pytest.mark.parametrize("controller_class", ALL_CONTROLLERS)
  def test_limited(self, mocker, controller_class):
    controller = patched_controller(mocker, controller_class)
    self.wind_up(controller, True)
    assert controller.update(100, True) == 100

  @pytest.mark.parametrize("controller_class", ALL_CONTROLLERS)
  def test_windup_speed(self, mocker, controller_class):
    controller = patched_controller(mocker, controller_class)
    self.wind_down(controller, True)
    for _ in range(10):
      controller.update(90, True)
    assert controller.update(90, True) >= 60


class TestFanConfig:
  def test_defaults_match_stock(self, mocker):
    controller = patched_controller(mocker, TiciFanController)
    for demand in range(101):
      assert controller.shape(demand) == demand

  def test_max_percent_scales_the_command(self, mocker):
    mocker.patch("os.system", new=mocker.Mock())
    controller = TiciFanController(FanConfig(max_percent=30))
    assert controller.shape(100) == 30
    assert controller.shape(50) == 15
    assert controller.shape(0) == 0

    # a fan that tops out at 2000 RPM can never reach the 6600 RPM the firmware asks for at 100%
    for _ in range(1000):
      controller.update(100, True)
    assert controller.update(100, True) == 30

  def test_min_percent_is_a_floor_only_while_running(self, mocker):
    mocker.patch("os.system", new=mocker.Mock())
    controller = TiciFanController(FanConfig(min_percent=25, max_percent=60))
    assert controller.shape(0) == 0
    assert controller.shape(1) == 25
    assert controller.shape(100) == 60

  def test_force_percent_overrides_everything(self, mocker):
    mocker.patch("os.system", new=mocker.Mock())
    controller = TiciFanController(FanConfig(force_percent=67))
    assert controller.shape(0) == 67
    assert controller.update(10, False) == 67
    assert controller.update(100, True) == 67

  def test_setpoint_changes_when_the_fan_spins_up(self, mocker):
    mocker.patch("os.system", new=mocker.Mock())
    cool = TiciFanController(FanConfig(setpoint_c=85.0, ff_lo_c=70.0, ff_hi_c=110.0))
    stock = TiciFanController(FanConfig())
    for _ in range(100):
      cool_out = cool.update(78, True)
      stock_out = stock.update(78, True)
    assert cool_out < stock_out

  def test_load_missing_file_is_stock(self, tmp_path):
    assert FanConfig.load(str(tmp_path / "nope.json")) == FanConfig()

  def test_load_ignores_unknown_keys(self, tmp_path):
    path = tmp_path / "fan_config.json"
    path.write_text(json.dumps({"max_percent": 40, "nonsense": True}))
    assert FanConfig.load(str(path)) == FanConfig(max_percent=40)

  def test_load_bad_json_is_stock(self, tmp_path):
    path = tmp_path / "fan_config.json"
    path.write_text("{ not json")
    assert FanConfig.load(str(path)) == FanConfig()

  def test_validate_clamps_out_of_range_values(self, tmp_path):
    path = tmp_path / "fan_config.json"
    path.write_text(json.dumps({"min_percent": 80, "max_percent": 20, "force_percent": 250, "min_rpm": -1}))
    config = FanConfig.load(str(path))
    assert config.min_percent == 80
    assert config.max_percent == 80
    assert config.force_percent == 100
    assert config.min_rpm == 0

  def test_validate_rejects_inverted_feedforward_ramp(self, tmp_path):
    path = tmp_path / "fan_config.json"
    path.write_text(json.dumps({"ff_lo_c": 90.0, "ff_hi_c": 50.0}))
    config = FanConfig.load(str(path))
    assert (config.ff_lo_c, config.ff_hi_c) == (60.0, 100.0)
