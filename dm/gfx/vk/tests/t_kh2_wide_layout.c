#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../kh2_wide_layout.h"

static int eq(double a, double b) { return fabs(a - b) < 1e-8; }
int main(void) {
    kh2_wide_layout w = kh2_wide_plan(2556, 1179, 1920, 1080);
    assert(w.expansion_possible && eq(w.y, 0) && eq(w.h, 1179));
    assert(eq(w.w, 1179 * 16.0 / 9.0) && eq(w.x, w.left));
    assert(eq(w.left, w.right) && eq(w.left + w.w + w.right, 2556));
    assert(eq(w.x + w.w, 2556 - w.right));
    puts("wide: centered 16:9 HUD; full-height world strips partition canvas without gaps");

    kh2_wide_layout equal = kh2_wide_plan(1920, 1080, 1920, 1080);
    assert(!equal.expansion_possible && eq(equal.x, 0) && eq(equal.y, 0));
    assert(eq(equal.w, 1920) && eq(equal.h, 1080));
    puts("16:9: identity, no world-only strips");

    kh2_wide_layout narrow = kh2_wide_plan(1024, 768, 1920, 1080);
    assert(!narrow.expansion_possible && eq(narrow.x, 0) && narrow.y > 0);
    assert(eq(narrow.w, 1024) && eq(narrow.y * 2 + narrow.h, 768));
    puts("narrow: fail closed to fitted picture, never cut HUD");

    kh2_wide_layout bad = kh2_wide_plan(0, 1179, 1920, 1080);
    assert(!bad.expansion_possible && eq(bad.w, 0));
    bad = kh2_wide_plan(NAN, 1179, 1920, 1080);
    assert(!bad.expansion_possible && eq(bad.w, 0));
    bad = kh2_wide_plan(INFINITY, 1179, 1920, 1080);
    assert(!bad.expansion_possible && eq(bad.w, 0));
    puts("invalid sizes: fail closed without invalid geometry");
    return 0;
}
