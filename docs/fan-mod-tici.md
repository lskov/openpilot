# Running a non-stock fan on a comma three (tici)

## The short version

The panda firmware this build ships does not command PWM duty, it commands a **target RPM**.
`set_fan_power(67)` does not mean "run at 67% duty", it means "spin at 67% of 6600 rpm", which is
4422 rpm. Whether that is a problem depends entirely on the fan you fitted, so measure before you
tune. A fan that reaches 6600 rpm tracks the command across the whole range and needs no
configuration at all. A fan that tops out well below it can never reach the target, the firmware's
integrator winds up to 100% duty and stays there, and the fan is left with two states, off and flat
out, with the temperature controller having no authority in between.

Upstream removed the ambiguity in commaai/panda `a2064b8`, "Change fan to use pure pwm", on
13 September 2025. The panda firmware in this build predates it: `panda/python/__init__.py` here
matches sunnyhaibin/panda `0e7a3fd` from 9 August 2025. Note that **sunnypilot master already carries
the change**, because it pins a newer panda, so this is a backport rather than an unsolved problem.

There are two ways to deal with it. The software route needs no firmware work and is described first.
The firmware route removes the whole class of problem and is described after it.

### What this device actually measured

A sweep of the modded comma three this document was written for, at 10% steps:

| command | rpm | applied duty |
|--------:|----:|-------------:|
| 10% | 665 | 21% |
| 30% | 1949 | 35% |
| 50% | 3246 | 52% |
| 70% | 4529 | 69% |
| 100% | 6498 | 87% |

Two things to read off it. The rpm is almost exactly `6500 * command / 100` at every step, so the
closed loop is hitting its target across the full range and this fan is not speed-limited at all.
And the applied duty is *not* the command, it is whatever the loop needed, which is what identifies
the firmware as closed loop rather than pure PWM. Note that duty crosses the command line around
50-70%: a single-point probe there would misidentify the firmware, which is why `fan_calibrate.py`
decides from the whole sweep.

For this device the conclusion is that no config file is needed. Removing the hardcoded fan output
is the entire fix.

## How the fan is actually wired

The panda drives three lines to the fan connector. `GPIOD3` enables the fan and IR power rail, and it
is shared with the IR LEDs, which is why the firmware comments note that a fan controller reset does
not work while IR is on. `GPIOC8` is `TIM3_CH3`, a 25 kHz PWM output, which is the speed control line
a four-wire fan expects. `GPIOD2` is the tachometer input on `EXTI2`, counted on both edges, so the
firmware expects four edges per revolution. That matches the two-pulse-per-revolution convention every
standard PC fan uses, so a four-wire PC fan is electrically compatible and its tachometer should read
correctly.

With the firmware in this build, `fan_tick()` runs at 8 Hz and integrates the RPM error:

```c
float error = (fan_state.target_rpm - fan_rpm_fast) / ((float) current_board->fan_max_rpm);
fan_state.error_integral += 6.5f * error;
fan_state.power = CLAMP(fan_state.error_integral, 0U, current_board->fan_max_pwm);
```

`fan_max_rpm` is 6600 on a tres. Two things follow. A fan that cannot reach the target saturates the
integrator at 100%, and a fan with **no tachometer connected at all** reads zero rpm forever, which
saturates it just the same and additionally trips openpilot's `fanMalfunction` alert.

## Software route: calibrate the command range

The fan controller now reads its tuning from `/data/fan_config.json`. The file is optional and a
missing file gives exactly the stock behaviour, so nothing changes until you write one. Because it is
plain JSON read at process start, it works on a prebuilt install with no rebuild.

Measure the fan first. Stop openpilot over ssh, since pandad holds the panda, then sweep it. This is
the same thing `tools/op.sh` does, and it survives until you start it again, unlike killing the tmux
session, which systemd brings straight back:

```bash
sudo systemctl stop comma
cd /data/openpilot && ./system/hardware/tici/fan_calibrate.py
sudo systemctl restart comma
```

The script detects which firmware the panda is running, steps the command from 0 to 100%, records the
rpm and the duty the firmware actually applied at each step, and prints a suggested config. Re-run it
with `--write` to save that config. Reboot afterwards.

