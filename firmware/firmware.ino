#include <TFT_eSPI.h>
#include <SPI.h>

#include "config.h"
#include "faces.h"
#include "animations.h"
#include "serial_protocol.h"
#include "display_modes.h"

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite sprite = TFT_eSprite(&tft);

// State
FaceType currentFace = FACE_IDLE;
DisplayMode currentMode = MODE_FACE;
bool needsRedraw = true;
int animFrame = 0;

// Blink state
unsigned long nextBlinkTime = 0;
bool isBlinking = false;
unsigned long blinkEndTime = 0;

// Notify state
char notifyMessage[128] = "";
unsigned long notifyEndTime = 0;

// Text lines
char textLines[4][64] = {"", "", "", ""};

// Status info
StatusInfo statusInfo = {0, "idle", "none", ""};

// Serial buffer
char cmdBuffer[CMD_BUFFER_SIZE];
int cmdIdx = 0;

void setup() {
  Serial.begin(SERIAL_BAUD);

  tft.init();
  tft.setRotation(1);  // Landscape: 320x240
  tft.fillScreen(BG_COLOR);

  // Create sprite (full screen buffer for landscape)
  sprite.createSprite(320, 240);
  sprite.setSwapBytes(true);

  // Schedule first blink
  nextBlinkTime = millis() + random(BLINK_MIN_MS, BLINK_MAX_MS);

  Serial.println("OK:READY");
}

void processSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdIdx > 0) {
        cmdBuffer[cmdIdx] = '\0';
        String line = String(cmdBuffer);
        handleCommand(line);
        cmdIdx = 0;
      }
    } else if (cmdIdx < CMD_BUFFER_SIZE - 1) {
      cmdBuffer[cmdIdx++] = c;
    }
  }
}

void handleCommand(const String &line) {
  Command cmd;
  if (!parseCommand(line, cmd)) return;

  if (cmd.type == "FACE") {
    currentFace = parseFace(cmd.payload);
    needsRedraw = true;
    Serial.println("OK:" + cmd.payload);
  }
  else if (cmd.type == "MODE") {
    currentMode = parseMode(cmd.payload);
    needsRedraw = true;
    Serial.println("OK:MODE:" + cmd.payload);
  }
  else if (cmd.type == "TEXT") {
    int colonIdx = cmd.payload.indexOf(':');
    if (colonIdx > 0) {
      int lineNum = cmd.payload.substring(0, colonIdx).toInt() - 1;
      if (lineNum >= 0 && lineNum < 4) {
        String content = cmd.payload.substring(colonIdx + 1);
        content.toCharArray(textLines[lineNum], 64);
        needsRedraw = true;
      }
    }
    Serial.println("OK:TEXT");
  }
  else if (cmd.type == "NOTIFY") {
    cmd.payload.toCharArray(notifyMessage, 128);
    notifyEndTime = millis() + 3000;
    currentMode = MODE_NOTIFY;
    needsRedraw = true;
    Serial.println("OK:NOTIFY");
  }
  else if (cmd.type == "CLEAR") {
    sprite.fillSprite(BG_COLOR);
    sprite.pushSprite(0, 0);
    Serial.println("OK:CLEAR");
  }
  else if (cmd.type == "ANIM") {
    // Animation commands just set the face type (animations are auto-drawn)
    currentFace = parseFace(cmd.payload);
    needsRedraw = true;
    Serial.println("OK:ANIM:" + cmd.payload);
  }
  else if (cmd.type == "BRIGHTNESS") {
    int val = cmd.payload.toInt();
    // TFT_eSPI doesn't have direct backlight control; depends on hardware
    // If backlight pin is connected, use analogWrite
    Serial.println("OK:BRIGHTNESS:" + cmd.payload);
  }
  else if (cmd.type == "STATUS") {
    // Parse JSON-like status: {"tasks":3,"timer":"12:30"}
    // Simple parsing for key fields
    if (cmd.payload.indexOf("tasks") >= 0) {
      int idx = cmd.payload.indexOf("tasks");
      int colon = cmd.payload.indexOf(':', idx);
      if (colon > 0) {
        statusInfo.taskCount = cmd.payload.substring(colon + 1).toInt();
      }
    }
    needsRedraw = true;
    Serial.println("OK:STATUS");
  }
  else {
    Serial.println("ERR:UNKNOWN:" + cmd.type);
  }
}

void updateBlink() {
  unsigned long now = millis();

  if (isBlinking && now >= blinkEndTime) {
    isBlinking = false;
    needsRedraw = true;
    nextBlinkTime = now + random(BLINK_MIN_MS, BLINK_MAX_MS);
  }

  if (!isBlinking && currentFace == FACE_IDLE && now >= nextBlinkTime) {
    isBlinking = true;
    blinkEndTime = now + BLINK_DUR_MS;
    needsRedraw = true;
  }
}

void render() {
  static unsigned long lastFrame = 0;
  unsigned long now = millis();

  if (now - lastFrame < ANIM_FRAME_MS && !needsRedraw) return;
  lastFrame = now;

  // Check if notify should expire
  if (currentMode == MODE_NOTIFY && now >= notifyEndTime) {
    currentMode = MODE_FACE;
    notifyMessage[0] = '\0';
    needsRedraw = true;
  }

  // Always redraw for animated faces
  bool animated = (currentFace == FACE_LISTENING || currentFace == FACE_THINKING || currentFace == FACE_SPEAKING);
  if (!needsRedraw && !animated) return;

  switch (currentMode) {
    case MODE_DASHBOARD:
      drawDashboardMode(sprite, currentFace, isBlinking, statusInfo);
      break;
    case MODE_NOTIFY:
      drawFace(sprite, currentFace, isBlinking);
      drawNotifyBanner(sprite, notifyMessage);
      break;
    case MODE_FACE:
    default:
      drawFace(sprite, currentFace, isBlinking);

      // Draw animations for special faces
      if (currentFace == FACE_LISTENING) {
        drawListeningAnim(sprite, animFrame);
      } else if (currentFace == FACE_THINKING) {
        drawThinkingAnim(sprite, animFrame);
      } else if (currentFace == FACE_SPEAKING) {
        drawSpeakingMouth(sprite, animFrame);
      }

      // Draw status text at bottom
      if (strlen(textLines[0]) > 0) {
        sprite.setTextColor(TEXT_COLOR);
        sprite.setTextSize(1);
        sprite.drawString(textLines[0], 20, 220);
      }
      break;
  }

  sprite.pushSprite(0, 0);
  needsRedraw = false;
  animFrame++;
}

void loop() {
  processSerial();
  updateBlink();
  render();
}
