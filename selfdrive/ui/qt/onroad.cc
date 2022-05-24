#include "selfdrive/ui/qt/onroad.h"

#include <cmath>

#include <QDebug>
#include <iomanip>
#include <sstream>
#include <QString>
#include <QMouseEvent>

#include "common/timing.h"
#include "selfdrive/ui/qt/util.h"
#include "selfdrive/common/params.h"
#ifdef ENABLE_MAPS
#include "selfdrive/ui/qt/maps/map.h"
#include "selfdrive/ui/qt/maps/map_helpers.h"
#endif

OnroadWindow::OnroadWindow(QWidget *parent) : QWidget(parent) {
  QVBoxLayout *main_layout  = new QVBoxLayout(this);
  main_layout->setMargin(bdr_s);
  QStackedLayout *stacked_layout = new QStackedLayout;
  stacked_layout->setStackingMode(QStackedLayout::StackAll);
  main_layout->addLayout(stacked_layout);

  nvg = new NvgWindow(VISION_STREAM_ROAD, this);

  QWidget * split_wrapper = new QWidget;
  split = new QHBoxLayout(split_wrapper);
  split->setContentsMargins(0, 0, 0, 0);
  split->setSpacing(0);
  split->addWidget(nvg);

  stacked_layout->addWidget(split_wrapper);

  alerts = new OnroadAlerts(this);
  alerts->setAttribute(Qt::WA_TransparentForMouseEvents, true);
  stacked_layout->addWidget(alerts);

  // setup stacking order
  alerts->raise();

  setAttribute(Qt::WA_OpaquePaintEvent);
  QObject::connect(uiState(), &UIState::uiUpdate, this, &OnroadWindow::updateState);
  QObject::connect(uiState(), &UIState::offroadTransition, this, &OnroadWindow::offroadTransition);
}

void OnroadWindow::updateState(const UIState &s) {
   QColor bgColor = bg_colors[s.status];
  Alert alert = Alert::get(*(s.sm), s.scene.started_frame);
  if (s.sm->updated("controlsState") || !alert.equal({})) {
    if (alert.type == "controlsUnresponsive") {
      bgColor = bg_colors[STATUS_ALERT];
    } else if (alert.type == "controlsUnresponsivePermanent") {
      bgColor = bg_colors[STATUS_DISENGAGED];
    }
    alerts->updateAlert(alert, bgColor);
  }

  nvg->updateState(s);

  if (bg != bgColor) {
    // repaint border
    bg = bgColor;
    update();
  }
}


void OnroadWindow::mousePressEvent(QMouseEvent* e) {
  bool sidebarVisible = geometry().x() > 0;
  bool propagate_event = true;
  UIState *s = uiState();
  
  const QRect dev_ui_touch_rect = max_speed_rc;

  if (s->scene.show_debug_ui && dev_ui_touch_rect.contains(e->x(), e->y())) {
    s->scene.dev_ui_enabled = s->scene.dev_ui_enabled + 1;
    if (s->scene.dev_ui_enabled > 2) {
      s->scene.dev_ui_enabled = 0;
    }
    if (s->scene.dev_ui_enabled == 0) {
      Params().put("DevUI", "0", 1);
    } else if (s->scene.dev_ui_enabled == 1) {
      Params().put("DevUI", "1", 1);
    } else if (s->scene.dev_ui_enabled == 2) {
      Params().put("DevUI", "2", 1);
    }
    propagate_event = false;
  }
  else if (map != nullptr) {
    map->setVisible(!sidebarVisible && !map->isVisible());
  }
  // propagation event to parent(HomeWindow)
  if (propagate_event) {
    QWidget::mousePressEvent(e);
  }
}

void OnroadWindow::offroadTransition(bool offroad) {
#ifdef ENABLE_MAPS
  if (!offroad) {
    if (map == nullptr && (uiState()->prime_type || !MAPBOX_TOKEN.isEmpty())) {
      MapWindow * m = new MapWindow(get_mapbox_settings());
      map = m;

      QObject::connect(uiState(), &UIState::offroadTransition, m, &MapWindow::offroadTransition);

      m->setFixedWidth(topWidget(this)->width() / 2);
      split->addWidget(m, 0, Qt::AlignRight);

      // Make map visible after adding to split
      m->offroadTransition(offroad);
    }
  }
#endif

  alerts->updateAlert({}, bg);

  // update stream type
  bool wide_cam = Hardware::TICI() && Params().getBool("EnableWideCamera");
  nvg->setStreamType(wide_cam ? VISION_STREAM_WIDE_ROAD : VISION_STREAM_ROAD);
}

