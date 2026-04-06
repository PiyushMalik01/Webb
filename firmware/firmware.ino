/*
  Webb Desk Bot — Tabbie Eyes + Serial Control
  ESP32 + ILI9341 TFT 240x320 (landscape 320x240)

  Keeps the full Tabbie-style animated eyes with eyebrows, blush,
  sparkles, tears, Z-particles. Adds serial command protocol so
  the Webb backend can control the mood, display text, notifications,
  and switch display modes.

  Serial commands (115200 baud, newline-terminated):
    FACE:<mood>     — IDLE|HAPPY|ANGRY|SLEEPY|SURPRISED|SAD|LOVE|SUS|FOCUS|LISTENING|THINKING|SPEAKING|REMINDER
    TEXT:<line>:<msg> — Set text line 1-4 (shown below eyes in FACE mode)
    NOTIFY:<msg>    — Show notification banner for 3s
    MODE:<mode>     — FACE|DASHBOARD|NOTIFY
    STATUS:<json>   — Update dashboard stats
    CLEAR           — Clear screen
    ANIM:<name>     — Alias for FACE (backward compat)

  Legacy: bare mood names (e.g. "HAPPY\n") also work.
*/

#include <SPI.h>
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite spr = TFT_eSprite(&tft);

// ── Display layout ──────────────────────────────────────────
#define SPR_W 320
#define SPR_H 120
#define SPR_Y  55

// ── Display modes ───────────────────────────────────────────
#define MODE_FACE      0
#define MODE_DASHBOARD 1
#define MODE_NOTIFY    2

int displayMode = MODE_FACE;

// ── Serial buffer ───────────────────────────────────────────
#define CMD_BUF_SIZE 256
char cmdBuf[CMD_BUF_SIZE];
int cmdIdx = 0;

// ── Text lines (shown below eyes) ───────────────────────────
char textLines[4][64] = {"", "", "", ""};

// ── Notify banner ───────────────────────────────────────────
char notifyMsg[128] = "";
unsigned long notifyEnd = 0;

// ── Dashboard stats ─────────────────────────────────────────
int dashTasks = 0;
char dashTimer[16] = "idle";
char dashReminder[32] = "none";

// ── Webb serial control flag ────────────────────────────────
bool webbControlled = false;  // True once first serial command arrives
unsigned long lastSerialCmd = 0;
#define SERIAL_TIMEOUT 30000  // Return to auto-mood after 30s of no commands

// ══════════════════════════════════════════════════════════════
//  TABBIE EYES ENGINE (preserved from original)
// ══════════════════════════════════════════════════════════════

// ── Eye state ───────────────────────────────────────────────
float lookX=0, lookY=0, lookTX=0, lookTY=0;

float leW=52, leH=48, leTW=52, leTH=48;
float leR=16, leTR=16, leSkew=0, leSkewT=0;

float reW=52, reH=48, reTW=52, reTH=48;
float reR=16, reTR=16, reSkew=0, reSkewT=0;

float eyeYOff=0, eyeYOffT=0, eyeGap=50, eyeGapT=50;

// Mouth
float moW=22, moTW=22;
float moCurve=2.5, moCurveT=2.5;
float moThick=2.5, moThickT=2.5;
float moY=38, moTY=38;

// Eyebrows
float browW=0, browTW=0;
float browH=4, browTH=4;
float browAngle=0, browAngleT=0;
float browY=-8, browTY=-8;

// Blush
float blushAlpha=0, blushAlphaT=0;

// Anger vein
float veinAlpha=0, veinAlphaT=0;

// Sparkles
float sparkAlpha=0, sparkAlphaT=0;

// Tears
float tearAlpha=0, tearAlphaT=0;
float tearY=0;

// Z particles
float zAlpha=0, zAlphaT=0;
float zY=0;

// Eye color
uint16_t eyeCol = TFT_WHITE;

// ── Moods ───────────────────────────────────────────────────
#define MOOD_NEUTRAL   0
#define MOOD_HAPPY     1
#define MOOD_ANGRY     2
#define MOOD_SLEEPY    3
#define MOOD_SURPRISED 4
#define MOOD_SAD       5
#define MOOD_LOVE      6
#define MOOD_SUS       7

