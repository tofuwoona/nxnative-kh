#pragma once
#include <math.h>

// Preparatory geometry only: there is deliberately no renderer hook or
// DM_KH2_TRUE_WIDE switch until KH2's world camera and HUD passes are proven
// separable. The full canvas would contain a *new* wider world render; a
// distinct 16:9 HUD layer would be composited into safe, never crop-to-fill.
typedef struct {
    double x, y, w, h;       // HUD-safe rect in destination pixel coordinates
    double left, right;      // world-only strips outside the safe rect
    int expansion_possible;  // 0: retain the existing fitted 16:9 path
} kh2_wide_layout;

static inline kh2_wide_layout kh2_wide_plan(double dw, double dh, double safe_w, double safe_h) {
    kh2_wide_layout out = {0};
    if (!isfinite(dw) || !isfinite(dh) || !isfinite(safe_w) || !isfinite(safe_h) ||
        dw <= 0 || dh <= 0 || safe_w <= 0 || safe_h <= 0) return out;
    // Division order also avoids multiplying huge input dimensions together.
    double ratio = safe_w / safe_h, target = dw / dh;
    if (!isfinite(ratio) || !isfinite(target) || ratio <= 0 || target <= 0) return out;
    double scale = fmin(dw / safe_w, dh / safe_h);
    out.w = safe_w * scale; out.h = safe_h * scale;
    if (!isfinite(out.w) || !isfinite(out.h)) return (kh2_wide_layout){0};
    out.x = (dw - out.w) / 2; out.y = (dh - out.h) / 2;
    if (target > ratio && out.x > 0) {
        // For a wide display, the HUD retains the whole native vertical
        // range and is centered, while world-only imagery would flank it.
        out.x = (dw - out.w) / 2;
        out.y = 0; out.h = dh;
        out.left = out.x; out.right = dw - (out.x + out.w);
        out.expansion_possible = 1;
    }
    return out;
}