void OnroadWindow::paintEvent(QPaintEvent *event) {
  QPainter p(this);
  p.fillRect(rect(), QColor(bg.red(), bg.green(), bg.blue(), 255));
}

// ***** onroad widgets *****

// OnroadAlerts
void OnroadAlerts::updateAlert(const Alert &a, const QColor &color) {
  if (!alert.equal(a) || color != bg) {
    alert = a;
    bg = color;
    update();
  }
}

void OnroadAlerts::paintEvent(QPaintEvent *event) {
  if (alert.size == cereal::ControlsState::AlertSize::NONE) {
    return;
  }
  static std::map<cereal::ControlsState::AlertSize, const int> alert_sizes = {
    {cereal::ControlsState::AlertSize::SMALL, 271},
    {cereal::ControlsState::AlertSize::MID, 420},
    {cereal::ControlsState::AlertSize::FULL, height()},
  };
  int h = alert_sizes[alert.size];
  QRect r = QRect(0, height() - h, width(), h);

  QPainter p(this);

  // draw background + gradient
  p.setPen(Qt::NoPen);
  p.setCompositionMode(QPainter::CompositionMode_SourceOver);

  p.setBrush(QBrush(bg));
  p.drawRect(r);

  QLinearGradient g(0, r.y(), 0, r.bottom());
  g.setColorAt(0, QColor::fromRgbF(0, 0, 0, 0.05));
  g.setColorAt(1, QColor::fromRgbF(0, 0, 0, 0.35));

  p.setCompositionMode(QPainter::CompositionMode_DestinationOver);
  p.setBrush(QBrush(g));
  p.fillRect(r, g);
  p.setCompositionMode(QPainter::CompositionMode_SourceOver);

  // text
  const QPoint c = r.center();
  p.setPen(QColor(0xff, 0xff, 0xff));
  p.setRenderHint(QPainter::TextAntialiasing);
  if (alert.size == cereal::ControlsState::AlertSize::SMALL) {
    configFont(p, "Open Sans", 74, "SemiBold");
    p.drawText(r, Qt::AlignCenter, alert.text1);
  } else if (alert.size == cereal::ControlsState::AlertSize::MID) {
    configFont(p, "Open Sans", 88, "Bold");
    p.drawText(QRect(0, c.y() - 125, width(), 150), Qt::AlignHCenter | Qt::AlignTop, alert.text1);
    configFont(p, "Open Sans", 66, "Regular");
    p.drawText(QRect(0, c.y() + 21, width(), 90), Qt::AlignHCenter, alert.text2);
  } else if (alert.size == cereal::ControlsState::AlertSize::FULL) {
    bool l = alert.text1.length() > 15;
    configFont(p, "Open Sans", l ? 132 : 177, "Bold");
    p.drawText(QRect(0, r.y() + (l ? 240 : 270), width(), 600), Qt::AlignHCenter | Qt::TextWordWrap, alert.text1);
    configFont(p, "Open Sans", 88, "Regular");
    p.drawText(QRect(0, r.height() - (l ? 361 : 420), width(), 300), Qt::AlignHCenter | Qt::TextWordWrap, alert.text2);
  }
}

// NvgWindow

NvgWindow::NvgWindow(VisionStreamType type, QWidget* parent) : fps_filter(UI_FREQ, 3, 1. / UI_FREQ), CameraViewWidget("camerad", type, true, parent) {
  engage_img = loadPixmap("../assets/img_chffr_wheel.png", {img_size, img_size});
  dm_img = loadPixmap("../assets/img_driver_face.png", {img_size, img_size});
}