int mood = MOOD_NEUTRAL;
int moodIdx = 0;
float mSpd = 0.15;

unsigned long nextMood=0, nextBlink=0, nextLook=0;
int phase=0;
unsigned long phaseStart=0;
int dblCnt=0;
bool booting=true;
float savLH, savRH, savLR, savRR;

int moodSeq[] = {0,1,0,2,0,3,0,4,0,5,0,6,0,7};
#define MSEQ_LEN 14

// ── Colors ──────────────────────────────────────────────────
uint16_t C_BLUSH, C_VEIN, C_SPARK, C_TEAR, C_BROW, C_Z;

// ── Helpers ─────────────────────────────────────────────────
float lerpf(float a, float b, float t) {
  if (t > 1.0) t = 1.0;
  return a + (b - a) * t;
}
unsigned long rr(unsigned long lo, unsigned long hi) {
  return lo + (esp_random() % (hi - lo + 1));
}

// ── Draw functions ──────────────────────────────────────────

void drawSkewRR(TFT_eSprite *s, int x, int y, int w, int h,
                int r, float skew, uint16_t col) {
  s->fillRoundRect(x, y, w, h, r, col);
  if (skew > 0.5 || skew < -0.5) {
    int sk = (int)skew;
    if (sk > 0)
      s->fillTriangle(x, y, x+w, y, x+w, y+sk, TFT_BLACK);
    else
      s->fillTriangle(x, y, x+w, y, x, y-sk, TFT_BLACK);
  }
}

void drawHappyEye(TFT_eSprite *s, int cx, int cy, int w, uint16_t col) {
  int r = w / 2;
  s->fillCircle(cx, cy + 4, r, col);
  s->fillCircle(cx, cy - r + 8, r + 4, TFT_BLACK);
}

void drawHeart(TFT_eSprite *s, int cx, int cy, int sz, uint16_t col) {
  int r = sz / 3;
  s->fillCircle(cx - r, cy - r/2, r, col);
  s->fillCircle(cx + r, cy - r/2, r, col);
  s->fillTriangle(cx - sz/2 - 2, cy, cx + sz/2 + 2, cy,
                   cx, cy + sz - 2, col);
}

void drawSmileArc(TFT_eSprite *s, int cx, int cy, float width,
                   float curve, float thick) {
  if (width < 4) return;
  int arcR = (int)(width * 0.6);
  int th = (int)(thick + 1.5);
  if (th < 2) th = 2;

  if (curve > 0.5) {
    int acy = cy - (int)(curve * 2.0);
    for (int t = 0; t < th; t++)
      s->drawCircle(cx, acy, arcR - t, TFT_WHITE);
    float endAngle = 0.45;
    int ex1 = cx - (int)(cosf(endAngle) * (float)(arcR - th/2));
    int ey1 = acy + (int)(sinf(endAngle) * (float)(arcR - th/2));
    int ex2 = cx + (int)(cosf(endAngle) * (float)(arcR - th/2));
    s->fillCircle(ex1, ey1, th/2, TFT_WHITE);
    s->fillCircle(ex2, ey1, th/2, TFT_WHITE);
    s->fillRect(cx - arcR - 3, acy - arcR - 3, arcR*2+6, arcR+3, TFT_BLACK);
  } else if (curve < -0.5) {
    int acy = cy + (int)(-curve * 2.0);
    for (int t = 0; t < th; t++)
      s->drawCircle(cx, acy, arcR - t, TFT_WHITE);
    float endAngle = 0.45;
    int ex1 = cx - (int)(cosf(endAngle) * (float)(arcR - th/2));
    int ey1 = acy - (int)(sinf(endAngle) * (float)(arcR - th/2));
    int ex2 = cx + (int)(cosf(endAngle) * (float)(arcR - th/2));
    s->fillCircle(ex1, ey1, th/2, TFT_WHITE);
    s->fillCircle(ex2, ey1, th/2, TFT_WHITE);
    s->fillRect(cx - arcR - 3, acy, arcR*2+6, arcR+3, TFT_BLACK);
  } else {
    int hw = (int)(width * 0.3);
    int hh = th / 2;
    if (hh < 1) hh = 1;
    s->fillRoundRect(cx - hw, cy - hh, hw*2, hh*2, hh, TFT_WHITE);
  }
}

