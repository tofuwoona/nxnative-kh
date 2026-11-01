// dm_aspect_visible()'s touch-coordinate mapping: fit (default) is always
// the identity (0,0,1,1); fill crops whichever axis the screen is narrower
// on relative to 16:9, always centered, and never exceeds [0,1].
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "../aspect_fill.h"

static int close(double a, double b) { return fabs(a - b) < 1e-9; }

int main(void) {
    // Fit mode (default): always the full frame, regardless of screen shape.
    unsetenv("DM_ASPECT_FILL");
    double ox, oy, fx, fy;
    dm_aspect_visible(2556, 1179, &ox, &oy, &fx, &fy);
    assert(close(ox, 0) && close(oy, 0) && close(fx, 1) && close(fy, 1));
    printf("  ✓ fit mode is the identity mapping on a wide screen\n");

    setenv("DM_ASPECT_FILL", "1", 1);

    // A screen wider than 16:9 (e.g. iPhone ~19.5:9, 2556x1179): crop height, not width.
    dm_aspect_visible(2556, 1179, &ox, &oy, &fx, &fy);
    assert(close(fx, 1) && fy < 1 && fy > 0);
    assert(close(ox, 0) && close(oy, (1 - fy) / 2));
    printf("  ✓ a wider-than-16:9 screen crops height, centered, full width kept (fy=%.4f)\n", fy);

    // A screen narrower than 16:9 (e.g. a 4:3 iPad in landscape, 1024x768): crop width, not height.
    dm_aspect_visible(1024, 768, &ox, &oy, &fx, &fy);
    assert(close(fy, 1) && fx < 1 && fx > 0);
    assert(close(oy, 0) && close(ox, (1 - fx) / 2));
    printf("  ✓ a narrower-than-16:9 screen crops width, centered, full height kept (fx=%.4f)\n", fx);

    // Exactly 16:9: no crop at all.
    dm_aspect_visible(1920, 1080, &ox, &oy, &fx, &fy);
    assert(close(ox, 0) && close(oy, 0) && close(fx, 1) && close(fy, 1));
    printf("  ✓ an exact 16:9 screen crops nothing even in fill mode\n");

    // A degenerate size falls back to the identity instead of dividing by zero.
    dm_aspect_visible(0, 0, &ox, &oy, &fx, &fy);
    assert(close(ox, 0) && close(oy, 0) && close(fx, 1) && close(fy, 1));
    printf("  ✓ a degenerate (0x0) screen size falls back to the identity, no divide-by-zero\n");

    unsetenv("DM_ASPECT_FILL");
    puts("aspect fill touch mapping: 5 checks, 0 failed");
    return 0;
}