void NvgWindow::updateState(const UIState &s) {
  const int SET_SPEED_NA = 255;
  const SubMaster &sm = *(s.sm);
  const auto cs = sm["controlsState"].getControlsState();

  float maxspeed = cs.getVCruise();
  bool cruise_set = maxspeed > 0 && (int)maxspeed != SET_SPEED_NA;
  if (cruise_set && !s.scene.is_metric) {
    maxspeed *= KM_TO_MILE;
  }
  QString maxspeed_str = cruise_set ? QString::number(std::nearbyint(maxspeed)) : "N/A";
  float cur_speed = std::max(0.0, sm["carState"].getCarState().getVEgo() * (s.scene.is_metric ? MS_TO_KPH : MS_TO_MPH));

  setProperty("is_cruise_set", cruise_set);
  setProperty("speed", QString::number(std::nearbyint(cur_speed)));
  setProperty("maxSpeed", maxspeed_str);
  setProperty("speedUnit", s.scene.is_metric ? "km/h" : "mph");
  setProperty("hideDM", cs.getAlertSize() != cereal::ControlsState::AlertSize::NONE);
  setProperty("status", s.status);
  //setProperty("is_brakelight_on", sm["carState"].getCarState().getBrakeLights());

  // update engageability and DM icons at 2Hz
  if (sm.frame % (UI_FREQ / 2) == 0) {
    setProperty("engageable", cs.getEngageable() || cs.getEnabled());
    setProperty("dmActive", sm["driverMonitoringState"].getDriverMonitoringState().getIsActiveMode());
    setProperty("showDebugUI", s.scene.show_debug_ui);

    if (cs.getEnabled() ) {
      uint64_t cur_time = nanos_since_boot() * 1e-9;
      if (openpilotEngagedElapsedTime == 0)
        openpilotEngagedElapsedTime = cur_time;

      setProperty("openpilotActiveTime",(int)(cur_time - openpilotEngagedElapsedTime)) ;
    } else {
      openpilotEngagedElapsedTime = 0;
    } 
  }  
  //const auto leadOne = sm["radarState"].getRadarState().getLeadOne();
  const auto carState = sm["carState"].getCarState();
  const auto gpsLocationExternal = sm["gpsLocationExternal"].getGpsLocationExternal();

  setProperty("lead_d_rel", sm["radarState"].getRadarState().getLeadOne().getDRel());
  //setProperty("lead_v_rel", leadOne.getVRel());
  setProperty("lead_v_rel", sm["radarState"].getRadarState().getLeadOne().getVRel());
  
  setProperty("lead_status", 1);//sm["radarState"].getRadarState().getLeadOne().getStatus());
  setProperty("angleSteers", carState.getSteeringAngleDeg());
  setProperty("steerAngleDesired", sm["controlsState"].getControlsState().getLateralControlState().getPidState().getSteeringAngleDesiredDeg());
  setProperty("devUiEnabled", s.scene.dev_ui_enabled);
  setProperty("gpsAccuracy", gpsLocationExternal.getAccuracy());
  setProperty("altitude", gpsLocationExternal.getAltitude());
  setProperty("vEgo", carState.getVEgo());
  setProperty("aEgo", carState.getAEgo());
  setProperty("steeringTorque", carState.getSteeringTorque());
  setProperty("steeringTorqueEps", carState.getSteeringTorqueEps());
  setProperty("bearingAccuracyDeg", gpsLocationExternal.getBearingAccuracyDeg());
  setProperty("bearingDeg", gpsLocationExternal.getBearingDeg());
  //setProperty("suspended", sm["controlsState"].getControlsState().get<Suspended(>));
}