void drawOMouth(TFT_eSprite *s, int cx, int cy, int sz) {
  s->fillCircle(cx, cy, sz, TFT_WHITE);
  s->fillCircle(cx, cy, sz - 4, TFT_BLACK);
}

void drawBrow(TFT_eSprite *s, int cx, int eyeTop, float w, float h,
              float angle, int isRight) {
  if (w < 3) return;
  int bw = (int)w;
  int bh = (int)h;
  if (bh < 3) bh = 3;
  int by = eyeTop + (int)browY;

  int innerDrop = (int)(angle * 0.6);
  int lx = cx - bw/2;
  int rx = cx + bw/2;
  int ly, ry;

  if (isRight) {
    ly = by + innerDrop;
    ry = by - innerDrop/3;
  } else {
    ly = by - innerDrop/3;
    ry = by + innerDrop;
  }

  for (int t = -bh/2; t <= bh/2; t++) {
    s->drawLine(lx, ly+t, rx, ry+t, C_BROW);
  }
  s->fillCircle(lx, ly, bh/2, C_BROW);
  s->fillCircle(rx, ry, bh/2, C_BROW);
}

void drawBlush(TFT_eSprite *s, int lCx, int rCx, int yCom) {
  if (blushAlpha < 0.05) return;
  int by = yCom + 18;
  int bx_off = 10;
  s->fillEllipse(lCx - bx_off, by, 12, 6, C_BLUSH);
  s->fillEllipse(rCx + bx_off, by, 12, 6, C_BLUSH);
}

void drawVein(TFT_eSprite *s, int rCx, int yCom) {
  if (veinAlpha < 0.05) return;
  int vx = rCx + 30;
  int vy = yCom - 30;
  int sz = 8;
  s->drawLine(vx-sz, vy-sz/2, vx+sz, vy+sz/2, C_VEIN);
  s->drawLine(vx-sz, vy+sz/2, vx+sz, vy-sz/2, C_VEIN);
  s->drawLine(vx-sz+1, vy-sz/2, vx+sz+1, vy+sz/2, C_VEIN);
  s->drawLine(vx-sz+1, vy+sz/2, vx+sz+1, vy-sz/2, C_VEIN);
  s->drawLine(vx, vy-sz/2, vx+sz, vy-sz/2, C_VEIN);
  s->drawLine(vx+sz, vy-sz/2, vx+sz, vy+sz/2, C_VEIN);
  s->drawLine(vx-sz, vy-sz/2, vx, vy-sz/2, C_VEIN);
  s->drawLine(vx-sz, vy-sz/2, vx-sz, vy+sz/2, C_VEIN);
}

void drawSparkles(TFT_eSprite *s, int cx, int cy) {
  if (sparkAlpha < 0.05) return;
  unsigned long t = millis() / 300;
  for (int i = 0; i < 4; i++) {
    float a = (float)(t + i * 90) * 0.0174f * 4.0f;
    int sx = cx + (int)(cosf(a) * 70) + (i % 2 ? 20 : -20);
    int sy = cy + (int)(sinf(a) * 25) - 15;
    if (sx < 2 || sx > SPR_W-2 || sy < 2 || sy > SPR_H-2) continue;
    s->drawFastHLine(sx-3, sy, 7, C_SPARK);
    s->drawFastVLine(sx, sy-3, 7, C_SPARK);
    s->drawPixel(sx-1, sy-1, C_SPARK);
    s->drawPixel(sx+1, sy-1, C_SPARK);
    s->drawPixel(sx-1, sy+1, C_SPARK);
    s->drawPixel(sx+1, sy+1, C_SPARK);
  }
}

void drawTears(TFT_eSprite *s, int lCx, int rCx, int yCom) {
  if (tearAlpha < 0.05) return;
  int ty = yCom + 20 + (int)tearY;
  s->fillCircle(lCx - 8, ty, 3, C_TEAR);
  s->fillTriangle(lCx - 8, ty - 5, lCx - 11, ty, lCx - 5, ty, C_TEAR);
  s->fillCircle(rCx + 8, ty, 3, C_TEAR);
  s->fillTriangle(rCx + 8, ty - 5, rCx + 5, ty, rCx + 11, ty, C_TEAR);
}

