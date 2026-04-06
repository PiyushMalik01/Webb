#ifndef SERIAL_PROTOCOL_H
#define SERIAL_PROTOCOL_H

#include <Arduino.h>

struct Command {
  String type;     // FACE, TEXT, STATUS, ANIM, PROGRESS, NOTIFY, MODE, CLEAR, BRIGHTNESS
  String payload;  // Everything after the colon
};

bool parseCommand(const String &line, Command &cmd) {
  String trimmed = line;
  trimmed.trim();
  if (trimmed.length() == 0) return false;

  int colonIdx = trimmed.indexOf(':');
  if (colonIdx < 0) {
    // Legacy format: bare face name (e.g., "HAPPY")
    cmd.type = "FACE";
    cmd.payload = trimmed;
    return true;
  }

  cmd.type = trimmed.substring(0, colonIdx);
  cmd.payload = trimmed.substring(colonIdx + 1);
  cmd.type.toUpperCase();
  cmd.payload.trim();
  return true;
}

#endif