void NvgWindow::drawHud(QPainter &p) {
  p.save();

  // Header gradient
  QLinearGradient bg(0, header_h - (header_h / 2.5), 0, header_h);
  bg.setColorAt(0, QColor::fromRgbF(0, 0, 0, 0.45));
  bg.setColorAt(1, QColor::fromRgbF(0, 0, 0, 0));
  p.fillRect(0, 0, width(), header_h, bg);

  // max speed
  QRect rc(bdr_s * 2, bdr_s * 1.5, 184, 202);
  p.setPen(QPen(QColor(0xff, 0xff, 0xff, 100), 10));
  p.setBrush(QColor(0, 0, 0, 100));
  p.drawRoundedRect(rc, 20, 20);
  p.setPen(Qt::NoPen);

  configFont(p, "Open Sans", 48, "Regular");
  drawText(p, rc.center().x(), 118, "MAX", is_cruise_set ? 200 : 100);
  if (is_cruise_set) {
    configFont(p, "Open Sans", 88, is_cruise_set ? "Bold" : "SemiBold");
    drawText(p, rc.center().x(), 212, maxSpeed, 255);
  } else {
    configFont(p, "Open Sans", 80, "SemiBold");
    drawText(p, rc.center().x(), 212, maxSpeed, 100);
  }

  // current speed
  configFont(p, "Open Sans", 176, "Bold");
  drawSpeedText(p, rect().center().x(), 210, speed, is_brakelight_on ? QColor(0xff, 0, 0, 255) : QColor(0xff, 0xff, 0xff, 255));
  configFont(p, "Open Sans", 66, "Regular");
  drawText(p, rect().center().x(), 290, speedUnit, 200);

  // engage-ability icon
  if (engageable) {
      drawIcon(p, rect().right() - radius / 2 - bdr_s * 2, radius / 2 + int(bdr_s * 1.5),
               engage_img, bg_colors[status], 1.0);
  }

  // dm icon
  if (!hideDM) {
    drawIcon(p, radius / 2 + (bdr_s * 2), rect().bottom() - footer_h / 2,
             dm_img, QColor(0, 0, 0, 70), dmActive ? 1.0 : 0.2);
  }

  // Right Dev UI 
  QRect rc2(rect().right() - (bdr_s * 2),  rect().bottom() - footer_h / 2, 184, 202);
  if (showDebugUI) {
    if (devUiEnabled == 1) {
      drawRightDevUi(p, rect().right() - 184 - bdr_s * 2, rect().bottom() - footer_h / 2 - 184 - bdr_s * 3 - rc2.height());
      drawRightDevUiBorder(p, rect().right() - 184 - bdr_s * 2, rect().bottom() - footer_h / 2 - 184 - bdr_s * 3 - rc2.height());
    } else if (devUiEnabled == 2) {
      drawRightDevUi(p, rect().right() - 184 - bdr_s * 2, rect().bottom() - footer_h / 2 - 184 - bdr_s * 3 - rc2.height());
      drawRightDevUi2(p, rect().right() - 184 - bdr_s * 2 - 184, rect().bottom() - footer_h / 2 - 184 - bdr_s * 3 - rc2.height());
      drawRightDevUiBorder(p, rect().right() - 184 - bdr_s * 2 - 184, rect().bottom() - footer_h / 2 - 184 - bdr_s * 3 - rc2.height());
    }
  }
  p.restore();
}

void NvgWindow::drawText(QPainter &p, int x, int y, const QString &text, int alpha) {
  QFontMetrics fm(p.font());
  QRect init_rect = fm.boundingRect(text);
  QRect real_rect = fm.boundingRect(init_rect, 0, text);
  real_rect.moveCenter({x, y - real_rect.height() / 2});

  p.setPen(QColor(0xff, 0xff, 0xff, alpha));
  p.drawText(real_rect.x(), real_rect.bottom(), text);
}

void OnroadHud::drawSpeedText(QPainter &p, int x, int y, const QString &text, QColor color) {
  QFontMetrics fm(p.font());
  QRect init_rect = fm.boundingRect(text);
  QRect real_rect = fm.boundingRect(init_rect, 0, text);
  real_rect.moveCenter({x, y - real_rect.height() / 2});

  p.setPen(color);
  p.drawText(real_rect.x(), real_rect.bottom(), text);
}

void OnroadHud::drawCenteredText(QPainter &p, int x, int y, const QString &text, QColor color) {
  QFontMetrics fm(p.font());
  QRect init_rect = fm.boundingRect(text);
  QRect real_rect = fm.boundingRect(init_rect, 0, text);
  real_rect.moveCenter({x, y});

  p.setPen(color);
  p.drawText(real_rect, Qt::AlignCenter, text);
}

void NvgWindow::drawIcon(QPainter &p, int x, int y, QPixmap &img, QBrush bg, float opacity) {
  p.setPen(Qt::NoPen);
  p.setBrush(bg);
  p.drawEllipse(x - radius / 2, y - radius / 2, radius, radius);
  p.setOpacity(opacity);
  p.drawPixmap(x - img_size / 2, y - img_size / 2, img);
  p.setOpacity(1.0);
}

void OnroadHud::drawCircle(QPainter &p, int x, int y, int r, QBrush bg) {
  p.setPen(Qt::NoPen);
  p.setBrush(bg);
  p.drawEllipse(x - r, y - r, 2 * r, 2 * r);
}