void drawZzz(TFT_eSprite *s, int rCx, int yCom) {
  if (zAlpha < 0.05) return;
  int bx = rCx + 35;
  int by = yCom - 20 - (int)zY;
  s->setTextColor(C_Z);
  s->setTextFont(2);
  s->drawString("Z", bx, by);
  s->setTextFont(1);
  s->drawString("z", bx + 10, by - 12);
  s->drawString("z", bx + 16, by - 20);
}

// ── Render ──────────────────────────────────────────────────

void render() {
  spr.fillSprite(TFT_BLACK);

  int cx = SPR_W / 2;
  int cy = 42 + (int)eyeYOff;
  int gap = (int)eyeGap;

  int lCx = cx - gap/2 - (int)(leW/2) + (int)lookX;
  int rCx = cx + gap/2 + (int)(reW/2) + (int)lookX;
  int yCom = cy + (int)lookY;

  drawBlush(&spr, lCx, rCx, yCom);

  if (mood == MOOD_HAPPY && leH > 14) {
    drawHappyEye(&spr, lCx, yCom, (int)leW, eyeCol);
    drawHappyEye(&spr, rCx, yCom, (int)reW, eyeCol);
  } else if (mood == MOOD_LOVE && leH > 14) {
    drawHeart(&spr, lCx, yCom, (int)(leW * 0.85), eyeCol);
    drawHeart(&spr, rCx, yCom, (int)(reW * 0.85), eyeCol);
  } else {
    int lx = lCx - (int)(leW/2);
    int ly = yCom - (int)(leH/2);
    int rx = rCx - (int)(reW/2);
    int ry = yCom - (int)(reH/2);
    drawSkewRR(&spr, lx, ly, (int)leW, (int)leH, (int)leR, leSkew, eyeCol);
    drawSkewRR(&spr, rx, ry, (int)reW, (int)reH, (int)reR, -reSkew, eyeCol);
  }

  if (browW > 3) {
    int leTop = yCom - (int)(leH/2);
    int reTop = yCom - (int)(reH/2);
    drawBrow(&spr, lCx, leTop, browW, browH, browAngle, 0);
    drawBrow(&spr, rCx, reTop, browW, browH, browAngle, 1);
  }

  int mouthCy = yCom + (int)moY;
  if (mood == MOOD_SURPRISED) {
    drawOMouth(&spr, cx + (int)lookX, mouthCy, 10);
  } else {
    drawSmileArc(&spr, cx + (int)lookX, mouthCy, moW, moCurve, moThick);
  }

  drawVein(&spr, rCx, yCom);
  drawSparkles(&spr, cx, cy);
  drawTears(&spr, lCx, rCx, yCom);
  drawZzz(&spr, rCx, yCom);

  spr.pushSprite(0, SPR_Y);
}

// ── Update interpolation ────────────────────────────────────

void updateAll() {
  float s = mSpd;
  float sf = s * 2.5;
  if (sf > 1.0) sf = 1.0;

  lookX = lerpf(lookX, lookTX, s);
  lookY = lerpf(lookY, lookTY, s);
  leW = lerpf(leW, leTW, sf);  leH = lerpf(leH, leTH, sf);
  leR = lerpf(leR, leTR, sf);  leSkew = lerpf(leSkew, leSkewT, s);
  reW = lerpf(reW, reTW, sf);  reH = lerpf(reH, reTH, sf);
  reR = lerpf(reR, reTR, sf);  reSkew = lerpf(reSkew, reSkewT, s);
  eyeYOff = lerpf(eyeYOff, eyeYOffT, s);
  eyeGap = lerpf(eyeGap, eyeGapT, s);
  moW = lerpf(moW, moTW, sf);
  moCurve = lerpf(moCurve, moCurveT, s * 0.7);
  moThick = lerpf(moThick, moThickT, sf);
  moY = lerpf(moY, moTY, s);
  browW = lerpf(browW, browTW, s * 1.5);
  browH = lerpf(browH, browTH, s);
  browAngle = lerpf(browAngle, browAngleT, s * 0.8);
  browY = lerpf(browY, browTY, s);
  blushAlpha = lerpf(blushAlpha, blushAlphaT, s);
  veinAlpha = lerpf(veinAlpha, veinAlphaT, s);
  sparkAlpha = lerpf(sparkAlpha, sparkAlphaT, s);
  tearAlpha = lerpf(tearAlpha, tearAlphaT, s);
  zAlpha = lerpf(zAlpha, zAlphaT, s * 0.3);

  if (tearAlpha > 0.1) {
    tearY += 0.4;
    if (tearY > 25) tearY = 0;
  } else { tearY = 0; }

  if (zAlpha > 0.1) {
    zY += 0.15;
    if (zY > 20) zY = 0;
  } else { zY = 0; }
}

