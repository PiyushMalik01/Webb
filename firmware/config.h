#ifndef CONFIG_H
#define CONFIG_H

// Serial settings
#define SERIAL_BAUD 115200
#define CMD_BUFFER_SIZE 256

// Display colors
#define BG_COLOR     0x0000   // Black
#define FACE_COLOR   0xFFFF   // White
#define ACCENT_COLOR 0x7BEF   // Light gray
#define TEXT_COLOR   0xBDF7   // Muted white
#define NOTIFY_BG    0x18E3   // Dark gray

// Face geometry (centered on 320x240 landscape)
#define FACE_CX      160
#define FACE_CY      100
#define EYE_LEFT_X   120
#define EYE_RIGHT_X  200
#define EYE_Y        80
#define MOUTH_Y      130
#define EYE_RADIUS   12
#define FACE_RECT_W  240
#define FACE_RECT_H  140
#define FACE_RECT_X  40
#define FACE_RECT_Y  20
#define FACE_RECT_R  24

// Animation timing
#define BLINK_MIN_MS  3000
#define BLINK_MAX_MS  6000
#define BLINK_DUR_MS  150
#define ANIM_FPS      15
#define ANIM_FRAME_MS (1000 / ANIM_FPS)

#endif