void OnroadHud::drawColoredText(QPainter &p, int x, int y, const QString &text, QColor &color) {
  QFontMetrics fm(p.font());
  QRect init_rect = fm.boundingRect(text);
  QRect real_rect = fm.boundingRect(init_rect, 0, text);
  real_rect.moveCenter({x, y - real_rect.height() / 2});

  p.setPen(color);
  p.drawText(real_rect.x(), real_rect.bottom(), text);
}

int OnroadHud::drawDevUiElementRight(QPainter &p, int x, int y, const char* value, const char* label, const char* units, QColor &color) {
  configFont(p, "Open Sans", 30 * 2, "SemiBold");
  drawColoredText(p, x + 92, y + 80, QString(value), color);

  configFont(p, "Open Sans", 28, "Regular");
  drawText(p, x + 92, y + 80 + 42, QString(label), 255);

  if (strlen(units) > 0) {
    p.save();
    p.translate(x + 54 + 30 - 3 + 92, y + 37 + 25);
    p.rotate(-90);
    drawText(p, 0, 0, QString(units), 255);
    p.restore();
  }

  return 110;
}

int OnroadHud::drawDevUiElementLeft(QPainter &p, int x, int y, const char* value, const char* label, const char* units, QColor &color) {
  configFont(p, "Open Sans", 30 * 2, "SemiBold");
  drawColoredText(p, x + 92, y + 80, QString(value), color);

  configFont(p, "Open Sans", 28, "Regular");
  drawText(p, x + 92, y + 80 + 42, QString(label), 255);

  if (strlen(units) > 0) {
    p.save();
    p.translate(x + 11, y + 37 + 25);
    p.rotate(90);
    drawText(p, 0, 0, QString(units), 255);
    p.restore();
  }

  return 110;
}

void OnroadHud::drawRightDevUi(QPainter &p, int x, int y) {
  int rh = 5;
  int ry = y;

  // Add Relative Distance to Primary Lead Car
  // Unit: Meters
  if (true) {
    char val_str[16];
    char units_str[8];
    QColor valueColor = QColor(255, 255, 255, 255);

    if (lead_status) {
      // Orange if close, Red if very close
      if (lead_d_rel < 5) {
        valueColor = QColor(255, 0, 0, 255);
      } else if (lead_d_rel < 15) {
        valueColor = QColor(255, 188, 0, 255);
      }
      snprintf(val_str, sizeof(val_str), "%d", (int)lead_d_rel);
    } else {
      snprintf(val_str, sizeof(val_str), "-");
    }

    snprintf(units_str, sizeof(units_str), "m");

    rh += drawDevUiElementRight(p, x, ry, val_str, "REL DIST", units_str, valueColor);
    ry = y + rh;
  }

  // Add Relative Velocity vs Primary Lead Car
  // Unit: kph if metric, else mph
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

     if (lead_status) {
       // Red if approaching faster than 10mph
       // Orange if approaching (negative)
       if (lead_v_rel < -4.4704) {
        valueColor = QColor(255, 0, 0, 255);
       } else if (lead_v_rel < 0) {
         valueColor = QColor(255, 188, 0, 255);
       }

       if (speedUnit == "mph") {
         snprintf(val_str, sizeof(val_str), "%d", (int)(lead_v_rel * 2.236936)); //mph
       } else {
         snprintf(val_str, sizeof(val_str), "%d", (int)(lead_v_rel * 3.6)); //kph
       }
     } else {
       snprintf(val_str, sizeof(val_str), "-");
     }

    rh += drawDevUiElementRight(p, x, ry, val_str, "REL SPEED", speedUnit.toStdString().c_str(), valueColor);
    ry = y + rh;
  }

  // Add Real Steering Angle
  // Unit: Degrees
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);
    if (madsEnabled && !suspended) {
      valueColor = QColor(0, 255, 0, 255);
    } else {
      valueColor = QColor(255, 255, 255, 255);
    }

    // Red if large steering angle
    // Orange if moderate steering angle
    if (std::fabs(angleSteers) > 50) {
      valueColor = QColor(255, 0, 0, 255);
    } else if (std::fabs(angleSteers) > 30) {
      valueColor = QColor(255, 188, 0, 255);
    }

    snprintf(val_str, sizeof(val_str), "%.1f%s%s", angleSteers , "°", "");

    rh += drawDevUiElementRight(p, x, ry, val_str, "REAL STEER", "", valueColor);
    ry = y + rh;
  }

  // Add Desired Steering Angle
  // Unit: Degrees
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

    if (engageable) {
      // Red if large steering angle
      // Orange if moderate steering angle
      if (std::fabs(angleSteers) > 50) {
        valueColor = QColor(255, 0, 0, 255);
      } else if (std::fabs(angleSteers) > 30) {
        valueColor = QColor(255, 188, 0, 255);
      }

      snprintf(val_str, sizeof(val_str), "%.1f%s%s", steerAngleDesired, "°", "");
    } else {
      snprintf(val_str, sizeof(val_str), "-");
    }

    rh += drawDevUiElementRight(p, x, ry, val_str, "DESIR STEER", "", valueColor);
    ry = y + rh;
  }

  // Add Traveled Distance in Current Drive
  // Unit: Km if metric, else Miles
  if (true) {
    char val_str[16];
    char units_str[8];
    QColor valueColor = QColor(255, 255, 255, 255);

    //if (engageable) {
    int minute = (int)(openpilotActiveTime / 60);
    int second = (int)((openpilotActiveTime) - (minute * 60));

    snprintf(val_str, sizeof(val_str), "%01d:%02d", minute, second);
    //}

    if (!engageable)
      valueColor = QColor(255, 188, 0, 255); 

    rh += drawDevUiElementRight(p, x, ry, val_str, "ACTIVE TIME", units_str, valueColor);
    ry = y + rh;
  }

  rh += 25;
  p.setBrush(QColor(0, 0, 0, 0));
  QRect ldu(x, y, 184, rh);
  //p.drawRoundedRect(ldu, 20, 20);
}