// ── Mood targets ────────────────────────────────────────────

void clearExtras() {
  blushAlphaT=0; veinAlphaT=0; sparkAlphaT=0; tearAlphaT=0; zAlphaT=0;
  browTW=0;
  eyeCol = TFT_WHITE;
}

void setNeutral() {
  leTW=reTW=52; leTH=reTH=48;
  leTR=reTR=16; leSkewT=reSkewT=0;
  eyeYOffT=0; eyeGapT=50;
  moTW=22; moCurveT=2.5; moThickT=2.5; moTY=40;
  browTW=28; browAngleT=0; browTY=-10; browTH=3;
  C_BROW = tft.color565(180, 180, 180);
  clearExtras();
  mSpd=0.18;
}

void setMoodTargets(int m) {
  mood = m;
  setNeutral();

  switch (m) {
    case MOOD_HAPPY:
      leTW=reTW=56; leTH=reTH=40; leTR=reTR=20;
      moTW=32; moCurveT=7; moThickT=3; moTY=36;
      browTW=32; browTH=3; browAngleT=-4; browTY=-14;
      blushAlphaT=1; sparkAlphaT=1;
      eyeCol = tft.color565(255, 240, 200);
      C_BROW = tft.color565(255, 220, 140);
      mSpd=0.22;
      break;
    case MOOD_ANGRY:
      leTW=reTW=54; leTH=reTH=30; leTR=reTR=8;
      leSkewT=reSkewT=14; eyeGapT=36;
      moTW=18; moCurveT=-4; moThickT=3; moTY=34;
      browTW=42; browTH=5; browAngleT=14; browTY=-12;
      veinAlphaT=1;
      eyeCol = tft.color565(255, 180, 180);
      C_BROW = tft.color565(255, 80, 60);
      mSpd=0.28;
      break;
    case MOOD_SLEEPY:
      leTW=reTW=54; leTH=reTH=10; leTR=reTR=5;
      eyeYOffT=5;
      moTW=16; moCurveT=0; moThickT=2; moTY=30;
      browTW=30; browTH=3; browAngleT=-3; browTY=-6;
      zAlphaT=1;
      eyeCol = tft.color565(200, 210, 255);
      C_BROW = tft.color565(140, 150, 200);
      mSpd=0.05;
      break;
    case MOOD_SURPRISED:
      leTW=reTW=56; leTH=reTH=58; leTR=reTR=26;
      eyeYOffT=-4; eyeGapT=56;
      moTW=18; moCurveT=0; moThickT=3; moTY=42;
      browTW=38; browTH=4; browAngleT=-8; browTY=-18;
      eyeCol = tft.color565(220, 255, 255);
      C_BROW = tft.color565(180, 255, 255);
      mSpd=0.35;
      break;
    case MOOD_SAD:
      leTW=reTW=48; leTH=reTH=38; leTR=reTR=14;
      leSkewT=reSkewT=-10; eyeYOffT=5;
      moTW=20; moCurveT=-5; moThickT=2.5; moTY=36;
      browTW=34; browTH=4; browAngleT=-12; browTY=-10;
      tearAlphaT=1;
      eyeCol = tft.color565(180, 200, 255);
      C_BROW = tft.color565(100, 140, 255);
      mSpd=0.07;
      break;
    case MOOD_LOVE:
      leTW=reTW=50; leTH=reTH=48; leTR=reTR=22;
      moTW=28; moCurveT=6; moThickT=2.5; moTY=38;
      browTW=30; browTH=3; browAngleT=-5; browTY=-14;
      blushAlphaT=1; sparkAlphaT=1;
      eyeCol = tft.color565(255, 200, 220);
      C_BROW = tft.color565(255, 150, 180);
      mSpd=0.1;
      break;
    case MOOD_SUS:
      leTW=48; leTH=20; reTW=54; reTH=50;
      leTR=8; reTR=18;
      leSkewT=8; reSkewT=-4;
      moTW=14; moCurveT=-1; moThickT=2; moTY=36;
      browTW=34; browTH=4; browAngleT=8; browTY=-10;
      eyeCol = tft.color565(255, 255, 200);
      C_BROW = tft.color565(255, 200, 60);
      mSpd=0.12;
      break;
  }
}

