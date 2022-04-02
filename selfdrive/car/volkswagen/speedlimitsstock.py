from common.realtime import sec_since_boot
from selfdrive.car.volkswagen.values import BUTTON_STATES

class VolkswagenSpeedlimitsStock:

  # global variables for sign-based speed limit recognition
  setpoint = 0
  targetSetpoint = 0
  currentSpeed = 0
  speedAdjustInProgress = False
  allowNextButtonPress = False
  nextStepTimer = 0
  smoothAdjust = False
  radarDistance = 0
  visionDistance = 0
  currentSpeedlimit = 0
  newSpeedlimit = 0
  processedSpeedlimit = -1
  requiredBtnPresses = 15
  BtnPressCounter = 0
  wasEngagedBefore = False
  leadSpeed = 0


  # configurable toggles
  smooth_adjust_option = True
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
                                100: {'targetSpeed': 100 },
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

  def __init__(self):
    self.initvar = 0


  @classmethod
  def update_speed_limit(cls, CS, c, graMsgSentCount):
    graButtonStatesToSend = None
    #-------------------------------------------------------------------------#
    #      adjust ACC setpoint from sign-based speed limit recognition        #
    #-------------------------------------------------------------------------#
    if c.hud_control.leadProb > 0:
        cls.visionDistance = c.hud_control.leadDistance
        cls.leadSpeed = round(c.hud_control.leadSpeed * 3.6)
    else:
        cls.visionDistance = 200
        cls.leadSpeed = 200

    # read current CAN values
    cls.rightStandziele = CS.rightStandziele
    cls.leftStandziele = CS.leftStandziele
    cls.rightKolonne = CS.rightKolonne
    cls.leftKolonne = CS.leftKolonne
    cls.radarDistance = CS.out.radarDistance
    cls.currentSpeed = round(CS.out.vEgoRaw * 3.6)
    cls.setpoint = round(CS.out.cruiseState.speed * 3.6)
    cls.newSpeedlimit = round(CS.out.trafficSign * 5) if CS.out.trafficSign < 104 else 150
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

    if not cls.speedAdjustInProgress:
        cls.currentSpeedlimit = cls.newSpeedlimit
        cls.targetSetpoint = 0
        cls.nextStepTimer = 0
        cls.smoothAdjust = False
        cls.BtnPressCounter = 0
        cls.requiredBtnPresses = 15

    # when engaged use the following 2 routines to adjust the ACC setpoint depending on the current speed
    if c.enabled and CS.out.cruiseState.enabled and not CS.out.standstill:
        cls.wasEngagedBefore = True

        # priority 1: set temporary setpoint for smooth slow down when approaching slow or stopped cars
        if cls.leadSpeed < 50 and not cls.speedAdjustInProgress:
            if cls.visionDistance < 100:
                cls.targetSetpoint = cls.currentSpeed - 20
            if cls.visionDistance < 70:
                cls.targetSetpoint = 40
            if cls.visionDistance < 50:
                cls.targetSetpoint = 30
            if cls.targetSetpoint < 30:
                cls.targetSetpoint = 30
            if cls.setpoint > 30:
                cls.speedAdjustInProgress = True

        # 1: logic when car is currently faster than speed limit
        if cls.currentSpeed > cls.currentSpeedlimit and not cls.speedAdjustInProgress and cls.processedSpeedlimit != cls.currentSpeedlimit:
            cls.speedAdjustInProgress = True
            cls.smoothAdjust = cls.smooth_adjust_option
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
    elif not c.enabled:
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
    if cls.speedAdjustInProgress and cls.setpoint != cls.targetSetpoint and cls.targetSetpoint > 0 and CS.out.cruiseState.available and cls.BtnPressCounter <= cls.requiredBtnPresses:
        cur_time = sec_since_boot()
        BtnPressesTen = int(round(abs(cls.processedSpeedlimit - cls.targetSetpoint) + 5.1,-1) / 10)
        BtnPressesSingle = cls.targetSetpoint % 10
        cls.requiredBtnPresses = BtnPressesTen + BtnPressesSingle + 3

        if graMsgSentCount == 0:

            if cls.smoothAdjust:
            # if there's more than one button press needed to reach the targetSetpoint, wait after each press until
            # the intermediate setpoint speed is actually reached, resulting in a less abrupt slow down
                if abs(cls.setpoint - cls.currentSpeed) < 3 or (cls.currentSpeed < cls.setpoint and cls.targetSetpoint <= cls.currentSpeed) or cur_time > cls.nextStepTimer + 10:
                    cls.allowNextButtonPress = True

            if cls.allowNextButtonPress or not cls.smoothAdjust:
                cls.allowNextButtonPress = False
                cls.nextStepTimer = cur_time
                if cls.setpoint > cls.targetSetpoint:
                    graButtonStatesToSend = BUTTON_STATES.copy()
                    graButtonStatesToSend["decelCruise"] = True
                    cls.BtnPressCounter += 1
                if cls.setpoint < cls.targetSetpoint and cls.targetSetpoint - cls.setpoint >= 10:
                    graButtonStatesToSend = BUTTON_STATES.copy()
                    graButtonStatesToSend["accelCruise"] = True
                    cls.BtnPressCounter += 1

            if cls.setpoint < cls.targetSetpoint and cls.targetSetpoint - cls.setpoint < 10:
                if c.enabled:
                    graButtonStatesToSend = BUTTON_STATES.copy()
                    graButtonStatesToSend["resumeCruise"] = True
                    cls.BtnPressCounter += 1
                else:
                    # never press the resume button when not engaged, otherwise OP would engage itself in a loop
                    # when not engaged, small adjust steps are not possible, abort adjustment process
                    cls.speedAdjustInProgress = False
                    cls.processedSpeedlimit = cls.currentSpeedlimit
    else:
        cls.speedAdjustInProgress = False
        cls.processedSpeedlimit = cls.currentSpeedlimit

    return graButtonStatesToSend

  @staticmethod
  def update_cruise_buttons(CS, c, graMsgSentCount):

    graButtonStatesToSend = VolkswagenSpeedlimitsStock.update_speed_limit(CS, c, graMsgSentCount)
    return graButtonStatesToSend