void OnroadHud::drawRightDevUi2(QPainter &p, int x, int y) {
  int rh = 5;
  int ry = y;


  // Add Acceleration from Car
  // Unit: Meters per Second Squared
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

    snprintf(val_str, sizeof(val_str), "%.1f", aEgo);

    rh += drawDevUiElementLeft(p, x, ry, val_str, "ACCEL", "m/s²", valueColor);
    ry = y + rh;
  }

  // Add Velocity of Primary Lead Car
  // Unit: kph if metric, else mph
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

     if (lead_status) {
       if (speedUnit == "mph") {
         snprintf(val_str, sizeof(val_str), "%d", (int)((lead_v_rel + vEgo) * 2.236936)); //mph
       } else {
         snprintf(val_str, sizeof(val_str), "%d", (int)((lead_v_rel + vEgo) * 3.6)); //kph
       }
     } else {
       snprintf(val_str, sizeof(val_str), "-");
     }

    rh += drawDevUiElementLeft(p, x, ry, val_str, "LEAD SPD", speedUnit.toStdString().c_str(), valueColor);
    ry = y + rh;
  }

  // Add Steering Torque from Car EPS
  // Unit: Newton Meters
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

    snprintf(val_str, sizeof(val_str), "%.1f", std::fabs(steeringTorque));

    rh += drawDevUiElementLeft(p, x, ry, val_str, "EPS TRQ", "N·dm", valueColor);
    ry = y + rh;
  }

  // Add Bearing Degree and Direction from Car (Compass)
  // Unit: Meters
  if (true) {
    char val_str[16];
    char dir_str[8];
    QColor valueColor = QColor(255, 255, 255, 255);

    if (bearingAccuracyDeg != 180.00) {
      snprintf(val_str, sizeof(val_str), "%.0d%s%s", (int)bearingDeg, "°", "");
      if (((bearingDeg >= 337.5) && (bearingDeg <= 360)) || ((bearingDeg >= 0) && (bearingDeg <= 22.5))) {
        snprintf(dir_str, sizeof(dir_str), "N");
      } else if ((bearingDeg > 22.5) && (bearingDeg < 67.5)) {
        snprintf(dir_str, sizeof(dir_str), "NE");
      } else if ((bearingDeg >= 67.5) && (bearingDeg <= 112.5)) {
        snprintf(dir_str, sizeof(dir_str), "E");
      } else if ((bearingDeg > 112.5) && (bearingDeg < 157.5)) {
        snprintf(dir_str, sizeof(dir_str), "SE");
      } else if ((bearingDeg >= 157.5) && (bearingDeg <= 202.5)) {
        snprintf(dir_str, sizeof(dir_str), "S");
      } else if ((bearingDeg > 202.5) && (bearingDeg < 247.5)) {
        snprintf(dir_str, sizeof(dir_str), "SW");
      } else if ((bearingDeg >= 247.5) && (bearingDeg <= 292.5)) {
        snprintf(dir_str, sizeof(dir_str), "W");
      } else if ((bearingDeg > 292.5) && (bearingDeg < 337.5)) {
        snprintf(dir_str, sizeof(dir_str), "NW");
      }
    } else {
      snprintf(dir_str, sizeof(dir_str), "OFF");
      snprintf(val_str, sizeof(val_str), "-");
    }

    rh += drawDevUiElementLeft(p, x, ry, dir_str, val_str, "", valueColor);
    ry = y + rh;
  }

  // Add Altitude of Current Location
  // Unit: Meters
  if (true) {
    char val_str[16];
    QColor valueColor = QColor(255, 255, 255, 255);

    if (gpsAccuracy != 0.00) {
      snprintf(val_str, sizeof(val_str), "%.1f", altitude);
    } else {
      snprintf(val_str, sizeof(val_str), "-");
    }

    rh += drawDevUiElementLeft(p, x, ry, val_str, "ALTITUDE", "m", valueColor);
    ry = y + rh;
  }

  rh += 25;
  p.setBrush(QColor(0, 0, 0, 0));
  QRect ldu(x, y, 184, rh);
  //p.drawRoundedRect(ldu, 20, 20);
}