// ── Blink helpers ───────────────────────────────────────────

void saveLids() { savLH=leTH; savRH=reTH; savLR=leTR; savRR=reTR; }
void restoreLids() { leTH=savLH; reTH=savRH; leTR=savLR; reTR=savRR; }
void closeLids() { saveLids(); leTH=reTH=3; leTR=reTR=2; }

// ══════════════════════════════════════════════════════════════
//  WEBB SERIAL PROTOCOL
// ══════════════════════════════════════════════════════════════

// Map Webb face names to Tabbie moods
int webbFaceToMood(String face) {
  face.toUpperCase();
  face.trim();
  if (face == "IDLE")       return MOOD_NEUTRAL;
  if (face == "HAPPY")      return MOOD_HAPPY;
  if (face == "FOCUS")      return MOOD_ANGRY;     // Intense/focused → angry eyes (squinting)
  if (face == "SLEEPY")     return MOOD_SLEEPY;
  if (face == "REMINDER")   return MOOD_SURPRISED;  // Alert → surprised
  if (face == "LISTENING")  return MOOD_SURPRISED;  // Attentive → wide eyes
  if (face == "SURPRISED")  return MOOD_SURPRISED;
  if (face == "THINKING")   return MOOD_SUS;        // Contemplative → one-eye-bigger
  if (face == "SPEAKING")   return MOOD_HAPPY;      // Talking → happy/engaged
  if (face == "ANGRY")      return MOOD_ANGRY;
  if (face == "SAD")        return MOOD_SAD;
  if (face == "LOVE")       return MOOD_LOVE;
  if (face == "SUS")        return MOOD_SUS;
  return MOOD_NEUTRAL;
}

void handleSerialCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  webbControlled = true;
  lastSerialCmd = millis();

  // Parse COMMAND:PAYLOAD or bare face name
  int colonIdx = line.indexOf(':');
  String cmdType, payload;

  if (colonIdx < 0) {
    // Legacy: bare face name
    cmdType = "FACE";
    payload = line;
  } else {
    cmdType = line.substring(0, colonIdx);
    payload = line.substring(colonIdx + 1);
    cmdType.toUpperCase();
    payload.trim();
  }

  if (cmdType == "FACE" || cmdType == "ANIM") {
    int newMood = webbFaceToMood(payload);
    setMoodTargets(newMood);
    lookTX = lookTY = 0;
    Serial.println("OK:" + payload);
  }
  else if (cmdType == "TEXT") {
    int c2 = payload.indexOf(':');
    if (c2 > 0) {
      int lineNum = payload.substring(0, c2).toInt() - 1;
      if (lineNum >= 0 && lineNum < 4) {
        payload.substring(c2 + 1).toCharArray(textLines[lineNum], 64);
      }
    }
    Serial.println("OK:TEXT");
  }
  else if (cmdType == "NOTIFY") {
    payload.toCharArray(notifyMsg, 128);
    notifyEnd = millis() + 3000;
    displayMode = MODE_NOTIFY;
    Serial.println("OK:NOTIFY");
  }
  else if (cmdType == "MODE") {
    payload.toUpperCase();
    if (payload == "DASHBOARD") displayMode = MODE_DASHBOARD;
    else if (payload == "NOTIFY") displayMode = MODE_NOTIFY;
    else displayMode = MODE_FACE;
    Serial.println("OK:MODE:" + payload);
  }
  else if (cmdType == "STATUS") {
    // Simple parsing for dashboard stats
    if (payload.indexOf("tasks") >= 0) {
      int idx = payload.indexOf("tasks");
      int c2 = payload.indexOf(':', idx);
      if (c2 > 0) dashTasks = payload.substring(c2 + 1).toInt();
    }
    Serial.println("OK:STATUS");
  }
  else if (cmdType == "CLEAR") {
    tft.fillScreen(TFT_BLACK);
    Serial.println("OK:CLEAR");
  }
  else {
    Serial.println("ERR:UNKNOWN:" + cmdType);
  }
}

void processSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdIdx > 0) {
        cmdBuf[cmdIdx] = '\0';
        handleSerialCommand(String(cmdBuf));
        cmdIdx = 0;
      }
    } else if (cmdIdx < CMD_BUF_SIZE - 1) {
      cmdBuf[cmdIdx++] = c;
    }
  }
}

// ── Draw text below eyes ────────────────────────────────────

void drawTextOverlay() {
  if (strlen(textLines[0]) == 0) return;
  tft.setTextColor(tft.color565(160, 160, 160), TFT_BLACK);
  tft.setTextFont(2);
  tft.setTextDatum(TC_DATUM);
  tft.drawString(textLines[0], 160, 200);
}

// ── Draw notify banner ──────────────────────────────────────

void drawNotifyOverlay() {
  if (strlen(notifyMsg) == 0) return;
  tft.fillRect(0, 200, 320, 40, tft.color565(30, 30, 30));
  tft.drawLine(0, 200, 320, 200, tft.color565(80, 80, 80));
  tft.setTextColor(TFT_WHITE, tft.color565(30, 30, 30));
  tft.setTextFont(2);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(notifyMsg, 160, 220);
}

// ── Draw dashboard below eyes ───────────────────────────────

void drawDashboardOverlay() {
  tft.fillRect(0, 185, 320, 55, TFT_BLACK);
  tft.drawLine(20, 188, 300, 188, tft.color565(60, 60, 60));

  tft.setTextColor(tft.color565(160, 160, 160), TFT_BLACK);
  tft.setTextFont(2);
  tft.setTextDatum(TL_DATUM);

  char buf[64];
  snprintf(buf, sizeof(buf), "Tasks: %d", dashTasks);
  tft.drawString(buf, 25, 195);

  snprintf(buf, sizeof(buf), "Timer: %s", dashTimer);
  tft.drawString(buf, 170, 195);

  snprintf(buf, sizeof(buf), "Next: %s", dashReminder);
  tft.drawString(buf, 25, 218);
}

// ── Tick (auto-behavior) ────────────────────────────────────

