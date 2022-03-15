from selfdrive.controls.lib.drive_helpers import update_v_cruise

class VolkswagenSpeedlimits:

  # configurable toggles
  ignore_limit_when_difference_too_high = True
  ignore_limit_when_following_lead = True


  # configurable offsets

  # these offsets will be applied when OP is not engaged
  offsetsNotEngaged = {
                                  0:  {'targetSpeed': 30 },
                                30:  {'targetSpeed': 30 },
                                50:  {'targetSpeed': 50 },
                                60:  {'targetSpeed': 60 },
                                70:  {'targetSpeed': 70 },
                                80:  {'targetSpeed': 80 },
                                100: {'targetSpeed': 103 },
                                110: {'targetSpeed': 110 },
                                120: {'targetSpeed': 120 },
                                130: {'targetSpeed': 130 },
                                140: {'targetSpeed': 140 },
                                150: {'targetSpeed': 150 }
                                }
  # these offsets will be applied when the car is currently slower than a new speedlimit
  offsetsAccel = {
                                0:  {'targetSpeed': 30 },
                                30:  {'targetSpeed': 30 },
                                50:  {'targetSpeed': 52 },
                                60:  {'targetSpeed': 62 },
                                70:  {'targetSpeed': 72 },
                                80:  {'targetSpeed': 82 },
                                100: {'targetSpeed': 103 },
                                110: {'targetSpeed': 110 },
                                120: {'targetSpeed': 122 },
                                130: {'targetSpeed': 130 },
                                140: {'targetSpeed': 140 },
                                150: {'targetSpeed': 150 }
                                }
  # these offsets will be applied when the car is currently faster than a new speedlimit
  offsetsDecel = {
                                50:  {'targetSpeed': 53 },
                                60:  {'targetSpeed': 64 },
                                80:  {'targetSpeed': 90 },
                                100: {'targetSpeed': 103 },
                                110: {'targetSpeed': 113 },
                                120: {'targetSpeed': 123 },
                                130: {'targetSpeed': 135 },
                                140: {'targetSpeed': 140 },
                                150: {'targetSpeed': 150 }
                                }


  setpoint = 0
  targetSetpoint = 0
  currentSpeed = 0
  speedAdjustInProgress = False
  allowNextButtonPress = False
  nextStepTimer = 0
  radarDistance = 0
  currentSpeedlimit = 0
  newSpeedlimit = 0
  processedSpeedlimit = -1
  wasEngagedBefore = False
  tempSpeedLimit = 0

  def __init__(self):
    self.initvar = 0


  @classmethod
  def update_speed_limit(cls, CS, v_cruise_kph, enabled):
    # read current CAN values
    cls.radarDistance = CS.radarDistance
    cls.currentSpeed = round(CS.vEgoRaw * 3.6)
    cls.setpoint = v_cruise_kph
    cls.newSpeedlimit = round(CS.trafficSign * 5) if CS.trafficSign < 104 else 140

    # abort current adjustment if a new limit is received while adjusting
    if cls.speedAdjustInProgress and cls.currentSpeedlimit != cls.newSpeedlimit:
        cls.processedSpeedlimit = cls.currentSpeedlimit
        cls.speedAdjustInProgress = False

    # ignore new limit after manual setpoint adjustment (setpoint is already lower than new limit)
    if cls.newSpeedlimit < cls.processedSpeedlimit and cls.setpoint <= cls.newSpeedlimit:
      cls.processedSpeedlimit = cls.currentSpeedlimit
      cls.speedAdjustInProgress = False

    # ignore new limit after manual setpoint adjustment (setpoint is lower than last processed limit)
    if cls.newSpeedlimit > cls.processedSpeedlimit and cls.setpoint < cls.processedSpeedlimit:
      cls.processedSpeedlimit = cls.currentSpeedlimit
      cls.speedAdjustInProgress = False

    # new speed limit received, proceed to adjustment logic
    if not cls.speedAdjustInProgress:
      cls.currentSpeedlimit = cls.newSpeedlimit
      cls.targetSetpoint = 0
      cls.nextStepTimer = 0

    # set temporary limit for smooth slow down to stop, priority 1
    #if cls.radarDistance < 50 and cls.currentSpeed > 60:
    #  cls.speedAdjustInProgress = True
    #  cls.targetSetpoint = cls.currentSpeed - 20

    # when engaged use the following 2 routines to adjust the ACC setpoint depending on the current speed
    if CS.cruiseState.enabled and not CS.standstill:
      cls.wasEngagedBefore = True

      # 1: logic when car is currently faster than speed limit
      if cls.currentSpeed > cls.currentSpeedlimit and not cls.speedAdjustInProgress and cls.processedSpeedlimit != cls.currentSpeedlimit:
        cls.speedAdjustInProgress = True
        cls.allowNextButtonPress = True

        if cls.ignore_limit_when_difference_too_high and cls.currentSpeed - cls.currentSpeedlimit > 25:
          # ignore speed limit if unplausible speed difference, treat speedlimit as processed
          cls.processedSpeedlimit = cls.currentSpeedlimit
        elif cls.ignore_limit_when_following_lead and cls.radarDistance > 0:
          # if currently following another car, adopt the speed of the lead to stay in traffic flow
          cls.targetSetpoint = cls.currentSpeed + 2
        else:
          # apply the setpoint via the offset table "offsetsDecel"
          if cls.currentSpeedlimit in cls.offsetsDecel:
            cls.targetSetpoint = cls.offsetsDecel[cls.currentSpeedlimit]['targetSpeed']


      # 2: logic when car is currently slower than speed limit
      if cls.currentSpeed < cls.currentSpeedlimit and not cls.speedAdjustInProgress and cls.processedSpeedlimit != cls.currentSpeedlimit:
        cls.speedAdjustInProgress = True

        if cls.ignore_limit_when_difference_too_high and cls.currentSpeedlimit - cls.currentSpeed > 20 and (cls.radarDistance == 0 or cls.radarDistance > 80):
          # limit max setpoint increment to 20 if there is no lead car to avoid excessive acceleration
          if cls.currentSpeed + 20 < cls.currentSpeedlimit and cls.currentSpeed + 20 >= 50:
            cls.targetSetpoint = cls.currentSpeed + 20
        else:
          # apply the setpoint via the offset table "offsetsAccel"
          if cls.currentSpeedlimit in cls.offsetsAccel:
            cls.targetSetpoint = cls.offsetsAccel[cls.currentSpeedlimit]['targetSpeed']


    # when not engaged, continue to pre-set the acc setpoint to speed limits (like stock pACC does)
    elif not CS.cruiseState.enabled:
      # if OP was engaged before, abort currently running setpoint adjustments
      if cls.wasEngagedBefore:
        cls.speedAdjustInProgress = False
        cls.wasEngagedBefore = False

      if not cls.speedAdjustInProgress and cls.processedSpeedlimit != cls.currentSpeedlimit:
        cls.speedAdjustInProgress = True

        if cls.currentSpeedlimit in cls.offsetsNotEngaged:
          # apply the setpoint via the offset table "offsetsNotEngaged"
          cls.targetSetpoint = cls.offsetsNotEngaged[cls.currentSpeedlimit]['targetSpeed']


    # setpoint adjustment logic
    if cls.speedAdjustInProgress and cls.setpoint != cls.targetSetpoint and cls.targetSetpoint > 0 and CS.cruiseState.available:
      v_cruise_kph = cls.targetSetpoint
      cls.speedAdjustInProgress = False
      cls.processedSpeedlimit = cls.currentSpeedlimit
    else:
      cls.speedAdjustInProgress = False
      cls.processedSpeedlimit = cls.currentSpeedlimit

    return v_cruise_kph

  @staticmethod
  def update_cruise_buttons(v_cruise_kph, buttonEvents, button_timers, enabled, metric, CS):

    v_cruise_kph = VolkswagenSpeedlimits.update_speed_limit(CS, v_cruise_kph, enabled)
    v_cruise_kph = update_v_cruise(v_cruise_kph, buttonEvents, button_timers, enabled, metric)

    return v_cruise_kph