void OnroadHud::drawRightDevUiBorder(QPainter &p, int x, int y) {
  int rh = 580;
  int rw = 184;
  p.setPen(QPen(QColor(0xff, 0xff, 0xff, 100), 6));
  p.setBrush(QColor(0, 0, 0, 0));
  if (devUiEnabled == 2) {
    rw *= 2;
  }
  QRect ldu(x, y, rw, rh);
  p.setCompositionMode(QPainter::CompositionMode_DestinationOver);
  p.setBrush(QColor(0, 0, 0, 100));
  p.drawRoundedRect(ldu, 20, 20);
}


void NvgWindow::initializeGL() {
  CameraViewWidget::initializeGL();
  qInfo() << "OpenGL version:" << QString((const char*)glGetString(GL_VERSION));
  qInfo() << "OpenGL vendor:" << QString((const char*)glGetString(GL_VENDOR));
  qInfo() << "OpenGL renderer:" << QString((const char*)glGetString(GL_RENDERER));
  qInfo() << "OpenGL language version:" << QString((const char*)glGetString(GL_SHADING_LANGUAGE_VERSION));

  prev_draw_t = millis_since_boot();
  setBackgroundColor(bg_colors[STATUS_DISENGAGED]);
}

void NvgWindow::updateFrameMat(int w, int h) {
  CameraViewWidget::updateFrameMat(w, h);

  UIState *s = uiState();
  s->fb_w = w;
  s->fb_h = h;
  auto intrinsic_matrix = s->wide_camera ? ecam_intrinsic_matrix : fcam_intrinsic_matrix;
  float zoom = ZOOM / intrinsic_matrix.v[0];
  if (s->wide_camera) {
    zoom *= 0.5;
  }
  // Apply transformation such that video pixel coordinates match video
  // 1) Put (0, 0) in the middle of the video
  // 2) Apply same scaling as video
  // 3) Put (0, 0) in top left corner of video
  s->car_space_transform.reset();
  s->car_space_transform.translate(w / 2, h / 2 + y_offset)
      .scale(zoom, zoom)
      .translate(-intrinsic_matrix.v[2], -intrinsic_matrix.v[5]);
}

