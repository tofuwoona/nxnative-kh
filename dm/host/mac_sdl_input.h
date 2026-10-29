#pragma once
#include <stdint.h>
#include <SDL.h>
#include "dm_input.h"
typedef struct { uint64_t buttons; int32_t lx,ly,rx,ry; } mac_pad_state;
static inline mac_pad_state mac_sdl_map(uint32_t b,int16_t lx,int16_t ly,int16_t rx,int16_t ry,int16_t lt,int16_t rt) {
    mac_pad_state s = {0};
    int32_t a = lx, b_y = ly, c = rx, d = ry;
    if (a < -32767) a = -32767; if (b_y < -32767) b_y = -32767;
    if (c < -32767) c = -32767; if (d < -32767) d = -32767;
    s.lx = a; s.ly = -b_y; s.rx = c; s.ry = -d;
    if ((int64_t)s.lx * s.lx + (int64_t)s.ly * s.ly <= 3277 * 3277) { s.lx = 0; s.ly = 0; }
    if ((int64_t)s.rx * s.rx + (int64_t)s.ry * s.ry <= 3277 * 3277) { s.rx = 0; s.ry = 0; }
#define MAP(k, v) if (b & (1u << SDL_CONTROLLER_BUTTON_##k)) s.buttons |= DM_BTN_##v
    MAP(A, B); MAP(B, A); MAP(X, Y); MAP(Y, X);
    MAP(LEFTSHOULDER, L); MAP(RIGHTSHOULDER, R);
    MAP(BACK, MINUS); MAP(START, PLUS); MAP(LEFTSTICK, LS); MAP(RIGHTSTICK, RS);
    MAP(DPAD_UP, UP); MAP(DPAD_DOWN, DOWN); MAP(DPAD_LEFT, LEFT); MAP(DPAD_RIGHT, RIGHT);
#undef MAP
    if (lt >= 16384) s.buttons |= DM_BTN_ZL;
    if (rt >= 16384) s.buttons |= DM_BTN_ZR;
    return s;
}
