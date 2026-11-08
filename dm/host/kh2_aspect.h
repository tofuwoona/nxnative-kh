#pragma once
#include <math.h>
#include <stdint.h>

typedef struct { uint32_t width, height; } dm_kh2_extent;
// Startup-only writer: after loading/final settings and viewport creation,
// BEFORE guest entry. Reinitialization is allowed only with the guest stopped.
// Readers atomically snapshot a coherent pair, zero/zero means disabled.
void dm_kh2_aspect_init(uint32_t viewport_w, uint32_t viewport_h);
dm_kh2_extent dm_kh2_aspect_size(void);
int dm_kh2_aspect_on(void);

// Exact viewport ratio, not a device/model whitelist. Stay inside the original
// 1920x1080 per-axis budget and a 960x540 quality floor. Supported landscape
// range is 16:9..20:9; invalid/portrait/tablet/coprime-too-large inputs fail closed.
static inline dm_kh2_extent dm_kh2_aspect_choose(uint32_t w, uint32_t h) {
    dm_kh2_extent off = {0, 0};
    if (!w || !h || w > 16384 || h > 16384 ||
        (uint64_t)w * 9 < (uint64_t)h * 16 ||
        (uint64_t)w * 9 > (uint64_t)h * 20) return off;
    uint32_t a = w, b = h;
    while (b) { uint32_t r = a % b; a = b; b = r; }
    w /= a; h /= a;
    uint32_t scale = 1920 / w, sy = 1080 / h;
    if (scale > sy) scale = sy;
    // Prefer an even scale (even render extents), but never halve a good
    // odd-scale result below the quality floor just for alignment.
    if ((scale & 1) && scale > 1 && w * (scale - 1) >= 960 && h * (scale - 1) >= 540) scale--;
    if (w * scale < 960 || h * scale < 540) return off;
    return (dm_kh2_extent){w * scale, h * scale};
}

// Exact KH1 Program 1 keeps its vertical field of view when OE stays at the
// authentic handheld 720-line baseline. Round only the width to the startup
// viewport ratio; the fit error is bounded to half a source pixel.
static inline dm_kh2_extent dm_kh1_aspect_choose(uint32_t w, uint32_t h) {
    if (!dm_kh2_aspect_choose(w, h).width) return (dm_kh2_extent){0, 0};
    uint32_t width = (uint32_t)(((uint64_t)w * 720 + h / 2) / h);
    if (width < 1280 || width > 1600) return (dm_kh2_extent){0, 0};
    return (dm_kh2_extent){width, 720};
}

// Convert an actual pixel viewport without truncation, overflow or NaN casts.
// Floating point UI scale multiplication may have tiny representation error;
// this is not a license to approximate an unsupported exact integer ratio.
static inline dm_kh2_extent dm_kh2_aspect_pixels(double w, double h) {
    if (!isfinite(w) || !isfinite(h) || w < 1 || h < 1 || w > 16384 || h > 16384 ||
        fabs(w - round(w)) > 0.000001 || fabs(h - round(h)) > 0.000001)
        return (dm_kh2_extent){0, 0};
    return (dm_kh2_extent){(uint32_t)round(w), (uint32_t)round(h)};
}

// Strict bounded diagnostic pixel viewport, not a screenshot encoder size.
static inline int dm_kh2_aspect_parse_viewport(const char *s, dm_kh2_extent *out) {
    uint32_t v[2] = {0, 0};
    if (!s || !out) return 0;
    for (int i = 0; i < 2; i++) {
        if (*s < '0' || *s > '9') return 0;
        do {
            v[i] = v[i] * 10 + (uint32_t)(*s++ - '0');
            if (v[i] > 4096) return 0; // bounded before the next multiply
        } while (*s >= '0' && *s <= '9');
        if (i == 0 && *s++ != 'x') return 0;
    }
    if (*s || v[0] < 320 || v[1] < 180) return 0;
    *out = (dm_kh2_extent){v[0], v[1]};
    return 1;
}

// Uncropped source fit, shared by present and touch only in this experiment.
// Fractional viewport avoids point/pixel rounding divergence. Legacy image
// origin flooring and near-aspect snapping remain untouched when disabled.
static inline void dm_kh2_aspect_fit(double sw, double sh, double dw, double dh,
                                     double *x, double *y, double *w, double *h) {
    double s = fmin(dw / sw, dh / sh);
    *w = sw * s; *h = sh * s; *x = (dw - *w) / 2; *y = (dh - *h) / 2;
}
