#pragma once
#include <stdlib.h>
#include <string.h>

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
// together at a non-16:9 aspect). This header only computes the matching
// touch-coordinate mapping, shared by the iOS (DmGamepad.m) and Mac
// (front_mac.m) front ends, so taps land where the cropped picture actually
// is on screen.
static inline int dm_aspect_fill_on(void) {
    const char *e = getenv("DM_ASPECT_FILL");
    return e && *e && strcmp(e, "0");
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
