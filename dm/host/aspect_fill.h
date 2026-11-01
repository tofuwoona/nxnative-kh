#pragma once
#include <stdlib.h>
#include <string.h>
#include <math.h>

// DM_ASPECT_FILL=1: crop the game's 16:9 picture to fill the whole screen
// instead of fitting it inside the screen with black bars on the rest
// (dm/gfx/nvn/nvn_mtl.m present_fit does the actual crop at present time;
// front_ios.m / front_mac.m let the game view take the whole screen instead
// of a centered 16:9 rect when this is on). Off by default. This never
// stretches the image -- it only crops top/bottom or left/right of the
// game's native 16:9 frame to match the screen's aspect ratio, so HUD
// elements positioned near whichever edge gets cropped may be clipped; see
// dm/games/010090C022978000/README.md, "Open issues", for the known
// unverified risk (projection/render targets/HUD/movies were not all tested
// together at a non-16:9 aspect). This header shares the effective crop
// policy, picture rectangle and matching touch-coordinate mapping across
// present, iOS layout/input and Mac input.
// Temporary KH2 fallback, not true widescreen: keep the ENTIRE original
// picture (world, HUD, menus and movies) at 16:9. Explicitly wins over crop,
// including when both switches came from an env file. Other profiles ignore it.
static inline int dm_preserve_full_hud_on(void) {
#if defined(DM_GAME_PROGRAM_ID) && DM_GAME_PROGRAM_ID == 0x010090C022978003ull
    const char *e = getenv("DM_PRESERVE_FULL_HUD");
    return e && *e && strcmp(e, "0");
#else
    return 0;
#endif
}
static inline int dm_aspect_fill_on(void) {
    const char *e = getenv("DM_ASPECT_FILL");
    return !dm_preserve_full_hud_on() && e && *e && strcmp(e, "0");
}

// screen_w/screen_h: the touch view's size, in the same units as the touch
// point (e.g. both in points, or both in pixels). Returns, in normalized
// [0,1] 16:9 touch-space fractions, the visible slice's origin and size
// (ox+fx <= 1, oy+fy <= 1, both centered: ox == (1-fx)/2). Fit mode (the
// default, or an invalid size) always returns the full frame (0,0,1,1);
// fill mode crops whichever axis the screen is narrower on relative to 16:9.
static inline void dm_aspect_visible(double screen_w, double screen_h, double *ox, double *oy, double *fx, double *fy) {
    if (!dm_aspect_fill_on() || screen_w <= 0 || screen_h <= 0) { *ox = *oy = 0; *fx = *fy = 1; return; }
    double want = screen_w / screen_h, have = 16.0 / 9.0;
    *fx = want > have ? 1.0 : want / have;
    *fy = want > have ? have / want : 1.0;
    *ox = (1 - *fx) / 2; *oy = (1 - *fy) / 2;
}

// One top-left-origin picture rectangle for iOS layout + iOS/Mac input.
// Only Preserve full HUD uses safe-area insets: existing fit/fill stay as-is.
// Keep doubles (including fractional points) so view and input agree at any scale.
#define DM_ASPECT_LAYOUT_VERSION 1
typedef struct { double x, y, w, h; } dm_aspect_rect;
static inline dm_aspect_rect dm_aspect_frame(double w, double h, double left, double top, double right, double bottom) {
    if (w <= 0 || h <= 0) return (dm_aspect_rect){0,0,0,0};
    double x=0, y=0, aw=w, ah=h;
    if (dm_preserve_full_hud_on()) {
        x=fmin(fmax(left,0),w); y=fmin(fmax(top,0),h);
        aw=fmax(0,w-x-fmax(right,0)); ah=fmax(0,h-y-fmax(bottom,0));
    }
    if (!dm_aspect_fill_on()) {
        double fw=aw, fh=ah;
        if (aw > ah * (16.0/9.0)) fw=ah*(16.0/9.0); else fh=aw*(9.0/16.0);
        x+=(aw-fw)/2; y+=(ah-fh)/2; aw=fw; ah=fh;
    }
    return (dm_aspect_rect){x,y,aw,ah};
}
static inline void dm_aspect_touch(dm_aspect_rect f, double x, double y, double *nx, double *ny) {
    if (f.w <= 0 || f.h <= 0) { *nx=*ny=0; return; }
    double ox,oy,fx,fy; dm_aspect_visible(f.w,f.h,&ox,&oy,&fx,&fy);
    *nx=ox+fmin(fmax((x-f.x)/f.w,0),1)*fx;
    *ny=oy+fmin(fmax((y-f.y)/f.h,0),1)*fy;
}
