#ifndef ANIMATIONS_H
#define ANIMATIONS_H

#include <TFT_eSPI.h>

// Listening animation: sound wave bars
void drawListeningAnim(TFT_eSprite &spr, int frame) {
  int baseX = 55;
  int baseY = 100;
  for (int i = 0; i < 3; i++) {
    int h = 8 + sin((frame * 0.3) + i * 1.5) * 8;
    int x = baseX + i * 8;
    spr.fillRect(x, baseY - h, 4, h * 2, ACCENT_COLOR);
  }
  // Right side too
  baseX = 320 - 55 - 24;
  for (int i = 0; i < 3; i++) {
    int h = 8 + sin((frame * 0.3) + i * 1.5 + 1.0) * 8;
    int x = baseX + i * 8;
    spr.fillRect(x, baseY - h, 4, h * 2, ACCENT_COLOR);
  }
}

// Thinking animation: cycling dots
void drawThinkingAnim(TFT_eSprite &spr, int frame) {
  int dotCount = (frame / 5) % 4;  // 0, 1, 2, 3 dots cycling
  int y = 170;
  for (int i = 0; i < dotCount; i++) {
    int x = FACE_CX - 12 + i * 12;
    spr.fillCircle(x, y, 3, FACE_COLOR);
  }
}

// Speaking animation: mouth open/close
void drawSpeakingMouth(TFT_eSprite &spr, int frame) {
  bool open = (frame / 4) % 2 == 0;
  if (open) {
    spr.drawEllipse(FACE_CX, MOUTH_Y, 14, 10, FACE_COLOR);
  } else {
    spr.drawEllipse(FACE_CX, MOUTH_Y, 14, 4, FACE_COLOR);
  }
}

#endif
