#pragma once
#include <stdint.h>
// Apple physical X/Y were already mapped by position; undo that pre-swap
// only when the opt-in name-based face swap is enabled.
static inline uint64_t dm_pad_before_face_swap(uint64_t mask, int enabled) {
    if (!enabled) return mask;
    uint64_t b2 = (mask >> 2) & 1ULL;
    uint64_t b3 = (mask >> 3) & 1ULL;
    uint64_t result = mask;
    result &= ~(1ULL << 2);
    result &= ~(1ULL << 3);
    result |= (b3 << 2);
    result |= (b2 << 3);
    return result;
}
static inline uint64_t dm_face_swap(uint64_t buttons, int enabled) {
    if (!enabled) return buttons;
    uint64_t a = buttons & 1u;
    uint64_t b = (buttons >> 1) & 1u;
    uint64_t x = (buttons >> 2) & 1u;
    uint64_t y = (buttons >> 3) & 1u;
    return (buttons & ~UINT64_C(0xf)) | (b << 0) | (a << 1) | (y << 2) | (x << 3);
}
