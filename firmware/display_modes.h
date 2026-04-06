#ifndef DISPLAY_MODES_H
#define DISPLAY_MODES_H

#include <TFT_eSPI.h>

enum DisplayMode {
  MODE_FACE,
  MODE_DASHBOARD,
  MODE_NOTIFY
};

// Status info for dashboard mode
struct StatusInfo {
  int taskCount;
  char timerText[16];
  char reminderText[32];
  char timeText[16];
};

void drawDashboardMode(TFT_eSprite &spr, FaceType face, bool blinking, StatusInfo &info) {
  spr.fillSprite(BG_COLOR);

  // Left half: smaller face area (just eyes and mouth, no outline)
  int eyeY = 60;
  int mouthY = 90;
  int leftEyeX = 90;
  int rightEyeX = 150;

  if (blinking) {
    spr.drawLine(leftEyeX - 8, eyeY, leftEyeX + 8, eyeY, FACE_COLOR);
    spr.drawLine(rightEyeX - 8, eyeY, rightEyeX + 8, eyeY, FACE_COLOR);
  } else {
    spr.drawCircle(leftEyeX, eyeY, 8, FACE_COLOR);
    spr.drawCircle(rightEyeX, eyeY, 8, FACE_COLOR);
  }
  spr.drawLine(FACE_CX - 14, mouthY, FACE_CX + 14, mouthY, FACE_COLOR);

  // Divider line
  spr.drawLine(20, 120, 300, 120, ACCENT_COLOR);

  // Bottom half: status info
  spr.setTextColor(TEXT_COLOR);
  spr.setTextSize(1);

  spr.setFreeFont(&FreeSans9pt7b);

  // Tasks
  char buf[64];
  snprintf(buf, sizeof(buf), "Tasks: %d active", info.taskCount);
  spr.drawString(buf, 30, 135);

  // Timer
  snprintf(buf, sizeof(buf), "Timer: %s", info.timerText);
  spr.drawString(buf, 30, 160);

  // Reminder
  snprintf(buf, sizeof(buf), "Next: %s", info.reminderText);
  spr.drawString(buf, 30, 185);

  // Time
  spr.setTextColor(FACE_COLOR);
  spr.drawString(info.timeText, 30, 215);
}

void drawNotifyBanner(TFT_eSprite &spr, const char *message) {
  // Draw notification banner at bottom 60px
  int bannerY = 180;
  spr.fillRect(0, bannerY, 320, 60, NOTIFY_BG);
  spr.drawLine(0, bannerY, 320, bannerY, ACCENT_COLOR);

  spr.setTextColor(FACE_COLOR);
  spr.setTextSize(1);
  spr.setFreeFont(&FreeSans9pt7b);
  spr.drawString(message, 15, bannerY + 20);
}

DisplayMode parseMode(const String &name) {
  if (name == "DASHBOARD") return MODE_DASHBOARD;
  if (name == "NOTIFY") return MODE_NOTIFY;
  return MODE_FACE;
}

#endif