The keys it sets are these. `max_percent` is the important one: on the closed-loop firmware it should
be `100 * fan_max_rpm / 6600`, so a 2100 rpm fan wants roughly 32, and the controller's full 0 to 100%
demand is then mapped into 0 to 32% of command, which is 0 to 2100 rpm of target. That restores real
proportional control. `min_percent` is the floor applied whenever the fan runs at all, for a fan that
will not start from rest at low duty. `min_rpm` is the threshold below which openpilot calls the fan
broken, and setting it to 0 disables the `fanMalfunction` alert for a fan with no tachometer wired.
`setpoint_c`, `ff_lo_c` and `ff_hi_c` move the temperature target and the feedforward ramp, which is
how you trade noise against cooling. `force_percent` pins the output to a fixed value and exists for
bring-up only, since it runs the fan offroad as well and wears it out.

A worked example for a fan measured at 2100 rpm that will not start below 20% command:

```json
{
  "min_percent": 20,
  "max_percent": 32,
  "min_rpm": 450
}
```

## Watching it work

`fan_calibrate.py` measures the fan with openpilot stopped. To see the whole thermal loop while it
runs, use `fan_watch.py`, which needs openpilot up because it subscribes to `deviceState` and
`peripheralState`:

```bash
./system/hardware/tici/fan_watch.py
```

It prints a line a second: current and peak `maxTempC`, the thermal status band, the percentage the
controller is asking for, the rpm the fan is delivering, the rpm that command implies, and the ratio
between the last two.

```
   temp    peak     status  desired     rpm  target  ratio
  77.5C   77.5C     yellow      34%    2210    2244    98%
  88.1C   88.1C        red     100%    6480    6600    98%
  91.0C   91.0C        red     100%    3100    6600    47%
```

Read the ratio first. Well under 100% means the fan is not delivering what it was told to, which is a
fan or firmware problem and the calibration sweep is where to look. Sitting near 100% while desired is
pinned at 100% and the temperature still climbs means the opposite: the fan is doing everything asked
of it and the limit is elsewhere, usually the airflow path or the heatsink contact rather than
anything in software.

For general CPU and memory context alongside it, `selfdrive/debug/live_cpu_and_temp.py` already
exists, and `selfdrive/debug/dump.py deviceState` prints the raw message.

## Firmware route: backport pure PWM

The better fix is to make the command mean duty cycle again, which is what upstream did. After it,
`set_fan_power()` writes the duty straight to `TIM3_CH3`, the tachometer is used for reporting only,
and the fan's own top speed stops mattering. `max_percent` then just caps duty and can stay at 100.

The panda sources are not in this repo, only the signed binaries under `panda/board/obj/`, so build
elsewhere and copy the output in. Apply the fan part of `a2064b8` on top of the panda commit this
build ships, `0e7a3fd`, rather than jumping to panda master. That commit touches only the fan driver
and the board fan configuration, it does not touch `board/health.h`, so the health and protocol packet
versions are unchanged and no openpilot-side change is needed to match.

```bash
git clone https://github.com/sunnyhaibin/panda.git && cd panda
git checkout 0e7a3fd
git remote add comma https://github.com/commaai/panda.git && git fetch comma
git cherry-pick -n a2064b8
docker build -t panda-fw .
docker run --rm -v "$PWD:/panda" -w /panda panda-fw \
  bash -c "git config --global --add safe.directory /panda && scons -j8"
```

One conflict is guaranteed and it is not in the fan driver. `a2064b8` drops `fan_max_rpm` and
`fan_max_pwm` from `struct board` and updates every board header that upstream still had at the time,
which no longer included the comma two. This commit predates the removal of the F4 boards, so
`board/boards/dos.h` is still here and still sets both fields. Replace them with `.has_fan = true,`
by hand or the build will not compile, even though nothing about the comma two matters to us.

The build is debug-signed with the key already in the repo at `board/crypto/certs/debug`, and that is
enough: pandad flashes whatever is in `panda/board/obj/`, and if the new firmware does not boot under
the release bootstub it falls back to flashing the development bootloader itself. Copy
`board/obj/panda_h7.bin.signed` and `board/obj/bootstub.panda_h7.bin` into `panda/board/obj/` in this
repo and reboot. pandad compares signatures, sees the mismatch and reflashes on the next start.

Re-run `fan_calibrate.py` afterwards. It will report pure PWM and suggest `max_percent: 100`.

## Keeping this fork current

sunnypilot no longer maintains the tici branch closely, so the fan work above is ours to carry. Two
upstream changes are worth tracking. The panda fan driver is the one that matters and is covered
above. The other is sunnypilot's own `FanController`, which now raises the temperature setpoint by
5 C on tici and tizi to cut fan noise after the AGNOS 18.1 thermal threshold change. That is a
deliberate trade of cooling for quiet and it is the opposite of what a modded fan usually wants, so it
is left out here and exposed as `setpoint_c` instead. Raise it if you want the quieter upstream
behaviour.
