#ifndef FACES_H
#define FACES_H

#include <TFT_eSPI.h>

enum FaceType {
  FACE_IDLE,
  FACE_HAPPY,
  FACE_FOCUS,
  FACE_SLEEPY,
  FACE_REMINDER,
  FACE_LISTENING,
  FACE_SURPRISED,
  FACE_THINKING,
  FACE_SPEAKING
};

void drawFace(TFT_eSprite &spr, FaceType face, bool blinking) {
  // Clear sprite
  spr.fillSprite(BG_COLOR);

  // Face outline (rounded rect)
  spr.drawRoundRect(FACE_RECT_X, FACE_RECT_Y, FACE_RECT_W, FACE_RECT_H, FACE_RECT_R, ACCENT_COLOR);

  // Draw eyes based on face type
  if (blinking) {
    // Blink: horizontal lines
    spr.drawLine(EYE_LEFT_X - 10, EYE_Y, EYE_LEFT_X + 10, EYE_Y, FACE_COLOR);
    spr.drawLine(EYE_RIGHT_X - 10, EYE_Y, EYE_RIGHT_X + 10, EYE_Y, FACE_COLOR);
  } else {
    switch (face) {
      case FACE_HAPPY:
        // Happy: curved arcs (upside-down U)
        for (int i = -10; i <= 10; i++) {
          int y = EYE_Y - abs(i) * 6 / 10;
          spr.drawPixel(EYE_LEFT_X + i, y, FACE_COLOR);
          spr.drawPixel(EYE_LEFT_X + i, y + 1, FACE_COLOR);
          spr.drawPixel(EYE_RIGHT_X + i, y, FACE_COLOR);
          spr.drawPixel(EYE_RIGHT_X + i, y + 1, FACE_COLOR);
        }
        break;
      case FACE_FOCUS:
        // Narrow squinting lines
        spr.drawLine(EYE_LEFT_X - 12, EYE_Y + 2, EYE_LEFT_X + 12, EYE_Y - 2, FACE_COLOR);
        spr.drawLine(EYE_LEFT_X - 12, EYE_Y + 3, EYE_LEFT_X + 12, EYE_Y - 1, FACE_COLOR);
        spr.drawLine(EYE_RIGHT_X - 12, EYE_Y - 2, EYE_RIGHT_X + 12, EYE_Y + 2, FACE_COLOR);
        spr.drawLine(EYE_RIGHT_X - 12, EYE_Y - 1, EYE_RIGHT_X + 12, EYE_Y + 3, FACE_COLOR);
        break;
      case FACE_SLEEPY:
        // Half-closed curved
        for (int i = -10; i <= 10; i++) {
          int y = EYE_Y + abs(i) * 3 / 10;
          spr.drawPixel(EYE_LEFT_X + i, y, FACE_COLOR);
          spr.drawPixel(EYE_RIGHT_X + i, y, FACE_COLOR);
        }
        break;
      case FACE_SURPRISED:
      case FACE_LISTENING:
        // Big circles
        spr.drawCircle(EYE_LEFT_X, EYE_Y, EYE_RADIUS + 4, FACE_COLOR);
        spr.drawCircle(EYE_LEFT_X, EYE_Y, EYE_RADIUS + 3, FACE_COLOR);
        spr.drawCircle(EYE_RIGHT_X, EYE_Y, EYE_RADIUS + 4, FACE_COLOR);
        spr.drawCircle(EYE_RIGHT_X, EYE_Y, EYE_RADIUS + 3, FACE_COLOR);
        break;
      case FACE_THINKING:
        // Normal eyes, looking up-right
        spr.drawCircle(EYE_LEFT_X + 3, EYE_Y - 3, EYE_RADIUS, FACE_COLOR);
        spr.drawCircle(EYE_RIGHT_X + 3, EYE_Y - 3, EYE_RADIUS, FACE_COLOR);
        break;
      default:
        // Normal round eyes (IDLE, SPEAKING, REMINDER)
        spr.drawCircle(EYE_LEFT_X, EYE_Y, EYE_RADIUS, FACE_COLOR);
        spr.drawCircle(EYE_RIGHT_X, EYE_Y, EYE_RADIUS, FACE_COLOR);
        break;
    }
  }

  // Draw mouth based on face type
  switch (face) {
    case FACE_HAPPY:
      // Smile curve
      for (int i = -20; i <= 20; i++) {
        int y = MOUTH_Y + (i * i) / 40;
        spr.drawPixel(FACE_CX + i, y, FACE_COLOR);
        spr.drawPixel(FACE_CX + i, y + 1, FACE_COLOR);
      }
      break;
    case FACE_SURPRISED:
      // O shape
      spr.drawCircle(FACE_CX, MOUTH_Y, 10, FACE_COLOR);
      spr.drawCircle(FACE_CX, MOUTH_Y, 9, FACE_COLOR);
      break;
    case FACE_SPEAKING:
      // Open ellipse (animates externally)
      spr.drawEllipse(FACE_CX, MOUTH_Y, 14, 8, FACE_COLOR);
      break;
    case FACE_SLEEPY:
      // Slight frown
      for (int i = -15; i <= 15; i++) {
        int y = MOUTH_Y - (i * i) / 60;
        spr.drawPixel(FACE_CX + i, y, FACE_COLOR);
      }
      break;
    case FACE_REMINDER:
      // Wavy
      for (int i = -18; i <= 18; i++) {
        int y = MOUTH_Y + sin(i * 0.3) * 4;
        spr.drawPixel(FACE_CX + i, y, FACE_COLOR);
      }
      break;
    default:
      // Neutral line
      spr.drawLine(FACE_CX - 18, MOUTH_Y, FACE_CX + 18, MOUTH_Y, FACE_COLOR);
      spr.drawLine(FACE_CX - 18, MOUTH_Y + 1, FACE_CX + 18, MOUTH_Y + 1, FACE_COLOR);
      break;
  }
}

FaceType parseFace(const String &name) {
  if (name == "HAPPY") return FACE_HAPPY;
  if (name == "FOCUS") return FACE_FOCUS;
  if (name == "SLEEPY") return FACE_SLEEPY;
  if (name == "REMINDER") return FACE_REMINDER;
  if (name == "LISTENING") return FACE_LISTENING;
  if (name == "SURPRISED") return FACE_SURPRISED;
  if (name == "THINKING") return FACE_THINKING;
  if (name == "SPEAKING") return FACE_SPEAKING;
  return FACE_IDLE;
}

#endif