void tick() {
  unsigned long now = millis();

  // If Webb is controlling, don't auto-cycle moods
  // But if no command for 30s, go back to auto-demo
  if (webbControlled && (now - lastSerialCmd < SERIAL_TIMEOUT)) {
    // Webb-controlled: only do blinks and eye movement, no mood changes
  } else {
    // Auto-demo mode: cycle through moods
    if (webbControlled && (now - lastSerialCmd >= SERIAL_TIMEOUT)) {
      webbControlled = false;  // Return to auto
    }
    if (now >= nextMood) {
      moodIdx = (moodIdx + 1) % MSEQ_LEN;
      setMoodTargets(moodSeq[moodIdx]);
      lookTX = lookTY = 0;
      nextMood = now + (mood == MOOD_NEUTRAL ? rr(2500,4000) : rr(4500,7500));
    }
  }

  // Blink and eye movement (always active)
  unsigned long elapsed = now - phaseStart;

  switch (phase) {
    case 0:
      if (now >= nextBlink) {
        int r = esp_random() % 100;
        if (r < 15) { phase=4; phaseStart=now; dblCnt=0; closeLids(); }
        else if (r < 25 && mood!=MOOD_ANGRY && mood!=MOOD_SAD) {
          phase=3; phaseStart=now; saveLids();
          if (esp_random()&1) leTH=3; else reTH=3;
        } else { phase=2; phaseStart=now; closeLids(); }
      } else if (now >= nextLook) {
        phase=1; phaseStart=now;
        float range = 28.0;
        if (mood==MOOD_SLEEPY) range=8.0;
        if (mood==MOOD_SURPRISED) range=35.0;
        lookTX = ((float)(esp_random()%200)-100.0)/100.0 * range;
        lookTY = ((float)(esp_random()%100)-50.0)/100.0 * 8.0;
      }
      break;
    case 1:
      if (elapsed>500) {
        if (esp_random()%3!=0) { lookTX=0; lookTY=0; }
        phase=0; nextLook=now+rr(600,2200);
      }
      break;
    case 2:
      if (elapsed>120) { restoreLids(); phase=0; nextBlink=now+rr(2000,5000); }
      break;
    case 3:
      if (elapsed>280) { restoreLids(); phase=0; nextBlink=now+rr(2500,5000); }
      break;
    case 4:
      if (dblCnt==0 && elapsed>90) { restoreLids(); dblCnt=1; phaseStart=now; }
      else if (dblCnt==1 && elapsed>70) { closeLids(); dblCnt=2; phaseStart=now; }
      else if (dblCnt==2 && elapsed>90) { restoreLids(); phase=0; nextBlink=now+rr(2500,5000); }
      break;
  }

  if (phase==0) {
    if (mood==MOOD_SLEEPY && esp_random()%80==0)
      lookTY = ((float)(esp_random()%60)-30.0)/30.0*3.0;
    if (mood==MOOD_SURPRISED && esp_random()%25==0)
      lookTX = ((float)(esp_random()%200)-100.0)/100.0*30.0;
    if (mood==MOOD_SUS && esp_random()%100==0)
      lookTX = ((float)(esp_random()%200)-100.0)/100.0*20.0;
  }
}

// ══════════════════════════════════════════════════════════════
//  SETUP & LOOP
// ══════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Webb Desk Bot ===");

  C_BLUSH = tft.color565(255, 100, 120);
  C_VEIN  = tft.color565(255, 60, 40);
  C_SPARK = tft.color565(255, 255, 100);
  C_TEAR  = tft.color565(100, 180, 255);
  C_BROW  = TFT_WHITE;
  C_Z     = tft.color565(150, 180, 255);

  tft.init();
  tft.invertDisplay(true);
  tft.setRotation(1);

  tft.startWrite();
  tft.writecommand(0x2A);
  tft.writedata(0x00); tft.writedata(0x00);
  tft.writedata(0x01); tft.writedata(0x3F);
  tft.writecommand(0x2B);
  tft.writedata(0x00); tft.writedata(0x00);
  tft.writedata(0x00); tft.writedata(0xEF);
  tft.endWrite();

  tft.fillScreen(TFT_BLACK);

  void *p = spr.createSprite(SPR_W, SPR_H);
  Serial.printf("Sprite: %s, heap: %d\n", p ? "OK" : "FAIL", ESP.getFreeHeap());

  leH=reH=0; leW=reW=52; moW=0;
  booting=true; mSpd=0.04;

  unsigned long now = millis();
  nextBlink=now+4500; nextLook=now+3500; nextMood=now+8000;

  Serial.println("OK:READY");
}

void loop() {
  // Always check serial
  processSerial();

  // Check if notify expired
  if (displayMode == MODE_NOTIFY && millis() >= notifyEnd) {
    displayMode = MODE_FACE;
    notifyMsg[0] = '\0';
    tft.fillRect(0, 200, 320, 40, TFT_BLACK);
  }

  if (booting) {
    leTH=reTH=48; leTR=reTR=16; leTW=reTW=52;
    moTW=22; moCurveT=2.5; moThickT=2.5; moTY=38;
    updateAll();
    render();
    delay(30);
    if (leH > 46) {
      booting=false;
      setMoodTargets(MOOD_NEUTRAL);
      mSpd=0.18;
      Serial.println("OK:AWAKE");
    }
    return;
  }

  tick();
  updateAll();
  render();

  // Draw overlays on the TFT directly (outside sprite area)
  switch (displayMode) {
    case MODE_DASHBOARD:
      drawDashboardOverlay();
      break;
    case MODE_NOTIFY:
      drawNotifyOverlay();
      break;
    case MODE_FACE:
    default:
      drawTextOverlay();
      break;
  }

  delay(16);
}