void NvgWindow::drawLaneLines(QPainter &painter, const UIState *s) {
  painter.save();

  const UIScene &scene = s->scene;
  // lanelines
  for (int i = 0; i < std::size(scene.lane_line_vertices); ++i) {
    painter.setBrush(QColor::fromRgbF(1.0, 1.0, 1.0, std::clamp<float>(scene.lane_line_probs[i], 0.0, 0.7)));
    painter.drawPolygon(scene.lane_line_vertices[i].v, scene.lane_line_vertices[i].cnt);
  }

  // road edges
  for (int i = 0; i < std::size(scene.road_edge_vertices); ++i) {
    painter.setBrush(QColor::fromRgbF(1.0, 0, 0, std::clamp<float>(1.0 - scene.road_edge_stds[i], 0.0, 1.0)));
    painter.drawPolygon(scene.road_edge_vertices[i].v, scene.road_edge_vertices[i].cnt);
  }

  // paint path
  QLinearGradient bg(0, height(), 0, height() / 4);
  if (scene.end_to_end) {
    const auto &orientation = (*s->sm)["modelV2"].getModelV2().getOrientation();
    float orientation_future = 0;
    if (orientation.getZ().size() > 16) {
      orientation_future = std::abs(orientation.getZ()[16]);  // 2.5 seconds
    }
    // straight: 112, in turns: 70
    float curve_hue = fmax(70, 112 - (orientation_future * 420));
    // FIXME: painter.drawPolygon can be slow if hue is not rounded
    curve_hue = int(curve_hue * 100 + 0.5) / 100;

    bg.setColorAt(0.0, QColor::fromHslF(148 / 360., 0.94, 0.51, 0.4));
    bg.setColorAt(0.75 / 1.5, QColor::fromHslF(curve_hue / 360., 1.0, 0.68, 0.35));
    bg.setColorAt(1.0, QColor::fromHslF(curve_hue / 360., 1.0, 0.68, 0.0));
  } else {
    bg.setColorAt(0, whiteColor());
    bg.setColorAt(1, whiteColor(0));
  }
  painter.setBrush(bg);
  painter.drawPolygon(scene.track_vertices.v, scene.track_vertices.cnt);

  painter.restore();
}

void NvgWindow::drawLead(QPainter &painter, const cereal::ModelDataV2::LeadDataV3::Reader &lead_data, const QPointF &vd) {
  painter.save();

  const float speedBuff = 10.;
  const float leadBuff = 40.;
  const float d_rel = lead_data.getX()[0];
  const float v_rel = lead_data.getV()[0];

  float fillAlpha = 0;
  if (d_rel < leadBuff) {
    fillAlpha = 255 * (1.0 - (d_rel / leadBuff));
    if (v_rel < 0) {
      fillAlpha += 255 * (-1 * (v_rel / speedBuff));
    }
    fillAlpha = (int)(fmin(fillAlpha, 255));
  }

  float sz = std::clamp((25 * 30) / (d_rel / 3 + 30), 15.0f, 30.0f) * 2.35;
  float x = std::clamp((float)vd.x(), 0.f, width() - sz / 2);
  float y = std::fmin(height() - sz * .6, (float)vd.y());

  float g_xo = sz / 5;
  float g_yo = sz / 10;

  QPointF glow[] = {{x + (sz * 1.35) + g_xo, y + sz + g_yo}, {x, y - g_yo}, {x - (sz * 1.35) - g_xo, y + sz + g_yo}};
  painter.setBrush(QColor(218, 202, 37, 255));
  painter.drawPolygon(glow, std::size(glow));

  // chevron
  QPointF chevron[] = {{x + (sz * 1.25), y + sz}, {x, y}, {x - (sz * 1.25), y + sz}};
  painter.setBrush(redColor(fillAlpha));
  painter.drawPolygon(chevron, std::size(chevron));

  painter.restore();
}

void NvgWindow::paintGL() {
  CameraViewWidget::paintGL();

  QPainter painter(this);
  painter.setRenderHint(QPainter::Antialiasing);
  painter.setPen(Qt::NoPen);

  UIState *s = uiState();
  if (s->worldObjectsVisible()) {

    drawLaneLines(painter, s);

    if (s->scene.longitudinal_control) {
      auto leads = (*s->sm)["modelV2"].getModelV2().getLeadsV3();
      if (leads[0].getProb() > .5) {
        drawLead(painter, leads[0], s->scene.lead_vertices[0]);
      }
      if (leads[1].getProb() > .5 && (std::abs(leads[1].getX()[0] - leads[0].getX()[0]) > 3.0)) {
        drawLead(painter, leads[1], s->scene.lead_vertices[1]);
      }
    }
  }

  drawHud(painter);

  double cur_draw_t = millis_since_boot();
  double dt = cur_draw_t - prev_draw_t;
  double fps = fps_filter.update(1. / dt * 1000);
  if (fps < 15) {
    LOGW("slow frame rate: %.2f fps", fps);
  }
  prev_draw_t = cur_draw_t;
}

void NvgWindow::showEvent(QShowEvent *event) {
  CameraViewWidget::showEvent(event);

  ui_update_params(uiState());
  prev_draw_t = millis_since_boot();
}
